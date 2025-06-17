import os
import shutil
import tempfile
import aiofiles
from pathlib import Path
from typing import Optional, Tuple, Dict
from datetime import datetime
import ffmpeg
from PIL import Image
from loguru import logger

from ..config import download_config
from ..utils.helpers import sanitize_filename, get_file_type, get_file_hash

class FileManager:
    """سرویس مدیریت فایل‌های دانلود شده"""
    
    def __init__(self):
        self.download_dir = download_config.download_dir
        self.temp_dir = download_config.temp_dir
        
        # ایجاد دایرکتوری‌ها
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
    
    async def process_downloaded_file(
        self,
        file_path: str,
        platform: str,
        target_format: str
    ) -> str:
        """
        پردازش فایل دانلود شده
        - تبدیل فرمت در صورت نیاز
        - بهینه‌سازی
        - انتقال به محل نهایی
        """
        try:
            # بررسی وجود فایل
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # تعیین نوع فایل
            mime_type = get_file_type(file_path)
            
            # تبدیل فرمت در صورت نیاز
            if self._needs_conversion(mime_type, target_format):
                file_path = await self.convert_format(file_path, target_format)
            
            # بهینه‌سازی
            if 'video' in mime_type:
                file_path = await self.optimize_video(file_path)
            elif 'audio' in mime_type:
                file_path = await self.optimize_audio(file_path)
            
            # ایجاد thumbnail
            thumbnail_path = None
            if 'video' in mime_type:
                thumbnail_path = await self.generate_thumbnail(file_path)
            
            # انتقال به محل نهایی
            final_path = await self.move_to_storage(file_path, platform)
            
            # انتقال thumbnail
            if thumbnail_path:
                thumb_final = await self.move_to_storage(thumbnail_path, platform)
                # ذخیره مسیر thumbnail در metadata
            
            return final_path
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            raise
    
    def _needs_conversion(self, mime_type: str, target_format: str) -> bool:
        """بررسی نیاز به تبدیل فرمت"""
        current_format = mime_type.split('/')[-1]
        
        # برای MP3
        if target_format == 'mp3' and 'audio' in mime_type and current_format != 'mpeg':
            return True
        
        # برای MP4
        if target_format == 'mp4' and 'video' in mime_type and current_format not in ['mp4', 'x-m4v']:
            return True
        
        return False
    
    async def convert_format(self, input_path: str, target_format: str) -> str:
        """تبدیل فرمت فایل"""
        try:
            output_path = input_path.rsplit('.', 1)[0] + f'.{target_format}'
            
            if target_format == 'mp3':
                # تبدیل به MP3
                stream = ffmpeg.input(input_path)
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    acodec='libmp3lame',
                    audio_bitrate='192k'
                )
            elif target_format == 'mp4':
                # تبدیل به MP4
                stream = ffmpeg.input(input_path)
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    vcodec='libx264',
                    acodec='aac',
                    crf=23,
                    preset='medium'
                )
            else:
                return input_path
            
            # اجرای تبدیل
            await self._run_ffmpeg(stream, overwrite=True)
            
            # حذف فایل اصلی
            os.remove(input_path)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Format conversion failed: {str(e)}")
            return input_path
    
    async def optimize_video(self, video_path: str) -> str:
        """بهینه‌سازی ویدیو"""
        try:
            # بررسی نیاز به بهینه‌سازی
            probe = ffmpeg.probe(video_path)
            video_info = next(
                stream for stream in probe['streams']
                if stream['codec_type'] == 'video'
            )
            
            # اگر bitrate خیلی بالا بود
            bitrate = int(video_info.get('bit_rate', 0))
            if bitrate > 5_000_000:  # 5 Mbps
                output_path = video_path.rsplit('.', 1)[0] + '_optimized.mp4'
                
                stream = ffmpeg.input(video_path)
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    vcodec='libx264',
                    crf=23,
                    preset='medium',
                    movflags='faststart'  # برای streaming بهتر
                )
                
                await self._run_ffmpeg(stream, overwrite=True)
                
                # اگر حجم کمتر شد، جایگزین کن
                if os.path.getsize(output_path) < os.path.getsize(video_path):
                    os.remove(video_path)
                    return output_path
                else:
                    os.remove(output_path)
            
            return video_path
            
        except Exception as e:
            logger.error(f"Video optimization failed: {str(e)}")
            return video_path
    
    async def optimize_audio(self, audio_path: str) -> str:
        """بهینه‌سازی صوت"""
        try:
            # نرمال‌سازی صدا
            output_path = audio_path.rsplit('.', 1)[0] + '_normalized.mp3'
            
            stream = ffmpeg.input(audio_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='libmp3lame',
                audio_bitrate='192k',
                af='loudnorm'  # نرمال‌سازی صدا
            )
            
            await self._run_ffmpeg(stream, overwrite=True)
            
            # جایگزینی اگر موفق بود
            if os.path.exists(output_path):
                os.remove(audio_path)
                return output_path
            
            return audio_path
            
        except Exception as e:
            logger.error(f"Audio optimization failed: {str(e)}")
            return audio_path
    
    async def generate_thumbnail(self, video_path: str) -> Optional[str]:
        """تولید thumbnail از ویدیو"""
        try:
            thumbnail_path = video_path.rsplit('.', 1)[0] + '_thumb.jpg'
            
            # استخراج فریم از وسط ویدیو
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
            time_point = min(duration / 2, 10)  # وسط یا ثانیه 10
            
            stream = ffmpeg.input(video_path, ss=time_point)
            stream = ffmpeg.output(
                stream,
                thumbnail_path,
                vframes=1,
                **{'q:v': 2}  # کیفیت بالا
            )
            
            await self._run_ffmpeg(stream, overwrite=True)
            
            # بهینه‌سازی تصویر
            if os.path.exists(thumbnail_path):
                await self._optimize_thumbnail(thumbnail_path)
                return thumbnail_path
            
            return None
            
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {str(e)}")
            return None
    
    async def _optimize_thumbnail(self, thumb_path: str):
        """بهینه‌سازی thumbnail"""
        try:
            img = Image.open(thumb_path)
            
            # تغییر اندازه اگر بزرگ بود
            max_size = (1280, 720)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # ذخیره با کیفیت بهینه
            img.save(thumb_path, 'JPEG', quality=85, optimize=True)
            
        except Exception as e:
            logger.error(f"Thumbnail optimization failed: {str(e)}")
    
    async def move_to_storage(self, file_path: str, platform: str) -> str:
        """انتقال فایل به محل ذخیره‌سازی نهایی"""
        try:
            # ایجاد نام یکتا
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_hash = await get_file_hash(file_path)
            extension = Path(file_path).suffix
            
            # ساختار دایرکتوری: platform/YYYY/MM/DD/
            date_path = datetime.now().strftime('%Y/%m/%d')
            storage_dir = Path(self.download_dir) / platform / date_path
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            # نام نهایی فایل
            final_name = f"{timestamp}_{file_hash[:8]}{extension}"
            final_path = storage_dir / final_name
            
            # انتقال فایل
            shutil.move(file_path, str(final_path))
            
            return str(final_path)
            
        except Exception as e:
            logger.error(f"Failed to move file to storage: {str(e)}")
            raise
    
    async def _run_ffmpeg(self, stream, overwrite: bool = False):
        """اجرای ffmpeg به صورت async"""
        import asyncio
        
        cmd = ffmpeg.compile(stream, overwrite_output=overwrite)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"FFmpeg failed: {stderr.decode()}")
    
    def get_mime_type(self, file_path: str) -> str:
        """دریافت MIME type فایل"""
        return get_file_type(file_path)
    
    async def get_file_info(self, file_path: str) -> Dict:
        """دریافت اطلاعات کامل فایل"""
        try:
            info = {
                'path': file_path,
                'size': os.path.getsize(file_path),
                'mime_type': self.get_mime_type(file_path),
                'created_at': datetime.fromtimestamp(os.path.getctime(file_path)),
                'hash': await get_file_hash(file_path)
            }
            
            # اطلاعات media
            if info['mime_type'].startswith(('video/', 'audio/')):
                probe = ffmpeg.probe(file_path)
                info['duration'] = float(probe['format'].get('duration', 0))
                info['bitrate'] = int(probe['format'].get('bit_rate', 0))
                
                # اطلاعات ویدیو
                for stream in probe['streams']:
                    if stream['codec_type'] == 'video':
                        info['width'] = stream.get('width')
                        info['height'] = stream.get('height')
                        info['fps'] = eval(stream.get('r_frame_rate', '0/1'))
                        info['codec'] = stream.get('codec_name')
                        break
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get file info: {str(e)}")
            return {'path': file_path, 'error': str(e)}
    
    async def cleanup_temp_files(self, hours: int = 24) -> int:
        """پاکسازی فایل‌های موقت"""
        from ..utils.helpers import cleanup_old_files
        
        count = await cleanup_old_files(self.temp_dir, hours)
        logger.info(f"Cleaned up {count} temporary files")
        
        return count
    
    async def get_storage_stats(self) -> Dict:
        """آمار فضای ذخیره‌سازی"""
        from ..utils.helpers import get_directory_size
        
        total_size = await get_directory_size(self.download_dir)
        temp_size = await get_directory_size(self.temp_dir)
        
        # آمار به تفکیک پلتفرم
        platform_stats = {}
        for platform_dir in Path(self.download_dir).iterdir():
            if platform_dir.is_dir():
                size = await get_directory_size(str(platform_dir))
                platform_stats[platform_dir.name] = size
        
        # فضای دیسک
        stat = os.statvfs(self.download_dir)
        disk_free = stat.f_bavail * stat.f_frsize
        disk_total = stat.f_blocks * stat.f_frsize
        
        return {
            'total_size': total_size,
            'temp_size': temp_size,
            'platform_stats': platform_stats,
            'disk_free': disk_free,
            'disk_total': disk_total,
            'disk_usage_percent': ((disk_total - disk_free) / disk_total) * 100
        }