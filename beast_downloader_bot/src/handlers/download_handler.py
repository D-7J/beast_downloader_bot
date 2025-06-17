import re
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from loguru import logger

from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..database.models import Download, DownloadStatus, SubscriptionType
from ..services.downloader import VideoDownloader
from ..services.validator import URLValidator
from ..utils import messages, keyboards
from ..utils.decorators import track_user, log_action, rate_limit, typing_action
from ..config import subscription_config, download_config
from ..tasks.download_tasks import process_download_task

# پترن‌های URL پشتیبانی شده
URL_PATTERNS = {
    'youtube': re.compile(r'(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)'),
    'instagram': re.compile(r'instagram\.com/(p|reel|tv)/'),
    'twitter': re.compile(r'(twitter\.com|x\.com)/\w+/status/'),
    'tiktok': re.compile(r'tiktok\.com/@[\w.-]+/video/'),
    'facebook': re.compile(r'facebook\.com/.+/videos/'),
}

@track_user
@log_action("download")
@rate_limit(max_calls=30, window=60)
@typing_action
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت URL ارسالی"""
    message = update.message
    url = message.text.strip()
    user_id = update.effective_user.id
    
    # اعتبارسنجی URL
    validator = URLValidator()
    is_valid, platform, clean_url = validator.validate_and_clean(url)
    
    if not is_valid:
        await message.reply_text(
            messages.ERROR_INVALID_URL,
            parse_mode='Markdown'
        )
        return
    
    # بررسی پشتیبانی از پلتفرم
    if platform == 'unknown':
        await message.reply_text(
            messages.ERROR_NOT_SUPPORTED,
            parse_mode='Markdown'
        )
        return
    
    # دریافت اطلاعات کاربر
    db_user = context.user_data.get('db_user')
    
    # بررسی محدودیت‌ها
    can_download, limit_msg, stats = await redis_manager.check_user_limit(
        user_id, db_user.subscription
    )
    
    if not can_download:
        if 'concurrent' in limit_msg:
            await message.reply_text(
                messages.ERROR_CONCURRENT_LIMIT.format(
                    current_concurrent=stats['current_concurrent'],
                    concurrent_limit=stats['concurrent_limit']
                ),
                parse_mode='Markdown',
                reply_markup=keyboards.Keyboards.subscription_plans()
            )
        else:
            await message.reply_text(
                messages.ERROR_DAILY_LIMIT.format(
                    downloads_today=stats['downloads_today'],
                    daily_limit=stats['daily_limit'],
                    size_today=messages.format_file_size(stats['size_today']),
                    reset_time=redis_manager._get_reset_time()
                ),
                parse_mode='Markdown',
                reply_markup=keyboards.Keyboards.subscription_plans()
            )
        return
    
    # افزایش شمارنده دانلود همزمان
    await redis_manager.set_concurrent_download(user_id, increment=True)
    
    try:
        # بررسی کش
        cached_info = await redis_manager.get_cached_video_info(clean_url)
        
        if cached_info:
            logger.info(f"Using cached info for {clean_url}")
            await show_download_options(update, context, cached_info, clean_url, platform)
        else:
            # دریافت اطلاعات ویدیو
            processing_msg = await message.reply_text(
                messages.PROCESSING_VIDEO_INFO,
                reply_to_message_id=message.message_id
            )
            
            # استفاده از downloader service
            downloader = VideoDownloader()
            video_info = await downloader.get_video_info(clean_url, platform)
            
            if not video_info:
                await processing_msg.edit_text(messages.ERROR_DOWNLOAD_FAILED.format(
                    error_code="INFO_EXTRACTION_FAILED"
                ))
                await redis_manager.set_concurrent_download(user_id, increment=False)
                return
            
            # کش کردن اطلاعات
            await redis_manager.cache_video_info(clean_url, video_info, ttl=3600)
            
            # حذف پیام processing
            await processing_msg.delete()
            
            # نمایش گزینه‌های دانلود
            await show_download_options(update, context, video_info, clean_url, platform)
            
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        await message.reply_text(
            messages.ERROR_DOWNLOAD_FAILED.format(error_code="GENERAL_ERROR"),
            parse_mode='Markdown'
        )
        await redis_manager.set_concurrent_download(user_id, increment=False)

async def show_download_options(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    video_info: dict,
    url: str,
    platform: str
):
    """نمایش گزینه‌های دانلود"""
    message = update.message
    user_id = update.effective_user.id
    db_user = context.user_data.get('db_user')
    
    # استخراج اطلاعات ویدیو
    title = video_info.get('title', 'بدون عنوان')[:100]
    duration = video_info.get('duration', 0)
    thumbnail = video_info.get('thumbnail', '')
    uploader = video_info.get('uploader', 'نامشخص')
    view_count = video_info.get('view_count', 0)
    upload_date = video_info.get('upload_date', '')
    
    # بررسی محدودیت مدت زمان
    plan = subscription_config.plans[db_user.subscription.value]
    max_duration = plan.get('max_duration', -1)
    
    if max_duration != -1 and duration > max_duration:
        await message.reply_text(
            messages.ERROR_DURATION_LIMIT.format(
                duration=messages.format_duration(duration),
                max_duration=messages.format_duration(max_duration)
            ),
            parse_mode='Markdown',
            reply_markup=keyboards.Keyboards.subscription_plans()
        )
        await redis_manager.set_concurrent_download(user_id, increment=False)
        return
    
    # ذخیره اطلاعات در context برای استفاده بعدی
    context.user_data[f'video_info_{hash(url) % 1000000}'] = {
        'url': url,
        'platform': platform,
        'title': title,
        'duration': duration,
        'formats': video_info.get('formats', []),
        'thumbnail': thumbnail
    }
    
    # ایجاد متن اطلاعات ویدیو
    info_text = messages.VIDEO_INFO.format(
        title=title,
        duration=messages.format_duration(duration),
        upload_date=upload_date,
        view_count=messages.format_number(view_count),
        uploader=uploader,
        platform=platform.title()
    )
    
    # ایجاد کیبورد کیفیت‌ها
    formats = video_info.get('formats', [])
    keyboard = keyboards.Keyboards.video_quality_buttons(formats, url)
    
    # ارسال با تصویر thumbnail
    try:
        if thumbnail:
            await message.reply_photo(
                photo=thumbnail,
                caption=info_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await message.reply_text(
                info_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    except TelegramError:
        # اگر ارسال عکس موفق نبود، فقط متن
        await message.reply_text(
            info_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # کاهش شمارنده همزمان (چون هنوز دانلود شروع نشده)
    await redis_manager.set_concurrent_download(user_id, increment=False)

async def handle_download_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback_data: str
):
    """مدیریت callback دانلود"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # پارس callback_data
    parts = callback_data.split('_')
    download_type = parts[1]  # 'v' برای ویدیو، 'a' برای صوت
    
    if download_type == 'v':
        format_id = parts[2]
        url_hash = parts[3]
    else:
        url_hash = parts[2]
        format_id = None
    
    # دریافت اطلاعات ویدیو از context
    video_info = context.user_data.get(f'video_info_{url_hash}')
    if not video_info:
        await query.answer("⚠️ اطلاعات ویدیو منقضی شده. لطفاً دوباره لینک را ارسال کنید.", show_alert=True)
        return
    
    # بررسی محدودیت‌های کاربر
    db_user = await mongo_manager.get_user(user_id)
    can_download, limit_msg, stats = await redis_manager.check_user_limit(
        user_id, db_user.subscription
    )
    
    if not can_download:
        await query.answer(limit_msg, show_alert=True)
        return
    
    # افزایش شمارنده همزمان
    await redis_manager.set_concurrent_download(user_id, increment=True)
    
    # ایجاد رکورد دانلود در دیتابیس
    download = Download(
        user_id=user_id,
        url=video_info['url'],
        platform=video_info['platform'],
        title=video_info['title'],
        duration=video_info.get('duration', 0),
        format='mp3' if download_type == 'a' else 'mp4',
        quality=format_id,
        thumbnail_url=video_info.get('thumbnail')
    )
    
    download = await mongo_manager.create_download(download)
    download_id = str(download._id)
    
    # ارسال پیام شروع دانلود
    progress_text = messages.DOWNLOADING_VIDEO.format(
        progress="🔄 در حال شروع..."
    )
    
    progress_message = await query.message.reply_text(
        progress_text,
        reply_markup=keyboards.Keyboards.download_actions(download_id),
        parse_mode='Markdown'
    )
    
    # ذخیره message_id برای update
    context.user_data[f'progress_msg_{download_id}'] = progress_message.message_id
    
    # ارسال به صف Celery
    queue_position = await redis_manager.add_to_download_queue(user_id, {
        'download_id': download_id,
        'user_id': user_id,
        'subscription': db_user.subscription.value
    })
    
    # اجرای task
    task = process_download_task.apply_async(
        args=[download_id, format_id, download_type == 'a'],
        priority=get_priority_by_subscription(db_user.subscription)
    )
    
    # ذخیره task_id
    download.task_id = task.id
    await mongo_manager.update_download(download)
    
    # نمایش موقعیت در صف
    if queue_position > 1:
        wait_time = queue_position * 30  # تخمین 30 ثانیه برای هر دانلود
        await progress_message.edit_text(
            messages.DOWNLOAD_IN_QUEUE.format(
                position=queue_position,
                wait_time=messages.format_duration(wait_time)
            ),
            reply_markup=keyboards.Keyboards.download_actions(download_id),
            parse_mode='Markdown'
        )

