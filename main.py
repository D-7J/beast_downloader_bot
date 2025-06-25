import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import (
    BOT_TOKEN,
    LOG_LEVEL,
    LOG_FILE,
    ADMIN_IDS,
    SubscriptionPlans,
    PLAN_LIMITS,
)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Constants
BOT_USERNAME = "beast_downloader_bot"  # Replace with your bot's username

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"سلام {user.first_name} 👋\n\n"
        "به ربات دانلودر حرفه‌ای خوش آمدید!\n\n"
        "با این ربات می‌توانید از منابع مختلف دانلود کنید.\n"
        "برای مشاهده منو از دکمه‌های پایین استفاده کنید."
    )
    
    keyboard = [
        [
            InlineKeyboardButton("💎 خرید اشتراک", callback_data="buy_subscription"),
            InlineKeyboardButton("📊 وضعیت اشتراک", callback_data="subscription_status"),
        ],
        [
            InlineKeyboardButton("📥 دانلود فایل", callback_data="download"),
            InlineKeyboardButton("ℹ️ راهنما", callback_data="help"),
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            welcome_message, reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.edit_text(
            welcome_message, reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "راهنمای استفاده از ربات:\n\n"
        "📥 دانلود فایل: لینک فایل یا ویدیوی مورد نظر را ارسال کنید.\n"
        "💎 اشتراک: برای مشاهده پلن‌های اشتراک و خرید.\n"
        "📊 وضعیت: اطلاعات اشتراک فعلی شما.\n\n"
        "پشتیبانی: @your_support_username"
    )
    await update.message.reply_text(help_text)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        await help_command(update, context)
    elif query.data == "buy_subscription":
        await show_subscription_plans(update, context)
    # Add more button handlers here

async def show_subscription_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available subscription plans."""
    plans_text = "🛒 پلن‌های اشتراک:\n\n"
    
    for plan_name, plan_data in PLAN_LIMITS.items():
        if plan_name == SubscriptionPlans.FREE:
            price = "رایگان"
        else:
            price = f"{plan_data['price']:,} تومان"
            
        plans_text += (
            f"{plan_name.upper()}\n"
            f"💵 قیمت: {price}\n"
            f"📥 دانلود روزانه: {plan_data['daily_downloads'] if plan_data['daily_downloads'] != float('inf') else 'نامحدود'}\n"
            f"📦 حداکثر حجم فایل: {plan_data['max_file_size'] // (1024*1024)} مگابایت\n"
            f"🖼 کیفیت: تا {plan_data['max_quality']}\n"
            f"💧 واترمارک: {'✅' if plan_data['watermark'] else '❌'}\n\n"
        )
    
    keyboard = [
        [
            InlineKeyboardButton("برنزی 🥉", callback_data=f"select_plan_{SubscriptionPlans.BRONZE}"),
            InlineKeyboardButton("نقره‌ای 🥈", callback_data=f"select_plan_{SubscriptionPlans.SILVER}"),
            InlineKeyboardButton("طلایی 🥇", callback_data=f"select_plan_{SubscriptionPlans.GOLD}"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main"),
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            plans_text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            plans_text, reply_markup=reply_markup
        )

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button))
    
    # Log all errors
    application.add_error_handler(error_handler)
    
    # Start the Bot
    logger.info("Bot is starting...")
    application.run_polling()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if update and hasattr(update, 'effective_message') and update.effective_message:
        await update.effective_message.reply_text(
            '⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.'
        )

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    main()
