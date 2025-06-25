"""
Beast Downloader Bot - Main Entry Point
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    ApplicationBuilder,
)
from telegram.error import TelegramError
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Add parent directory to path to allow importing modules
sys.path.append(str(Path(__file__).parent.parent))

# Import handlers and middleware
from bot.handlers import (
    start as start_handler,
    help as help_handler,
    buy as buy_handler,
    admin as admin_handler,
    download as download_handler,
)
from bot.middleware import setup_middlewares
from database import Base, get_db_url
from config import config

from database import init_db, get_db
from config import config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize database
engine = create_engine(get_db_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create database tables
Base.metadata.create_all(bind=engine)

def get_db_session():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Disable some noisy logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and send a message to the user if possible."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if update and hasattr(update, 'message'):
        try:
            await update.message.reply_text(
                "❌ متاسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید."
            )
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    # Log the full traceback
    logger.error(
        "Exception while handling an update:",
        exc_info=context.error
    )
    
    # Close any open database sessions
    if 'db' in context.bot_data:
        try:
            context.bot_data['db'].close()
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")


def setup_handlers(application: Application) -> None:
    """Set up all the handlers for the bot."""
    # Command handlers (these bypass middleware)
    command_handlers = [
        ("start", start_handler.start),
        ("help", help_handler.help_command),
        ("buy", buy_handler.buy),
    ]
    
    for command, callback in command_handlers:
        application.add_handler(CommandHandler(command, callback))
    
    # Admin command handlers
    admin_filter = filters.User(username=config.ADMIN_USERNAMES)
    admin_handlers = [
        ("admin", admin_handler.admin),
        ("stats", admin_handler.stats),
        ("users", admin_handler.list_users),
        ("broadcast", admin_handler.broadcast),
    ]
    
    for command, callback in admin_handlers:
        application.add_handler(CommandHandler(command, callback, filters=admin_filter))
    
    # Callback query handlers
    callback_handlers = [
        ("^plan_", buy_handler.button),
        ("^admin_", admin_handler.admin_button),
    ]
    
    for pattern, callback in callback_handlers:
        application.add_handler(CallbackQueryHandler(callback, pattern=pattern))
    
    # Message handler for downloads (must be last)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        download_handler.handle_download
    ))
    
    # Set up middleware
    setup_middlewares(application)
    
    # Error handler
    application.add_error_handler(error_handler)


async def post_init(application: Application) -> None:
    """Configure bot commands and other post-initialization tasks."""
    # Set bot commands for regular users
    await application.bot.set_my_commands([
        BotCommand("start", "شروع کار با ربات"),
        BotCommand("help", "راهنمای استفاده"),
        BotCommand("buy", "خرید اشتراک"),
    ])
    
    # Set admin commands for admin users
    if config.ADMIN_USERNAMES:
        admin_commands = [
            ("admin", "پنل مدیریت"),
            ("stats", "آمار ربات"),
            ("users", "مدیریت کاربران"),
            ("broadcast", "ارسال پیام همگانی"),
        ]
        
        # Add admin commands for both private chats and groups
        for scope_type in ["all_private_chats", "all_group_chats"]:
            await application.bot.set_my_commands(
                [BotCommand(cmd, desc) for cmd, desc in admin_commands],
                scope={"type": scope_type, "user_ids": [int(id) for id in config.ADMIN_IDS]}
            )
    
    # Store database session generator in bot_data for use in handlers
    application.bot_data['db_session_generator'] = get_db_session
    
    logger.info("Bot is ready to receive updates")


def main() -> None:
    """Start the bot."""
    # Create the Application with persistence and context settings
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)  # Enable handling updates in parallel
        .build()
    )
    
    # Set up handlers
    setup_handlers(application)
    
    # Start the Bot
    if config.WEBHOOK_MODE:
        # Webhook mode for production
        application.run_webhook(
            listen=config.WEBHOOK_LISTEN,
            port=config.WEBHOOK_PORT,
            url_path=config.BOT_TOKEN,
            webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}",
            cert=config.WEBHOOK_SSL_CERT,
            key=config.WEBHOOK_SSL_PRIV,
            drop_pending_updates=True,
        )
    else:
        # Polling mode for development
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