async def update_download_progress(
    bot,
    user_id: int,
    download_id: str,
    progress_data: dict
):
    """بروزرسانی پیشرفت دانلود"""
    # این تابع از Celery فراخوانی می‌شود
    try:
        # دریافت message_id از Redis
        session = await redis_manager.get_user_session(user_id)
        if not session:
            return
        
        message_id = session.get(f'progress_msg_{download_id}')
        if not message_id:
            return
        
        # ایجاد متن پیشرفت
        progress_text = messages.DOWNLOAD_PROGRESS.format(
            progress=progress_data.get('percent', 0),
            progress_bar=messages.create_progress_bar(progress_data.get('percent', 0)),
            downloaded=messages.format_file_size(progress_data.get('downloaded_bytes', 0)),
            total_size=messages.format_file_size(progress_data.get('total_bytes', 0)),
            speed=progress_data.get('speed', 'نامشخص'),
            eta=messages.format_duration(progress_data.get('eta', 0))
        )
        
        # ارسال update
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=progress_text,
            reply_markup=keyboards.Keyboards.download_actions(download_id),
            parse_mode='Markdown'
        )
        
    except TelegramError as e:
        if "message is not modified" not in str(e):
            logger.error(f"Error updating progress: {str(e)}")

async def handle_download_complete(
    bot,
    user_id: int,
    download_id: str,
    file_path: str,
    file_size: int
):
    """مدیریت اتمام دانلود"""
    try:
        # بروزرسانی رکورد دانلود
        download = await mongo_manager.get_download(download_id)
        download.status = DownloadStatus.COMPLETED
        download.file_path = file_path
        download.file_size = file_size
        download.completed_at = datetime.now()
        await mongo_manager.update_download(download)
        
        # کاهش شمارنده همزمان
        await redis_manager.set_concurrent_download(user_id, increment=False)
        
        # افزایش شمارنده روزانه
        await redis_manager.increment_user_downloads(user_id, file_size)
        
        # ارسال فایل
        caption = f"✅ **{download.title}**\n\n"
        caption += f"📦 حجم: {messages.format_file_size(file_size)}\n"
        caption += f"⏱ مدت دانلود: {download.download_time} ثانیه\n"
        caption += f"🌐 منبع: {download.platform}"
        
        # ارسال بر اساس نوع فایل
        if download.format == 'mp3':
            await bot.send_audio(
                chat_id=user_id,
                audio=open(file_path, 'rb'),
                caption=caption,
                parse_mode='Markdown',
                title=download.title,
                duration=download.duration
            )
        else:
            await bot.send_video(
                chat_id=user_id,
                video=open(file_path, 'rb'),
                caption=caption,
                parse_mode='Markdown',
                duration=download.duration,
                supports_streaming=True
            )
        
        # حذف پیام progress
        session = await redis_manager.get_user_session(user_id)
        if session:
            message_id = session.get(f'progress_msg_{download_id}')
            if message_id:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=message_id)
                except:
                    pass
        
        # پیام موفقیت
        await bot.send_message(
            chat_id=user_id,
            text=messages.DOWNLOAD_COMPLETED,
            reply_markup=keyboards.Keyboards.main_menu()
        )
        
    except Exception as e:
        logger.error(f"Error in download complete handler: {str(e)}")
        await handle_download_error(bot, user_id, download_id, str(e))

