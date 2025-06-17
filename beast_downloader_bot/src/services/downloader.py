import os
import asyncio
import yt_dlp
import tempfile
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from pathlib import Path
import aiofiles
from loguru import logger

from ..config import download_config, YDL_OPTIONS, PLATFORM_OPTIONS
from ..utils.helpers import sanitize_filename, get_file_hash

class DownloadProgress:
    """کلاس مدیریت پیشرفت دانلود"""
    
    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed = "0 B/s"
        self.eta = 0
        self.percent = 0
        self.status = "downloading"
        
    def hook(self, d: dict):
        """Hook برای yt-dlp"""
        if d['status'] == 'downloading':
            self.downloaded_bytes = d.get('downloaded_bytes', 0)
            self.total_bytes = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            self.speed = d.get('speed_str', '0 B/s')
            self.eta = d.get('eta', 0)
            
            if self.total_bytes > 0:
                self.percent = int((self.downloaded_bytes / self.total_bytes) * 100)
            
            if self.callback:
                asyncio.create_task(self.callback({
                    'downloaded_bytes': self.downloaded_bytes,
                    'total_bytes': self.total_bytes,
                    'speed': self.speed,
                    'eta': self.eta,
                    'percent': self.percent,
                    'status': 'downloading'
                }))
                
        elif d['status'] == 'finished':
            self.status = 'finished'
            if self.callback:
                asyncio.create_task(self.callback({
                    'status': 'finished',
                    'percent': 100
                }))

