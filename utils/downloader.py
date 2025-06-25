import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional, Any, Union

import yt_dlp

# Configure logging
logger = logging.getLogger(__name__)

class DownloadError(Exception):
    """Custom exception for download errors"""
    pass

class Downloader:
    """Handles downloading media from various platforms using yt-dlp"""
    
    def __init__(self):
        # Default options for yt-dlp
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'no_color': True,
            'extract_flat': False,
            'skip_download': True,
            'simulate': True,
            'force_generic_extractor': False,
            'noplaylist': True,
        }
    
    async def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """Get available formats for a given URL"""
        try:
            # Run yt-dlp in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Get video info
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = await loop.run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=False)
                )
            
            if not info:
                raise DownloadError("Could not extract video information")
            
            # Handle playlists
            if 'entries' in info:
                # For now, just get the first entry
                if not info['entries']:
                    raise DownloadError("No videos found in playlist")
                info = info['entries'][0]
            
            # Extract available formats
            formats = info.get('formats', [])
            
            # Filter and clean formats
            cleaned_formats = []
            for fmt in formats:
                # Skip formats without video or with no format_id
                if not fmt.get('format_id') or fmt.get('vcodec') == 'none':
                    continue
                
                # Get format info
                format_info = {
                    'format_id': fmt['format_id'],
                    'ext': fmt.get('ext', 'mp4'),
                    'resolution': self._get_resolution(fmt),
                    'filesize': fmt.get('filesize') or fmt.get('filesize_approx'),
                    'vcodec': fmt.get('vcodec', ''),
                    'acodec': fmt.get('acodec', ''),
                    'fps': fmt.get('fps'),
                    'tbr': fmt.get('tbr'),
                }
                
                # Calculate approximate size if not available
                if not format_info['filesize'] and 'filesize_approx' not in fmt:
                    duration = info.get('duration') or 0
                    tbr = fmt.get('tbr') or 0
                    if duration and tbr:
                        # Very rough estimate: tbr is in kbps, duration in seconds
                        format_info['filesize_approx'] = (tbr * 1000 * duration) / 8  # in bytes
                
                cleaned_formats.append(format_info)
            
            return cleaned_formats
            
        except yt_dlp.DownloadError as e:
            logger.error(f"Download error: {str(e)}")
            raise DownloadError("خطا در دریافت اطلاعات ویدیو. لطفا لینک را بررسی کنید.")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise DownloadError("خطای ناشناخته در پردازش درخواست.")
    
    async def download(self, url: str, format_id: str, output_template: str, 
                      progress_hook=None) -> str:
        """Download a video with the specified format"""
        try:
            # Configure download options
            download_opts = {
                **self.ydl_opts,
                'format': format_id,
                'outtmpl': output_template,
                'noprogress': True,
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'extract_flat': False,
                'skip_download': False,
                'simulate': False,
            }
            
            if progress_hook:
                download_opts['progress_hooks'] = [progress_hook]
            
            # Run download in a separate thread
            loop = asyncio.get_event_loop()
            
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                # First get the info to determine the output filename
                info = await loop.run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=False)
                )
                
                if not info:
                    raise DownloadError("Could not extract video information")
                
                # Handle playlists
                if 'entries' in info:
                    if not info['entries']:
                        raise DownloadError("No videos found in playlist")
                    info = info['entries'][0]
                
                # Get the output filename
                output_path = ydl.prepare_filename(info)
                
                # Start the download
                await loop.run_in_executor(
                    None,
                    lambda: ydl.download([url])
                )
                
                return output_path
                
        except yt_dlp.DownloadError as e:
            logger.error(f"Download error: {str(e)}")
            raise DownloadError(f"خطا در دانلود ویدیو: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected download error: {str(e)}", exc_info=True)
            raise DownloadError(f"خطای ناشناخته در دانلود: {str(e)}")
    
    def _get_resolution(self, fmt: Dict[str, Any]) -> str:
        """Get resolution string from format info"""
        if fmt.get('resolution'):
            return fmt['resolution']
        
        height = fmt.get('height')
        if height:
            return f"{height}p"
        
        # Try to extract from format string
        format_note = fmt.get('format_note', '').lower()
        if '4k' in format_note:
            return '4K'
        
        for res in ['1440p', '1080p', '720p', '480p', '360p', '240p', '144p']:
            if res in format_note:
                return res
        
        # Try to extract from format_id
        format_id = fmt.get('format_id', '').lower()
        for res in ['4k', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p']:
            if res in format_id:
                return res
        
        # Default to SD if no resolution found
        return 'SD'