async def handle_download_error(
    bot,
    user_id: int,
    download_id: str,
    error: str
):
    """مدیریت خطای دانلود"""
    try:
        # بروزرسانی رکورد
        download = await mongo_manager.get_download(download_id)
        download.status = DownloadStatus.FAILED
        download.error_message = error
        download.completed_at = datetime.now()
        await mongo_manager.update_download(download)
        
        # کاهش شمارنده همزمان
        await redis_manager.set_concurrent_download(user_id, increment=False)
        
        # ارسال پیام خطا
        error_code = "DOWNLOAD_FAILED"
        if "private" in error.lower():
            error_code = "PRIVATE_CONTENT"
        elif "copyright" in error.lower():
            error_code = "COPYRIGHT"
        
        await bot.send_message(
            chat_id=user_id,
            text=messages.ERROR_DOWNLOAD_FAILED.format(error_code=error_code),
            parse_mode='Markdown',
            reply_markup=keyboards.Keyboards.main_menu()
        )
        
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}")

def get_priority_by_subscription(subscription: SubscriptionType) -> int:
    """تعیین اولویت بر اساس اشتراک"""
    priorities = {
        SubscriptionType.GOLD: 1,
        SubscriptionType.SILVER: 2,
        SubscriptionType.BRONZE: 3,
        SubscriptionType.FREE: 4
    }
    return priorities.get(subscription, 4)