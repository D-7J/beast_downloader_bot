#!/usr/bin/env python3
"""
Persian Downloader Bot - Main File
A powerful Telegram bot for downloading videos from social media platforms
"""

import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.error import TelegramError
from loguru import logger

# تنظیمات لاگ
from src.config import bot_config, log_config
logger.remove()
logger.add(
    sys.stderr,
    level=log_config.level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(
    log_config.file_path,
    rotation=log_config.max_size,
    retention=log_config.backup_count,
    level=log_config.level
)

# ایمپورت ماژول‌های محلی
from src.database.mongo_client import mongo_manager
from src.database.redis_client import redis_manager
from src.handlers import (
    start_handler,
    download_handler,
    payment_handler,
    admin_handler,
    profile_handler,
    callback_handler
)
from src.utils.decorators import async_error_handler
from src.tasks.celery_app import celery_app

class DownloaderBot:
    """کلاس اصلی بات دانلودر"""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self.is_running = False
        
    async def initialize(self):
        """مقداردهی اولیه بات و سرویس‌ها"""
        logger.info("Initializing bot...")
        
        # اتصال به دیتابیس‌ها
        await mongo_manager.connect()
        await redis_manager.connect()
        
        # ساخت Application
        builder = Application.builder().token(bot_config.token)
        
        # تنظیمات اختیاری
        builder.concurrent_updates(True)
        builder.connect_timeout(30.0)
        builder.read_timeout(30.0)
        
        self.application = builder.build()
        
        # ثبت هندلرها
        self._register_handlers()
        
        # ثبت دستورات بات
        await self._set_bot_commands()
        
        # راه‌اندازی Celery
        celery_app.start()
        
        logger.info("Bot initialized successfully")
    
    def _register_handlers(self):
        """ثبت تمام هندلرهای بات"""
        logger.info("Registering handlers...")
        
        # Command Handlers
        self.application.add_handler(CommandHandler("start", start_handler.start_command))
        self.application.add_handler(CommandHandler("help", start_handler.help_command))
        self.application.add_handler(CommandHandler("profile", profile_handler.profile_command))
        self.application.add_handler(CommandHandler("subscription", payment_handler.subscription_command))
        self.application.add_handler(CommandHandler("support", start_handler.support_command))
        
        # Admin Commands
        self.application.add_handler(CommandHandler("admin", admin_handler.admin_panel))
        self.application.add_handler(CommandHandler("stats", admin_handler.stats_command))
        self.application.add_handler(CommandHandler("broadcast", admin_handler.broadcast_command))
        self.application.add_handler(CommandHandler("user", admin_handler.user_info_command))
        self.application.add_handler(CommandHandler("maintenance", admin_handler.maintenance_command))
        
        # Message Handlers
        # URL handler - باید اول باشد
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & filters.Regex(r'https?://[^\s]+') & ~filters.COMMAND,
                download_handler.handle_url
            )
        )
        
        # Text message handler
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                start_handler.handle_text_message
            )
        )
        
        # Callback Query Handler
        self.application.add_handler(CallbackQueryHandler(callback_handler.handle_callback))
        
        # Error Handler
        self.application.add_error_handler(self.error_handler)
        
        logger.info("All handlers registered")
    
    async def _set_bot_commands(self):
        """تنظیم دستورات بات در منو"""
        commands = [
            BotCommand("start", "شروع کار با ربات"),
            BotCommand("help", "راهنمای استفاده"),
            BotCommand("profile", "مشاهده پروفایل"),
            BotCommand("subscription", "خرید اشتراک"),
            BotCommand("support", "پشتیبانی"),
        ]
        
        await self.application.bot.set_my_commands(commands)
        
        # دستورات ادمین (فقط برای ادمین‌ها نمایش داده می‌شود)
        admin_commands = commands + [
            BotCommand("admin", "پنل مدیریت"),
            BotCommand("stats", "آمار ربات"),
            BotCommand("broadcast", "پیام همگانی"),
            BotCommand("user", "اطلاعات کاربر"),
            BotCommand("maintenance", "حالت تعمیر"),
        ]
        
        for admin_id in bot_config.admin_ids:
            try:
                await self.application.bot.set_my_commands(
                    admin_commands,
                    scope={'type': 'chat', 'chat_id': admin_id}
                )
            except TelegramError:
                pass
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت خطاهای بات"""
        logger.error(f"Update {update} caused error {context.error}")
        
        # ارسال پیام به کاربر
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ متأسفانه خطایی رخ داد.\n"
                    "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                )
        except:
            pass
        
        # ارسال گزارش به ادمین‌ها
        error_message = f"""
🚨 **خطا در بات**

👤 کاربر: {update.effective_user.id if update and update.effective_user else 'Unknown'}
📅 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
❌ خطا: `{str(context.error)}`

📝 Update:
```
{str(update)[:500] if update else 'No update'}
```
        """
        
        for admin_id in bot_config.admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=error_message,
                    parse_mode='Markdown'
                )
            except:
                pass
    
    async def start(self):
        """شروع بات"""
        await self.initialize()
        
        self.is_running = True
        logger.info("Starting bot polling...")
        
        if bot_config.use_webhook:
            # Webhook mode
            await self.application.run_webhook(
                listen="0.0.0.0",
                port=8443,
                url_path=bot_config.token,
                webhook_url=f"{bot_config.webhook_url}/{bot_config.token}"
            )
        else:
            # Polling mode
            await self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
    
    async def stop(self):
        """توقف بات"""
        logger.info("Stopping bot...")
        self.is_running = False
        
        # توقف Celery
        celery_app.control.shutdown()
        
        # قطع اتصال دیتابیس‌ها
        await mongo_manager.disconnect()
        await redis_manager.disconnect()
        
        # توقف بات
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
        
        logger.info("Bot stopped successfully")
    
    def handle_signal(self, signum, frame):
        """مدیریت سیگنال‌های سیستم"""
        logger.info(f"Received signal {signum}")
        asyncio.create_task(self.stop())

async def main():
    """تابع اصلی"""
    bot = DownloaderBot()
    
    # ثبت signal handlers
    signal.signal(signal.SIGINT, bot.handle_signal)
    signal.signal(signal.SIGTERM, bot.handle_signal)
    
    try:
        await bot.start()
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}")
        await bot.stop()
        sys.exit(1)

if __name__ == "__main__":
    # اجرا در حالت async
    asyncio.run(main())