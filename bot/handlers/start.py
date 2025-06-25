from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from database import get_or_create_user, get_user_subscription
from config import PLAN_LIMITS, SubscriptionPlans

# Helper function to get subscription info text
def get_subscription_info(subscription):
    if not subscription or not subscription.is_active:
        return "❌ *وضعیت اشتراک:* غیرفعال\n\nشما اشتراک فعالی ندارید. لطفا برای استفاده از امکانات ربات، اشتراک تهیه کنید."
    
    plan_name = {
        SubscriptionPlans.FREE: "رایگان",
        SubscriptionPlans.BRONZE: "برنزی",
        SubscriptionPlans.SILVER: "نقره‌ای",
        SubscriptionPlans.GOLD: "طلایی"
    }.get(subscription.plan, "ناشناخته")
    
    plan_limits = PLAN_LIMITS.get(subscription.plan, {})
    
    # Calculate remaining downloads if not unlimited
    remaining_downloads = "نامحدود"
    if plan_limits.get("daily_downloads", float('inf')) != float('inf'):
        remaining = max(0, plan_limits["daily_downloads"] - subscription.daily_downloads_used)
        remaining_downloads = f"{remaining} از {plan_limits['daily_downloads']}"
    
    # Format end date if exists
    end_date = "نامحدود"
    if subscription.end_date:
        end_date = subscription.end_date.strftime("%Y-%m-%d %H:%M")
    
    return f"""✅ *وضعیت اشتراک:* فعال

📋 *پلن:* {plan_name}
📥 *دانلود باقی‌مانده امروز:* {remaining_downloads}
📆 *تاریخ انقضا:* {end_date}

برای مشاهده امکانات ربات از منوی پایین استفاده کنید."""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    # Get or create user in database
    user = update.effective_user
    db = context.bot_data["db"]
    
    # Create or update user in database
    db_user = get_or_create_user(db, {
        'telegram_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    })
    
    # Get user's subscription
    subscription = get_user_subscription(db, db_user.id)
    
    # Prepare welcome message
    welcome_text = f"""سلام {user.first_name} 👋

به ربات دانلودر خوش آمدید! با استفاده از این ربات می‌توانید فایل‌های ویدیویی را با کیفیت بالا دانلود کنید.

{subscription_info}"""
    
    # Get subscription info
    subscription_info = get_subscription_info(subscription)
    welcome_text = welcome_text.format(subscription_info=subscription_info)
    
    # Create inline keyboard for main menu
    keyboard = [
        [
            InlineKeyboardButton("🛒 خرید اشتراک", callback_data="buy_plan"),
            InlineKeyboardButton("📥 دانلود فایل", callback_data="download")
        ],
        [
            InlineKeyboardButton("📊 وضعیت اشتراک", callback_data="subscription_status"),
            InlineKeyboardButton("ℹ️ راهنما", callback_data="help")
        ]
    ]
    
    # Add admin button if user is admin
    if user.id in context.bot_data["admin_ids"]:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send welcome message
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# Create command handler
start_handler = CommandHandler("start", start)