class VideoDownloader:
    """سرویس اصلی دانلود ویدیو"""
    
    def __init__(self):
        self.ydl_opts = YDL_OPTIONS.copy()
        self.platform_options = PLATFORM_OPTIONS
        
    async def get_video_info(self, url: str, platform: str = None) -> Optional[Dict]:
        """دریافت اطلاعات ویدیو"""
        try:
            # تنظیمات خاص پلتفرم
            opts = self._get_platform_options(platform)
            opts['extract_flat'] = False
            opts['quiet'] = True
            
            # اجرا در thread pool
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                self._extract_info,
                url,
                opts
            )
            
            if not info:
                return None
            
            # پردازش و تمیز کردن اطلاعات
            cleaned_info = self._clean_video_info(info)
            
            # فیلتر فرمت‌ها بر اساس پلتفرم
            cleaned_info['formats'] = self._filter_formats(
                info.get('formats', []),
                platform
            )
            
            return cleaned_info
            
        except Exception as e:
            logger.error(f"Error extracting video info: {str(e)}")
            return None
    
    def _extract_info(self, url: str, opts: dict) -> Optional[dict]:
        """استخراج اطلاعات (blocking)"""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"YoutubeDL extract error: {str(e)}")
            return None
    
    async def download_video(
        self,
        url: str,
        format_id: Optional[str] = None,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        platform: str = None
    ) -> Optional[Dict[str, Any]]:
        """دانلود ویدیو"""
        try:
            # تنظیم مسیر خروجی
            if not output_path:
                temp_dir = tempfile.mkdtemp(dir=download_config.temp_dir)
                output_path = os.path.join(temp_dir, '%(title)s.%(ext)s')
            
            # تنظیمات دانلود
            opts = self._get_download_options(format_id, output_path, platform)
            
            # اضافه کردن progress hook
            if progress_callback:
                progress = DownloadProgress(progress_callback)
                opts['progress_hooks'] = [progress.hook]
            
            # اجرا در thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._download_file,
                url,
                opts
            )
            
            if result and result.get('filepath'):
                # محاسبه هش فایل
                file_hash = await self._calculate_file_hash(result['filepath'])
                result['file_hash'] = file_hash
                
                # تغییر نام فایل نهایی
                final_path = await self._finalize_file(result['filepath'], platform)
                result['filepath'] = final_path
            
            return result
            
        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            return None
    
    def _download_file(self, url: str, opts: dict) -> Optional[dict]:
        """دانلود فایل (blocking)"""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # پیدا کردن مسیر فایل دانلود شده
                if 'requested_downloads' in info:
                    filepath = info['requested_downloads'][0]['filepath']
                else:
                    # برای فرمت‌های قدیمی
                    filepath = ydl.prepare_filename(info)
                    # بررسی پسوند‌های مختلف
                    for ext in ['.mp4', '.webm', '.mkv', '.mp3', '.m4a']:
                        if os.path.exists(filepath.replace('.%(ext)s', ext)):
                            filepath = filepath.replace('.%(ext)s', ext)
                            break
                
                return {
                    'filepath': filepath,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'filesize': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                    'format': info.get('ext', 'unknown'),
                    'thumbnail': info.get('thumbnail'),
                    'info': info
                }
                
        except Exception as e:
            logger.error(f"YoutubeDL download error: {str(e)}")
            return None
    
    async def download_audio(
        self,
        url: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        platform: str = None,
        quality: str = '192'
    ) -> Optional[Dict[str, Any]]:
        """دانلود فقط صوت"""
        try:
            if not output_path:
                temp_dir = tempfile.mkdtemp(dir=download_config.temp_dir)
                output_path = os.path.join(temp_dir, '%(title)s.mp3')
            
            opts = self._get_audio_options(output_path, quality, platform)
            
            if progress_callback:
                progress = DownloadProgress(progress_callback)
                opts['progress_hooks'] = [progress.hook]
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._download_file,
                url,
                opts
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error downloading audio: {str(e)}")
            return None
    
    def _get_platform_options(self, platform: str) -> dict:
        """دریافت تنظیمات خاص پلتفرم"""
        opts = self.ydl_opts.copy()
        
        if platform and platform in self.platform_options:
            platform_opts = self.platform_options[platform]
            
            # اضافه کردن cookies یا authentication
            if platform_opts.get('cookiefile') and os.path.exists(platform_opts['cookiefile']):
                opts['cookiefile'] = platform_opts['cookiefile']
            
            if platform_opts.get('username') and platform_opts.get('password'):
                opts['username'] = platform_opts['username']
                opts['password'] = platform_opts['password']
        
        return opts
    
    def _get_download_options(
        self,
        format_id: Optional[str],
        output_path: str,
        platform: str
    ) -> dict:
        """تنظیمات دانلود ویدیو"""
        opts = self._get_platform_options(platform)
        opts['outtmpl'] = output_path
        
        if format_id:
            opts['format'] = format_id
        else:
            # فرمت پیش‌فرض بر اساس پلتفرم
            if platform == 'twitter':
                opts['format'] = 'best[ext=mp4]'
            elif platform == 'instagram':
                opts['format'] = 'best'
            else:
                opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        
        return opts
    
    def _get_audio_options(self, output_path: str, quality: str, platform: str) -> dict:
        """تنظیمات دانلود صوت"""
        opts = self._get_platform_options(platform)
        opts['outtmpl'] = output_path
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': quality,
        }]
        
        return opts
    
    def _clean_video_info(self, info: dict) -> dict:
        """تمیز کردن اطلاعات ویدیو"""
        return {
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration', 0),
            'view_count': info.get('view_count', 0),
            'like_count': info.get('like_count', 0),
            'upload_date': info.get('upload_date', ''),
            'uploader': info.get('uploader', 'Unknown'),
            'uploader_id': info.get('uploader_id', ''),
            'description': info.get('description', '')[:500],  # محدود کردن طول
            'thumbnail': info.get('thumbnail', ''),
            'webpage_url': info.get('webpage_url', ''),
            'extractor': info.get('extractor', ''),
            'formats': []
        }
    
    def _filter_formats(self, formats: List[dict], platform: str) -> List[dict]:
        """فیلتر و مرتب‌سازی فرمت‌ها"""
        filtered = []
        
        for fmt in formats:
            # فقط فرمت‌های با ویدیو
            if fmt.get('vcodec') == 'none':
                continue
            
            # فیلتر بر اساس پلتفرم
            if platform == 'instagram' and not fmt.get('http_headers'):
                continue
            
            filtered.append({
                'format_id': fmt.get('format_id'),
                'ext': fmt.get('ext'),
                'height': fmt.get('height', 0),
                'width': fmt.get('width', 0),
                'filesize': fmt.get('filesize', 0),
                'vcodec': fmt.get('vcodec'),
                'acodec': fmt.get('acodec'),
                'fps': fmt.get('fps', 0),
                'vbr': fmt.get('vbr', 0),
                'abr': fmt.get('abr', 0),
            })
        
        # مرتب‌سازی بر اساس کیفیت
        filtered.sort(key=lambda x: (x.get('height', 0), x.get('vbr', 0)), reverse=True)
        
        return filtered[:20]  # حداکثر 20 فرمت
    
    async def _calculate_file_hash(self, filepath: str) -> str:
        """محاسبه هش فایل"""
        return await get_file_hash(filepath)
    
    async def _finalize_file(self, filepath: str, platform: str) -> str:
        """نهایی کردن فایل دانلود شده"""
        try:
            # تولید نام جدید
            path = Path(filepath)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = sanitize_filename(path.stem)
            new_name = f"{platform}_{safe_name}_{timestamp}{path.suffix}"
            
            # مسیر نهایی
            final_dir = os.path.join(download_config.download_dir, platform)
            os.makedirs(final_dir, exist_ok=True)
            
            final_path = os.path.join(final_dir, new_name)
            
            # انتقال فایل
            os.rename(filepath, final_path)
            
            # حذف دایرکتوری موقت
            temp_dir = path.parent
            if 'temp' in str(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except:
                    pass
            
            return final_path
            
        except Exception as e:
            logger.error(f"Error finalizing file: {str(e)}")
            return filepath
    
    async def extract_thumbnail(self, video_path: str) -> Optional[str]:
        """استخراج thumbnail از ویدیو"""
        try:
            import ffmpeg
            
            output_path = video_path.replace(Path(video_path).suffix, '_thumb.jpg')
            
            stream = ffmpeg.input(video_path, ss=1)
            stream = ffmpeg.output(stream, output_path, vframes=1)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, ffmpeg.run, stream, None, True, True)
            
            return output_path if os.path.exists(output_path) else None
            
        except Exception as e:
            logger.error(f"Error extracting thumbnail: {str(e)}")
            return None