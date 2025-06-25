import logging
import os
import tempfile
import asyncio
from typing import Optional, Tuple
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode, FileSizeLimit

from database import (
    get_user_subscription,
    record_download,
    get_user_downloads
)
from config import PLAN_LIMITS, SubscriptionPlans
from utils.helpers import format_size, get_readable_time, format_timedelta
from utils.downloader import Downloader, DownloadError
from utils.ffmpeg import process_video

# Configure logging
logger = logging.getLogger(__name__)


class DownloadManager:
    """Manages file downloads with subscription-based restrictions"""
    
    def __init__(self, context):
        self.context = context
        self.downloader = Downloader()
        self.active_downloads = {}
    
    async def handle_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming download requests"""
        user = update.effective_user
        message = update.message or update.callback_query.message
        
        # Check if user sent a URL
        if not update.message or not update.message.text:
            await message.reply_text(
                "❌ لطفا یک لینک معتبر ارسال کنید.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        url = update.message.text.strip()
        
        # Check if URL is valid
        if not self._is_valid_url(url):
            await message.reply_text(
                "❌ لینک ارسال شده معتبر نیست. لطفا یک لینک معتبر ارسال کنید.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check user's subscription status
        db = context.bot_data["db"]
        subscription = get_user_subscription(db, user.id)
        
        if not subscription or not subscription.is_active:
            await message.reply_text(
                "❌ اشتراک شما فعال نیست. لطفا برای دانلود فایل، اشتراک تهیه کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 خرید اشتراک", callback_data="buy_plan")]
                ])
            )
            return
        
        # Check daily download limit
        plan_limits = PLAN_LIMITS.get(subscription.plan, {})
        if (subscription.daily_downloads_used >= plan_limits.get("daily_downloads", 0) and
                subscription.plan != SubscriptionPlans.GOLD):
            await message.reply_text(
                "❌ تعداد دانلود روزانه شما به پایان رسیده است.\n"
                "لطفا اشتراک خود را ارتقا دهید یا فردا مجددا تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 ارتقای اشتراک", callback_data="buy_plan")]
                ])
            )
            return
        
        # Get available formats
        try:
            loading_msg = await message.reply_text("🔍 در حال دریافت اطلاعات فایل...")
            
            # Get available formats
            formats = await self.downloader.get_available_formats(url)
            
            if not formats:
                await loading_msg.edit_text(
                    "❌ امکان دانلود این لینک وجود ندارد. لطفا لینک دیگری ارسال کنید."
                )
                return
            
            # Filter formats based on subscription plan
            allowed_formats = self._filter_allowed_formats(formats, subscription.plan)
            
            if not allowed_formats:
                await loading_msg.edit_text(
                    "❌ هیچ فرمت مجازی برای اشتراک فعلی شما یافت نشد.\n"
                    "لطفا اشتراک خود را ارتقا دهید.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛒 ارتقای اشتراک", callback_data="buy_plan")]
                    ])
                )
                return
            
            # Prepare format selection keyboard
            keyboard = []
            for fmt in allowed_formats[:10]:  # Show max 10 formats
                quality = fmt.get('resolution', fmt.get('ext', 'N/A'))
                size = format_size(fmt.get('filesize', 0) or fmt.get('filesize_approx', 0))
                text = f"🎬 {quality} ({size})"
                callback_data = f"dl:{url}:{fmt['format_id']}"
                keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
            
            # Add cancel button
            keyboard.append([
                InlineKeyboardButton("❌ انصراف", callback_data="cancel_download")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading_msg.edit_text(
                "🎬 لطفا کیفیت مورد نظر را انتخاب کنید:",
                reply_markup=reply_markup
            )
            
        except DownloadError as e:
            logger.error(f"Download error: {str(e)}")
            error_msg = "❌ خطا در دریافت اطلاعات فایل. لطفا دوباره امتحان کنید."
            if loading_msg:
                await loading_msg.edit_text(error_msg)
            else:
                await message.reply_text(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            error_msg = "❌ خطای ناشناخته‌ای رخ داد. لطفا دوباره امتحان کنید."
            if loading_msg:
                await loading_msg.edit_text(error_msg)
            else:
                await message.reply_text(error_msg)
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start download with selected format"""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data
        _, url, format_id = query.data.split(":", 2)
        
        user = update.effective_user
        message = query.message
        
        # Check user's subscription status
        db = context.bot_data["db"]
        subscription = get_user_subscription(db, user.id)
        
        if not subscription or not subscription.is_active:
            await message.edit_text(
                "❌ اشتراک شما منقضی شده است. لطفا برای دانلود فایل، اشتراک تهیه کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 خرید اشتراک", callback_data="buy_plan")]
                ])
            )
            return
        
        # Get format info
        try:
            formats = await self.downloader.get_available_formats(url)
            selected_format = next((f for f in formats if f['format_id'] == format_id), None)
            
            if not selected_format:
                await message.edit_text("❌ فرمت انتخابی یافت نشد. لطفا دوباره تلاش کنید.")
                return
            
            # Check file size limit
            file_size = selected_format.get('filesize', 0) or selected_format.get('filesize_approx', 0)
            plan_limits = PLAN_LIMITS.get(subscription.plan, {})
            max_size = plan_limits.get("max_file_size", 0)
            
            if file_size > max_size:
                await message.edit_text(
                    f"❌ حجم فایل ({format_size(file_size)}) بیشتر از حد مجاز "
                    f"({format_size(max_size)}) برای اشتراک فعلی شما است.\n\n"
                    "لطفا اشتراک خود را ارتقا دهید.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛒 ارتقای اشتراک", callback_data="buy_plan")]
                    ])
                )
                return
            
            # Update download status
            status_msg = await message.edit_text("⏳ در حال آماده‌سازی دانلود...")
            
            # Create temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Start download
                download_task = asyncio.create_task(
                    self._download_file(url, format_id, temp_dir, status_msg, user.id)
                )
                
                # Store download task
                self.active_downloads[user.id] = {
                    'task': download_task,
                    'start_time': datetime.now(),
                    'status_msg': status_msg,
                    'file_size': file_size
                }
                
                try:
                    # Wait for download to complete
                    output_path = await download_task
                    
                    # Record download in database
                    file_name = os.path.basename(output_path)
                    record_download(
                        db=db,
                        user_id=user.id,
                        file_url=url,
                        file_name=file_name,
                        file_size=file_size
                    )
                    
                    # Send file to user
                    await self._send_file(user.id, output_path, status_msg)
                    
                except asyncio.CancelledError:
                    await status_msg.edit_text("❌ دانلود لغو شد.")
                except Exception as e:
                    logger.error(f"Download failed: {str(e)}", exc_info=True)
                    await status_msg.edit_text(
                        f"❌ خطا در دانلود فایل: {str(e)}"
                    )
                finally:
                    # Clean up
                    if user.id in self.active_downloads:
                        del self.active_downloads[user.id]
                    
                    # Delete temp file if it exists
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass
        
        except Exception as e:
            logger.error(f"Error in download process: {str(e)}", exc_info=True)
            await message.edit_text(
                f"❌ خطا در پردازش درخواست: {str(e)}"
            )
    
    async def _download_file(self, url: str, format_id: str, temp_dir: str, 
                           status_msg, user_id: int) -> str:
        """Download file with progress updates"""
        output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")
        
        # Start download
        download_task = asyncio.create_task(
            self.downloader.download(
                url,
                format_id=format_id,
                output_template=output_template,
                progress_hook=lambda d: self._progress_hook(d, status_msg, user_id)
            )
        )
        
        try:
            return await download_task
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            raise
    
    def _progress_hook(self, d: dict, status_msg, user_id: int):
        """Update download progress"""
        if user_id not in self.active_downloads:
            return
        
        download_info = self.active_downloads[user_id]
        
        if d['status'] == 'downloading':
            # Calculate download speed
            elapsed = (datetime.now() - download_info['start_time']).total_seconds()
            if elapsed > 0:
                speed = d.get('downloaded_bytes', 0) / elapsed
                speed_str = f"{format_size(speed)}/s"
            else:
                speed_str = "0 B/s"
            
            # Calculate progress percentage
            total_size = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total_size > 0:
                percent = d['downloaded_bytes'] / total_size * 100
                progress = int(percent / 5)  # 20 steps (5% each)
                progress_bar = "▓" * progress + "░" * (20 - progress)
                progress_text = f"{progress_bar} {percent:.1f}%"
            else:
                progress_text = "در حال دریافت اطلاعات..."
            
            # Calculate ETA
            eta = d.get('eta')
            if eta and eta > 0:
                eta_str = get_readable_time(eta)
            else:
                eta_str = "در حال محاسبه..."
            
            # Update status message
            status_text = (
                f"⬇️ *در حال دانلود...*\n\n"
                f"📊 پیشرفت: {progress_text}\n"
                f"📦 حجم: {format_size(d.get('downloaded_bytes', 0))} / {format_size(total_size)}\n"
                f"⚡ سرعت: {speed_str}\n"
                f"⏳ زمان باقی‌مانده: {eta_str}"
            )
            
            # Only update if status has changed significantly
            current_time = datetime.now()
            last_update = download_info.get('last_update_time')
            
            if not last_update or (current_time - last_update).total_seconds() > 3:  # Update every 3 seconds
                asyncio.create_task(status_msg.edit_text(
                    status_text,
                    parse_mode=ParseMode.MARKDOWN
                ))
                download_info['last_update_time'] = current_time
        
        elif d['status'] == 'finished':
            asyncio.create_task(status_msg.edit_text(
                "✅ دانلود با موفقیت انجام شد.\n\n"
                "در حال پردازش فایل..."
            ))
    
    async def _send_file(self, chat_id: int, file_path: str, status_msg):
        """Send downloaded file to user"""
        try:
            file_size = os.path.getsize(file_path)
            
            # Check if file is too large for Telegram
            if file_size > FileSizeLimit.FILESIZE_DOWNLOAD:
                await status_msg.edit_text(
                    f"❌ حجم فایل ({format_size(file_size)}) بیشتر از حد مجاز "
                    f"({format_size(FileSizeLimit.FILESIZE_DOWNLOAD)}) برای ارسال در تلگرام است."
                )
                return
            
            # Send file
            with open(file_path, 'rb') as f:
                await self.context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=os.path.basename(file_path),
                    caption=f"✅ فایل با موفقیت دانلود شد.\n\n📝 نام فایل: `{os.path.basename(file_path)}`\n"
                            f"📦 حجم فایل: {format_size(file_size)}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await status_msg.delete()
            
        except Exception as e:
            logger.error(f"Error sending file: {str(e)}", exc_info=True)
            await status_msg.edit_text(
                f"❌ خطا در ارسال فایل: {str(e)}"
            )
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid for download"""
        # Simple URL validation
        return (url.startswith(('http://', 'https://')) and 
                any(domain in url for domain in ['youtube.com', 'youtu.be', 'instagram.com', 'tiktok.com', 'twitter.com']))
    
    def _filter_allowed_formats(self, formats: list, plan: str) -> list:
        """Filter available formats based on subscription plan"""
        plan_limits = PLAN_LIMITS.get(plan, {})
        max_quality = plan_limits.get('max_quality', '720p')
        
        # Map quality strings to numeric values for comparison
        quality_map = {
            '144p': 1, '240p': 2, '360p': 3, '480p': 4,
            '720p': 5, '1080p': 6, '1440p': 7, '2160p': 8, '4K': 8
        }
        
        max_quality_num = quality_map.get(max_quality, 3)  # Default to 360p
        
        allowed_formats = []
        for fmt in formats:
            # Skip audio-only formats
            if fmt.get('vcodec') == 'none':
                continue
                
            # Check resolution
            resolution = fmt.get('resolution', '').lower()
            if not resolution:
                continue
                
            # Extract quality number (e.g., '720p' -> 720)
            quality_num = 0
            for q, num in quality_map.items():
                if q in resolution:
                    quality_num = num
                    break
            
            # Skip if quality exceeds plan limit
            if quality_num > max_quality_num:
                continue
            
            # Add format to allowed list
            allowed_formats.append(fmt)
        
        # Sort by quality (descending) and file size (descending)
        allowed_formats.sort(
            key=lambda x: (
                quality_map.get(x.get('resolution', '0p').lower().split('p')[0] + 'p', 0),
                x.get('filesize', 0) or x.get('filesize_approx', 0)
            ),
            reverse=True
        )
        
        return allowed_formats

# Create global download manager instance
download_manager = DownloadManager(None)

# Create message handler
download_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    download_manager.handle_download
)

# Create callback query handler
download_callback = CallbackQueryHandler(
    download_manager.start_download,
    pattern=r"^dl:"
)

# Cancel download handler
async def cancel_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel active download"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id in download_manager.active_downloads:
        download_info = download_manager.active_downloads[user_id]
        download_info['task'].cancel()
        del download_manager.active_downloads[user_id]
        
        await query.message.edit_text("❌ دانلود لغو شد.")
    else:
        await query.answer("هیچ دانلود فعالی برای لغو وجود ندارد.")

cancel_download_handler = CallbackQueryHandler(
    cancel_download,
    pattern="^cancel_download$"
)
