import os
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import ffmpeg
from loguru import logger

from ..config import download_config
from ..utils.helpers import sanitize_filename, get_file_type

class MediaConverter:
    """سرویس تبدیل فرمت فایل‌های مدیا"""
    
    def __init__(self):
        self.ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.temp_dir = download_config.temp_dir
        
    async def convert_to_mp3(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        bitrate: str = "192k",
        metadata: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """تبدیل فایل ویدیو/صوتی به MP3"""
        try:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
            
            # تعیین مسیر خروجی
            if not output_path:
                base_name = Path(input_path).stem
                output_path = os.path.join(
                    self.temp_dir,
                    f"{sanitize_filename(base_name)}.mp3"
                )
            
            # ایجاد stream ffmpeg
            stream = ffmpeg.input(input_path)
            
            # تنظیمات صوتی
            audio_settings = {
                'acodec': 'libmp3lame',
                'audio_bitrate': bitrate,
                'ar': 44100,  # Sample rate
                'ac': 2,      # Stereo
            }
            
            # اضافه کردن metadata
            if metadata:
                for key, value in metadata.items():
                    audio_settings[f'metadata:{key}'] = value
            
            # اعمال تنظیمات
            stream = ffmpeg.output(stream, output_path, **audio_settings)
            
            # اجرای تبدیل
            await self._run_ffmpeg_async(stream, overwrite=True)
            
            if os.path.exists(output_path):
                logger.info(f"Successfully converted to MP3: {output_path}")
                return output_path
            else:
                raise Exception("Output file was not created")
                
        except Exception as e:
            logger.error(f"Error converting to MP3: {str(e)}")
            return None
    
    async def convert_video_format(
        self,
        input_path: str,
        output_format: str,
        output_path: Optional[str] = None,
        quality_preset: str = "medium",
        target_size: Optional[int] = None
    ) -> Optional[str]:
        """تبدیل فرمت ویدیو"""
        try:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
            
            # تعیین مسیر خروجی
            if not output_path:
                base_name = Path(input_path).stem
                output_path = os.path.join(
                    self.temp_dir,
                    f"{sanitize_filename(base_name)}.{output_format}"
                )
            
            # دریافت اطلاعات ویدیو
            probe = ffmpeg.probe(input_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            
            # ایجاد stream
            stream = ffmpeg.input(input_path)
            
            # تنظیمات بر اساس فرمت خروجی
            if output_format == "mp4":
                video_settings = {
                    'vcodec': 'libx264',
                    'acodec': 'aac',
                    'preset': quality_preset,
                    'crf': 23,
                    'movflags': '+faststart'  # برای streaming
                }
            elif output_format == "webm":
                video_settings = {
                    'vcodec': 'libvpx-vp9',
                    'acodec': 'libopus',
                    'crf': 30,
                    'b:v': 0
                }
            elif output_format == "avi":
                video_settings = {
                    'vcodec': 'libxvid',
                    'acodec': 'mp3',
                    'vtag': 'xvid'
                }
            else:
                # فرمت‌های دیگر
                video_settings = {}
            
            # محاسبه bitrate برای target size
            if target_size:
                duration = float(probe['format']['duration'])
                target_bitrate = self._calculate_bitrate(target_size, duration)
                video_settings['video_bitrate'] = target_bitrate
            
            # اعمال تنظیمات
            stream = ffmpeg.output(stream, output_path, **video_settings)
            
            # اجرای تبدیل
            await self._run_ffmpeg_async(stream, overwrite=True)
            
            if os.path.exists(output_path):
                logger.info(f"Successfully converted video to {output_format}: {output_path}")
                return output_path
            else:
                raise Exception("Output file was not created")
                
        except Exception as e:
            logger.error(f"Error converting video: {str(e)}")
            return None
    
    async def extract_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        audio_format: str = "mp3"
    ) -> Optional[str]:
        """استخراج صدا از ویدیو"""
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # تعیین مسیر خروجی
            if not output_path:
                base_name = Path(video_path).stem
                output_path = os.path.join(
                    self.temp_dir,
                    f"{sanitize_filename(base_name)}_audio.{audio_format}"
                )
            
            # ایجاد stream
            stream = ffmpeg.input(video_path)
            
            # انتخاب codec بر اساس فرمت
            if audio_format == "mp3":
                audio_codec = "libmp3lame"
            elif audio_format == "aac":
                audio_codec = "aac"
            elif audio_format == "opus":
                audio_codec = "libopus"
            else:
                audio_codec = "copy"  # کپی بدون تغییر
            
            # استخراج صدا
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec=audio_codec,
                audio_bitrate='192k',
                vn=None  # no video
            )
            
            await self._run_ffmpeg_async(stream, overwrite=True)
            
            if os.path.exists(output_path):
                logger.info(f"Successfully extracted audio: {output_path}")
                return output_path
            else:
                raise Exception("Audio file was not created")
                
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            return None
    
    async def compress_video(
        self,
        input_path: str,
        target_size_mb: int,
        output_path: Optional[str] = None,
        maintain_quality: bool = True
    ) -> Optional[str]:
        """فشرده‌سازی ویدیو به حجم مشخص"""
        try:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
            
            # تعیین مسیر خروجی
            if not output_path:
                base_name = Path(input_path).stem
                extension = Path(input_path).suffix
                output_path = os.path.join(
                    self.temp_dir,
                    f"{sanitize_filename(base_name)}_compressed{extension}"
                )
            
            # دریافت اطلاعات ویدیو
            probe = ffmpeg.probe(input_path)
            duration = float(probe['format']['duration'])
            
            # محاسبه bitrate هدف
            target_size_bits = target_size_mb * 8 * 1024 * 1024
            target_bitrate = int(target_size_bits / duration)
            
            # کم کردن 10% برای اطمینان
            target_bitrate = int(target_bitrate * 0.9)
            
            # ایجاد stream
            stream = ffmpeg.input(input_path)
            
            if maintain_quality:
                # Two-pass encoding برای کیفیت بهتر
                # Pass 1
                pass1 = ffmpeg.output(
                    stream,
                    '/dev/null' if os.name != 'nt' else 'NUL',
                    vcodec='libx264',
                    preset='slow',
                    video_bitrate=target_bitrate,
                    pass_=1,
                    an=None,  # no audio in pass 1
                    f='null'
                )
                await self._run_ffmpeg_async(pass1, overwrite=True)
                
                # Pass 2
                stream = ffmpeg.input(input_path)
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    vcodec='libx264',
                    preset='slow',
                    video_bitrate=target_bitrate,
                    pass_=2,
                    acodec='aac',
                    audio_bitrate='128k'
                )
            else:
                # Single pass - سریع‌تر ولی کیفیت کمتر
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    vcodec='libx264',
                    preset='fast',
                    video_bitrate=target_bitrate,
                    acodec='aac',
                    audio_bitrate='128k'
                )
            
            await self._run_ffmpeg_async(stream, overwrite=True)
            
            # بررسی حجم نهایی
            if os.path.exists(output_path):
                final_size = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(f"Compressed video from {os.path.getsize(input_path)/(1024*1024):.1f}MB to {final_size:.1f}MB")
                
                if final_size > target_size_mb:
                    logger.warning(f"Compressed file ({final_size:.1f}MB) is larger than target ({target_size_mb}MB)")
                
                return output_path
            else:
                raise Exception("Compressed file was not created")
                
        except Exception as e:
            logger.error(f"Error compressing video: {str(e)}")
            return None
    
    async def add_watermark(
        self,
        input_path: str,
        watermark_path: str,
        output_path: Optional[str] = None,
        position: str = "bottom-right",
        opacity: float = 0.5
    ) -> Optional[str]:
        """اضافه کردن واترمارک به ویدیو"""
        try:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
            if not os.path.exists(watermark_path):
                raise FileNotFoundError(f"Watermark file not found: {watermark_path}")
            
            # تعیین مسیر خروجی
            if not output_path:
                base_name = Path(input_path).stem
                extension = Path(input_path).suffix
                output_path = os.path.join(
                    self.temp_dir,
                    f"{sanitize_filename(base_name)}_watermarked{extension}"
                )
            
            # تعیین موقعیت واترمارک
            position_map = {
                "top-left": "10:10",
                "top-right": "main_w-overlay_w-10:10",
                "bottom-left": "10:main_h-overlay_h-10",
                "bottom-right": "main_w-overlay_w-10:main_h-overlay_h-10",
                "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
            }
            overlay_position = position_map.get(position, position_map["bottom-right"])
            
            # ایجاد streams
            input_stream = ffmpeg.input(input_path)
            watermark_stream = ffmpeg.input(watermark_path)
            
            # اعمال واترمارک با opacity
            stream = ffmpeg.filter(
                [input_stream, watermark_stream],
                'overlay',
                overlay_position,
                format='auto',
                alpha='straight'
            )
            
            # تنظیمات خروجی
            stream = ffmpeg.output(
                stream,
                output_path,
                vcodec='libx264',
                acodec='copy',
                preset='fast'
            )
            
            await self._run_ffmpeg_async(stream, overwrite=True)
            
            if os.path.exists(output_path):
                logger.info(f"Successfully added watermark: {output_path}")
                return output_path
            else:
                raise Exception("Watermarked file was not created")
                
        except Exception as e:
            logger.error(f"Error adding watermark: {str(e)}")
            return None
    
    async def merge_videos(
        self,
        video_paths: List[str],
        output_path: Optional[str] = None,
        transition: Optional[str] = None
    ) -> Optional[str]:
        """ادغام چند ویدیو"""
        try:
            if not video_paths or len(video_paths) < 2:
                raise ValueError("At least 2 videos required for merging")
            
            # بررسی وجود فایل‌ها
            for path in video_paths:
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Video file not found: {path}")
            
            # تعیین مسیر خروجی
            if not output_path:
                output_path = os.path.join(
                    self.temp_dir,
                    f"merged_{int(asyncio.get_event_loop().time())}.mp4"
                )
            
            # ایجاد فایل لیست برای concat
            list_file = os.path.join(self.temp_dir, f"merge_list_{id(video_paths)}.txt")
            with open(list_file, 'w') as f:
                for path in video_paths:
                    f.write(f"file '{os.path.abspath(path)}'\n")
            
            # استفاده از concat demuxer
            stream = ffmpeg.input(list_file, format='concat', safe=0)
            stream = ffmpeg.output(
                stream,
                output_path,
                c='copy'  # کپی بدون encoding مجدد
            )
            
            await self._run_ffmpeg_async(stream, overwrite=True)
            
            # حذف فایل موقت
            os.remove(list_file)
            
            if os.path.exists(output_path):
                logger.info(f"Successfully merged {len(video_paths)} videos: {output_path}")
                return output_path
            else:
                raise Exception("Merged file was not created")
                
        except Exception as e:
            logger.error(f"Error merging videos: {str(e)}")
            return None
    
    async def create_thumbnail(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        time_position: Optional[float] = None,
        size: tuple = (320, 180)
    ) -> Optional[str]:
        """ایجاد thumbnail از ویدیو"""
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # تعیین مسیر خروجی
            if not output_path:
                base_name = Path(video_path).stem
                output_path = os.path.join(
                    self.temp_dir,
                    f"{sanitize_filename(base_name)}_thumb.jpg"
                )
            
            # تعیین زمان برای عکس
            if time_position is None:
                # دریافت مدت ویدیو
                probe = ffmpeg.probe(video_path)
                duration = float(probe['format']['duration'])
                time_position = min(duration * 0.3, 10)  # 30% یا حداکثر 10 ثانیه
            
            # ایجاد thumbnail
            stream = ffmpeg.input(video_path, ss=time_position)
            stream = ffmpeg.filter(stream, 'scale', size[0], size[1])
            stream = ffmpeg.output(
                stream,
                output_path,
                vframes=1,
                format='image2',
                vcodec='mjpeg'
            )
            
            await self._run_ffmpeg_async(stream, overwrite=True)
            
            if os.path.exists(output_path):
                logger.info(f"Successfully created thumbnail: {output_path}")
                return output_path
            else:
                raise Exception("Thumbnail was not created")
                
        except Exception as e:
            logger.error(f"Error creating thumbnail: {str(e)}")
            return None
    
    def _calculate_bitrate(self, target_size_mb: int, duration_seconds: float) -> str:
        """محاسبه bitrate برای رسیدن به حجم مشخص"""
        # تبدیل MB به bits
        target_bits = target_size_mb * 8 * 1024 * 1024
        
        # محاسبه bitrate (با در نظر گرفتن audio)
        video_bitrate = int((target_bits / duration_seconds) * 0.9)  # 90% برای ویدیو
        
        # حداقل و حداکثر bitrate
        video_bitrate = max(500000, min(video_bitrate, 50000000))  # 500kbps - 50Mbps
        
        return f"{video_bitrate}"
    
    async def _run_ffmpeg_async(self, stream, overwrite: bool = False):
        """اجرای ffmpeg به صورت async"""
        try:
            # کامپایل دستور
            cmd = ffmpeg.compile(stream, overwrite_output=overwrite)
            
            # اجرا با asyncio
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"FFmpeg failed with code {process.returncode}: {error_msg}")
                
        except Exception as e:
            logger.error(f"FFmpeg execution error: {str(e)}")
            raise
    
    async def get_media_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """دریافت اطلاعات کامل فایل مدیا"""
        try:
            probe = ffmpeg.probe(file_path)
            
            info = {
                'format': probe['format']['format_name'],
                'duration': float(probe['format'].get('duration', 0)),
                'size': int(probe['format'].get('size', 0)),
                'bitrate': int(probe['format'].get('bit_rate', 0)),
                'streams': []
            }
            
            for stream in probe['streams']:
                stream_info = {
                    'type': stream['codec_type'],
                    'codec': stream.get('codec_name'),
                }
                
                if stream['codec_type'] == 'video':
                    stream_info.update({
                        'width': stream.get('width', 0),
                        'height': stream.get('height', 0),
                        'fps': eval(stream.get('r_frame_rate', '0/1')),
                        'bitrate': int(stream.get('bit_rate', 0))
                    })
                elif stream['codec_type'] == 'audio':
                    stream_info.update({
                        'sample_rate': int(stream.get('sample_rate', 0)),
                        'channels': stream.get('channels', 0),
                        'bitrate': int(stream.get('bit_rate', 0))
                    })
                
                info['streams'].append(stream_info)
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting media info: {str(e)}")
            return None