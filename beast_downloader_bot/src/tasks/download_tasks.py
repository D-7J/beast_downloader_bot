import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from .celery_app import celery_app
from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..database.models import Download, DownloadStatus
from ..services.downloader import VideoDownloader
from ..services.file_manager import FileManager
from ..handlers.download_handler import update_download_progress, handle_download_complete, handle_download_error
from ..config import bot_config

class CallbackTask(Task):
    """Task با callback برای گزارش پیشرفت"""
    
    def __init__(self):
        self.download_id = None
        self.user_id = None
        self.bot = None
    
    async def progress_callback(self, progress_data: dict):
        """Callback برای گزارش پیشرفت"""
        if self.download_id and self.user_id and self.bot:
            await redis_manager.publish_download_update(
                self.user_id,
                self.download_id,
                progress_data
            )
            
            # بروزرسانی UI هر 2 ثانیه
            current_time = datetime.now().timestamp()
            last_update_key = f"last_update:{self.download_id}"
            last_update = await redis_manager.client.get(last_update_key)
            
            if not last_update or current_time - float(last_update) > 2:
                await update_download_progress(
                    self.bot,
                    self.user_id,
                    self.download_id,
                    progress_data
                )
                await redis_manager.client.setex(last_update_key, 10, str(current_time))

@celery_app.task(
    bind=True,
    base=CallbackTask,
    name='tasks.download_tasks.process_download_task',
    max_retries=3,
    default_retry_delay=60
)
def process_download_task(
    self,
    download_id: str,
    format_id: Optional[str] = None,
    audio_only: bool = False
) -> Dict[str, Any]:
    """
    وظیفه اصلی پردازش دانلود
    """
    # تنظیمات اولیه
    self.download_id = download_id
    loop = None
    
    try:
        # ایجاد event loop جدید برای Celery
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # اجرای async function
        result = loop.run_until_complete(
            _process_download_async(
                self,
                download_id,
                format_id,
                audio_only
            )
        )
        
        return result
        
    except SoftTimeLimitExceeded:
        logger.error(f"Download {download_id} exceeded time limit")
        if loop:
            loop.run_until_complete(
                _handle_download_failure(download_id, "TIMEOUT", "زمان دانلود بیش از حد مجاز")
            )
        raise
        
    except Exception as e:
        logger.error(f"Download {download_id} failed: {str(e)}")
        if loop:
            loop.run_until_complete(
                _handle_download_failure(download_id, "ERROR", str(e))
            )
        
        # Retry logic
        raise self.retry(exc=e)
        
    finally:
        if loop:
            loop.close()

async def _process_download_async(
    task: CallbackTask,
    download_id: str,
    format_id: Optional[str],
    audio_only: bool
) -> Dict[str, Any]:
    """
    پردازش async دانلود
    """
    # دریافت اطلاعات دانلود
    download = await mongo_manager.get_download(download_id)
    if not download:
        raise ValueError(f"Download {download_id} not found")
    
    # تنظیم user_id برای callback
    task.user_id = download.user_id
    
    # دریافت bot instance (در production از bot اصلی استفاده کنید)
    from telegram import Bot
    task.bot = Bot(token=bot_config.token)
    
    # بروزرسانی وضعیت
    download.status = DownloadStatus.PROCESSING
    download.started_at = datetime.now()
    await mongo_manager.update_download(download)
    
    # افزایش شمارنده همزمان
    await redis_manager.set_concurrent_download(download.user_id, increment=True)
    
    try:
        # ایجاد downloader
        downloader = VideoDownloader()
        
        # تابع progress callback
        async def progress_wrapper(data):
            await task.progress_callback(data)
        
        # دانلود
        if audio_only:
            result = await downloader.download_audio(
                url=download.url,
                progress_callback=progress_wrapper,
                platform=download.platform,
                quality=download_config.audio_quality
            )
        else:
            result = await downloader.download_video(
                url=download.url,
                format_id=format_id,
                progress_callback=progress_wrapper,
                platform=download.platform
            )
        
        if not result or not result.get('filepath'):
            raise Exception("Download failed - no file returned")
        
        # بررسی حجم فایل
        file_size = result.get('filesize', 0)
        user = await mongo_manager.get_user(download.user_id)
        max_file_size = bot_config.subscription_config.plans[user.subscription.value]['max_file_size']
        
        if file_size > max_file_size:
            os.remove(result['filepath'])
            raise Exception(f"File too large: {file_size} > {max_file_size}")
        
        # مدیریت فایل
        file_manager = FileManager()
        final_path = await file_manager.process_downloaded_file(
            result['filepath'],
            download.platform,
            download.format
        )
        
        # بروزرسانی اطلاعات دانلود
        download.file_path = final_path
        download.file_size = file_size
        download.status = DownloadStatus.COMPLETED
        download.completed_at = datetime.now()
        download.metadata.update({
            'file_hash': result.get('file_hash'),
            'final_format': result.get('format'),
            'download_duration': (download.completed_at - download.started_at).total_seconds()
        })
        
        await mongo_manager.update_download(download)
        
        # کش لینک دانلود
        await redis_manager.cache_download_link(
            download_id,
            {
                'file_path': final_path,
                'file_size': file_size,
                'mime_type': file_manager.get_mime_type(final_path)
            },
            ttl=3600  # 1 ساعت
        )
        
        # ارسال فایل به کاربر
        await handle_download_complete(
            task.bot,
            download.user_id,
            download_id,
            final_path,
            file_size
        )
        
        # آمار
        await redis_manager.increment_platform_stats(download.platform)
        
        return {
            'status': 'success',
            'download_id': download_id,
            'file_path': final_path,
            'file_size': file_size,
            'duration': (download.completed_at - download.started_at).total_seconds()
        }
        
    except Exception as e:
        logger.error(f"Error in download process: {str(e)}")
        await _handle_download_failure(download_id, "PROCESS_ERROR", str(e))
        raise
        
    finally:
        # کاهش شمارنده همزمان
        await redis_manager.set_concurrent_download(download.user_id, increment=False)

