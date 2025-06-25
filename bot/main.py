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
    download as download_handlers_module,
)
from bot.middleware import setup_middlewares
from database import Base
from config import (
    BOT_TOKEN,
    DATABASE_URL,
    ADMIN_IDS,
    LOG_LEVEL,
    WEBHOOK_MODE,
    WEBHOOK_LISTEN,
    WEBHOOK_PORT,
    WEBHOOK_URL,
    WEBHOOK_SSL_CERT,
    WEBHOOK_SSL_PRIV,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.getLevelName(LOG_LEVEL),
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create database tables
        Base.metadata.create_all(bind=self.engine)
    
    def get_db(self):
        """Get a database session."""
        db = self.SessionLocal()
        try:
            return db
        except Exception as e:
            logger.error(f"Error getting database session: {e}")
            db.close()
            raise

# Initialize database manager
db_manager = DatabaseManager(DATABASE_URL)

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

def setup_handlers(application: Application) -> None:
    """Set up all the handlers for the bot."""
    # Command handlers (these bypass middleware)
    command_handlers = [
        ("start", start_handler.start),
        ("help", help_handler.help_command),
        ("buy", buy_handler.buy_plan),
    ]
    
    for command, callback in command_handlers:
        application.add_handler(CommandHandler(command, callback))
    
    # Admin command handlers
    admin_filter = filters.User(user_id=ADMIN_IDS) if ADMIN_IDS else None
    admin_handlers = [
        ("admin", admin_handler.admin_panel),
        ("stats", admin_handler.stats),
        ("users", admin_handler.list_users),
        ("broadcast", admin_handler.broadcast),
    ]
    
    for command, callback in admin_handlers:
        application.add_handler(CommandHandler(command, callback, filters=admin_filter))
    
    # Callback query handlers
    callback_handlers = [
        ("^buy_plan$", buy_handler.buy_plan),
        ("^select_plan:", buy_handler.select_plan),
        ("^admin_", admin_handler.admin_button),
    ]
    
    for pattern, callback in callback_handlers:
        application.add_handler(CallbackQueryHandler(callback, pattern=pattern))
    
    # Add download handlers
    for handler in download_handlers_module.handlers:
        application.add_handler(handler)
    
    # Set up middleware
    setup_middlewares(application)
    
    # Error handler
    application.add_error_handler(error_handler)

async def post_init(application: Application) -> None:
    """Configure bot commands and other post-initialization tasks."""
    # Store database manager in bot_data for use in handlers
    application.bot_data['db_manager'] = db_manager
    
    # Set bot commands for regular users
    await application.bot.set_my_commands([
        BotCommand("start", "شروع کار با ربات"),
        BotCommand("help", "راهنمای استفاده"),
        BotCommand("buy", "خرید اشتراک"),
    ])
    
    # Set admin commands for admin users
    if ADMIN_IDS:
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
                scope={"type": scope_type, "user_ids": ADMIN_IDS}
            )
    
    logger.info("Bot is ready to receive updates")

def main() -> None:
    """Start the bot."""
    # Create the Application with persistence and context settings
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)  # Enable handling updates in parallel
        .build()
    )
    
    # Set up handlers
    setup_handlers(application)
    
    # Start the Bot
    if WEBHOOK_MODE:
        # Webhook mode for production
        webhook_path = f"/webhook/{BOT_TOKEN}"
        webhook_url = f"{WEBHOOK_URL.rstrip('/')}{webhook_path}"
        
        logger.info(f"Starting webhook on {webhook_url}")
        
        application.run_webhook(
            listen=WEBHOOK_LISTEN,
            port=int(WEBHOOK_PORT),
            url_path=webhook_path,
            webhook_url=webhook_url,
            cert=WEBHOOK_SSL_CERT,
            key=WEBHOOK_SSL_PRIV,
            drop_pending_updates=True,
        )
    else:
        # Polling mode for development
        logger.info("Starting in polling mode...")
        application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)