import asyncio
import logging
import os
import subprocess
from typing import Optional, Tuple, List, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

class FFmpegError(Exception):
    """Custom exception for FFmpeg related errors"""
    pass

def get_video_info(file_path: str) -> Dict[str, Any]:
    """Get video information using ffprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,r_frame_rate,codec_name',
            '-show_entries', 'format=size,duration',
            '-of', 'json',
            file_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        import json
        info = json.loads(result.stdout)
        
        if not info.get('streams') or not info.get('format'):
            raise FFmpegError("Could not get video information")
        
        stream = info['streams'][0]
        format_info = info['format']
        
        # Calculate FPS
        fps = 0
        if 'r_frame_rate' in stream:
            num, den = map(int, stream['r_frame_rate'].split('/'))
            if den != 0:
                fps = num / den
        
        return {
            'width': int(stream.get('width', 0)),
            'height': int(stream.get('height', 0)),
            'duration': float(stream.get('duration', format_info.get('duration', 0))),
            'fps': fps,
            'codec': stream.get('codec_name', 'unknown'),
            'size': int(format_info.get('size', 0)),
            'format': os.path.splitext(file_path)[1].lstrip('.').lower()
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe error: {e.stderr}")
        raise FFmpegError(f"خطا در دریافت اطلاعات ویدیو: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error in get_video_info: {str(e)}", exc_info=True)
        raise FFmpegError(f"خطای ناشناخته در پردازش ویدیو: {str(e)}")

async def compress_video(
    input_path: str,
    output_path: str,
    target_size: int,  # in bytes
    min_bitrate: int = 100,  # kbps
    max_bitrate: int = 2000,  # kbps
    preset: str = 'medium',
    crf: int = 23,
) -> str:
    """
    Compress video to fit target size while maintaining quality
    
    Args:
        input_path: Path to input video file
        output_path: Path to save compressed video
        target_size: Target size in bytes
        min_bitrate: Minimum bitrate in kbps
        max_bitrate: Maximum bitrate in kbps
        preset: FFmpeg preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
        crf: Constant Rate Factor (18-28 is good, lower is better quality)
    
    Returns:
        Path to compressed video
    """
    try:
        # Get video info
        video_info = get_video_info(input_path)
        duration = video_info['duration']
        
        if duration <= 0:
            raise FFmpegError("مدت زمان ویدیو نامعتبر است")
        
        # Calculate target bitrate (in kbps)
        target_bitrate = int((target_size * 8) / (1_048_576 * duration))  # Convert to kbps
        target_bitrate = max(min(target_bitrate, max_bitrate), min_bitrate)
        
        # Prepare FFmpeg command
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', preset,
            '-crf', str(crf),
            '-b:v', f'{target_bitrate}k',
            '-maxrate', f'{int(target_bitrate * 1.2)}k',  # Maximum bitrate (with 20% buffer)
            '-bufsize', f'{int(target_bitrate * 2)}k',    # Buffer size (2x target bitrate)
            '-movflags', '+faststart',  # For web streaming
            '-threads', '0',  # Use all available threads
            '-pass', '1',
            '-f', 'mp4',
            output_path
        ]
        
        # Run FFmpeg
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for process to complete
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise FFmpegError(f"خطا در فشرده‌سازی ویدیو: {stderr.decode()}")
        
        # Check output file
        if not os.path.exists(output_path):
            raise FFmpegError("خطا در ایجاد فایل خروجی")
        
        # Get output file size
        output_size = os.path.getsize(output_path)
        
        # If output is still too large, try again with lower quality
        if output_size > target_size * 1.1:  # 10% tolerance
            logger.info(f"Output size {output_size} > target {target_size}, retrying with lower quality...")
            os.remove(output_path)  # Remove failed attempt
            return await compress_video(
                input_path,
                output_path,
                target_size,
                min_bitrate,
                max_bitrate,
                preset,
                min(crf + 2, 28)  # Increase CRF (lower quality) for next attempt
            )
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error in compress_video: {str(e)}", exc_info=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        raise FFmpegError(f"خطا در پردازش ویدیو: {str(e)}")

async def add_watermark(
    input_path: str,
    output_path: str,
    watermark_text: str,
    position: str = 'bottom-right',
    font_size: int = 24,
    opacity: float = 0.6
) -> str:
    """
    Add watermark text to a video
    
    Args:
        input_path: Path to input video
        output_path: Path to save watermarked video
        watermark_text: Text to use as watermark
        position: Position of watermark (top-left, top-right, bottom-left, bottom-right, center)
        font_size: Font size
        opacity: Watermark opacity (0.0 - 1.0)
    
    Returns:
        Path to watermarked video
    """
    try:
        # Map position to FFmpeg overlay coordinates
        position_map = {
            'top-left': f'{font_size}:{font_size}',
            'top-right': f'main_w-text_w-{font_size}:{font_size}',
            'bottom-left': f'{font_size}:main_h-text_h-{font_size}',
            'bottom-right': f'main_w-text_w-{font_size}:main_h-text_h-{font_size}',
            'center': '(main_w-text_w)/2:(main_h-text_h)/2'
        }
        
        overlay_pos = position_map.get(position.lower(), position_map['bottom-right'])
        
        # Prepare FFmpeg command
        cmd = [
            'ffmpeg',
            '-y',
            '-i', input_path,
            '-vf', (
                f"drawtext=text='{watermark_text}':"
                f"fontcolor=white@0.6:fontsize={font_size}:"
                f"x={overlay_pos}:"
                f"box=1:boxcolor=black@0.3:boxborderw=5"
            ),
            '-codec:a', 'copy',  # Copy audio without re-encoding
            output_path
        ]
        
        # Run FFmpeg
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for process to complete
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise FFmpegError(f"خطا در اضافه کردن واترمارک: {stderr.decode()}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error in add_watermark: {str(e)}", exc_info=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        raise FFmpegError(f"خطا در پردازش ویدیو: {str(e)}")

def get_supported_formats() -> list:
    """Get list of supported video/audio formats"""
    try:
        # Run ffmpeg -formats
        result = subprocess.run(
            ['ffmpeg', '-formats'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        # Parse output to get supported formats
        formats = []
        for line in result.stdout.split('\n'):
            if line.startswith('  '):
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] in ['DE', 'D', 'E']:
                    formats.append(parts[1])
        
        return formats
        
    except Exception as e:
        logger.error(f"Error getting supported formats: {str(e)}")
        return []