async def _handle_download_failure(
    download_id: str,
    error_code: str,
    error_message: str
):
    """
    مدیریت شکست دانلود
    """
    download = await mongo_manager.get_download(download_id)
    if download:
        download.status = DownloadStatus.FAILED
        download.error_message = f"{error_code}: {error_message}"
        download.completed_at = datetime.now()
        await mongo_manager.update_download(download)
        
        # اطلاع به کاربر
        from telegram import Bot
        bot = Bot(token=bot_config.token)
        await handle_download_error(
            bot,
            download.user_id,
            download_id,
            error_message
        )

@celery_app.task(
    name='tasks.download_tasks.retry_failed_downloads',
    max_retries=1
)
def retry_failed_downloads():
    """
    تلاش مجدد برای دانلودهای ناموفق
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_retry_failed_downloads_async())
        return result
    finally:
        loop.close()

async def _retry_failed_downloads_async():
    """
    پردازش async تلاش مجدد
    """
    # دریافت دانلودهای ناموفق اخیر
    failed_downloads = await mongo_manager.get_recent_failed_downloads(hours=1)
    
    retried_count = 0
    for download in failed_downloads:
        # بررسی تعداد تلاش‌ها
        retry_count = download.metadata.get('retry_count', 0)
        if retry_count >= 3:
            continue
        
        # بروزرسانی تعداد تلاش
        download.metadata['retry_count'] = retry_count + 1
        download.status = DownloadStatus.PENDING
        download.error_message = None
        await mongo_manager.update_download(download)
        
        # ارسال مجدد به صف
        process_download_task.apply_async(
            args=[str(download._id), download.quality, download.format == 'mp3'],
            priority=5
        )
        
        retried_count += 1
    
    logger.info(f"Retried {retried_count} failed downloads")
    return {'retried_count': retried_count}

@celery_app.task(
    name='tasks.download_tasks.cancel_download',
    max_retries=0
)
def cancel_download(download_id: str, user_id: int):
    """
    لغو دانلود
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _cancel_download_async(download_id, user_id)
        )
        return result
    finally:
        loop.close()

async def _cancel_download_async(download_id: str, user_id: int):
    """
    پردازش async لغو دانلود
    """
    download = await mongo_manager.get_download(download_id)
    
    if not download or download.user_id != user_id:
        return {'status': 'error', 'message': 'Download not found'}
    
    if download.status not in [DownloadStatus.PENDING, DownloadStatus.PROCESSING]:
        return {'status': 'error', 'message': 'Cannot cancel completed download'}
    
    # بروزرسانی وضعیت
    download.status = DownloadStatus.CANCELLED
    download.completed_at = datetime.now()
    await mongo_manager.update_download(download)
    
    # حذف از صف
    # در اینجا باید task را از Celery cancel کنید
    if download.task_id:
        celery_app.control.revoke(download.task_id, terminate=True)
    
    # کاهش شمارنده همزمان
    await redis_manager.set_concurrent_download(user_id, increment=False)
    
    # حذف فایل‌های موقت
    if download.file_path and os.path.exists(download.file_path):
        try:
            os.remove(download.file_path)
        except:
            pass
    
    return {'status': 'success', 'message': 'Download cancelled'}