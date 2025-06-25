"""
Beast Downloader Bot - Main Entry Point
"""
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import TelegramError

# Add parent directory to path to allow importing modules
sys.path.append(str(Path(__file__).parent.parent))

# Import handlers
from bot.handlers import (
    start as start_handler,
    help as help_handler,
    buy as buy_handler,
    admin as admin_handler,
    download as download_handler,
)
from database import init_db, get_db
from config import config

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Disable some noisy logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and send a message to the user if possible."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Log the error and the update that caused it
    error_msg = f"An error occurred: {context.error}"
    logger.error(error_msg)

    # Only try to send a message if we have a valid update with a chat
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            )
        except Exception as e:
            logger.error(f"Error sending error message: {e}")


def setup_handlers(application: Application) -> None:
    """Set up all the handlers for the bot."""
    # Command handlers
    application.add_handler(CommandHandler("start", start_handler.start))
    application.add_handler(CommandHandler("help", help_handler.help_command))
    application.add_handler(CommandHandler("buy", buy_handler.buy_command))
    application.add_handler(CommandHandler("status", download_handler.status_command))
    application.add_handler(CommandHandler("cancel", download_handler.cancel_command))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_handler.admin_command))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(buy_handler.buy_button, pattern=r"^buy_"))
    application.add_handler(CallbackQueryHandler(admin_handler.admin_callback, pattern=r"^admin_"))
    application.add_handler(CallbackQueryHandler(download_handler.download_callback, pattern=r"^dl_"))
    application.add_handler(CallbackQueryHandler(download_handler.cancel_callback, pattern=r"^cancel_"))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        download_handler.handle_message
    ))
    
    # Error handler
    application.add_error_handler(error_handler)


async def post_init(application: Application) -> None:
    """Configure bot commands and other post-initialization tasks."""
    # Set bot commands
    commands = [
        BotCommand("start", "شروع کار با ربات"),
        BotCommand("help", "راهنمای استفاده"),
        BotCommand("buy", "خرید اشتراک"),
        BotCommand("status", "وضعیت دانلودها"),
        BotCommand("cancel", "لغو عملیات جاری"),
    ]
    
    # Add admin commands if user is admin
    if config.ADMIN_IDS:
        admin_commands = [
            BotCommand("admin", "پنل مدیریت"),
        ]
        commands.extend(admin_commands)
    
    await application.bot.set_my_commands(commands)
    
    # Log bot info
    me = await application.bot.get_me()
    logger.info(f"Bot started: @{me.username} (ID: {me.id})")


def main() -> None:
    """Start the bot."""
    # Load environment variables
    load_dotenv()
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Create the Application
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Set up handlers
    setup_handlers(application)
    
    # Start the Bot
    logger.info("Starting bot...")
    
    # Run the bot until you press Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
