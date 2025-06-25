from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from database import get_user_subscription
from config import PLAN_LIMITS, SubscriptionPlans

# Helper function to get plan details
def get_plan_details(plan):
    plan_names = {
        SubscriptionPlans.FREE: "رایگان",
        SubscriptionPlans.BRONZE: "برنزی",
        SubscriptionPlans.SILVER: "نقره‌ای",
        SubscriptionPlans.GOLD: "طلایی"
    }
    
    plan_info = PLAN_LIMITS.get(plan, {})
    
    details = []
    details.append(f"📌 *{plan_names.get(plan, plan)}*")
    
    # Add price if not free
    if plan != SubscriptionPlans.FREE:
        details.append(f"💵 قیمت: {plan_info.get('price', 0):,} تومان در ماه")
    
    # Add limits
    downloads = plan_info.get('daily_downloads', 0)
    if downloads == float('inf'):
        downloads = "نامحدود"
    details.append(f"📥 دانلود روزانه: {downloads}")
    
    max_size = plan_info.get('max_file_size', 0) / (1024 * 1024)  # Convert to MB
    details.append(f"📦 حداکثر حجم فایل: {max_size} مگابایت")
    
    details.append(f"🎞️ حداکثر کیفیت: {plan_info.get('max_quality', 'نامعلوم')}")
    
    if plan_info.get('watermark', False):
        details.append("⚠️ دارای واترمارک")
    else:
        details.append("✅ بدون واترمارک")
    
    # Add extra features for premium plans
    if plan == SubscriptionPlans.SILVER:
        details.append("✅ امکان انتخاب فرمت خروجی")
        details.append("✅ دانلود زیرنویس")
        details.append("⚡ سرعت دانلود بالاتر")
    elif plan == SubscriptionPlans.GOLD:
        details.append("✅ امکان دانلود پلی‌لیست")
        details.append("✅ دانلود همزمان ۵ فایل")
        details.append("⚡ سریع‌ترین سرعت ممکن")
        details.append("🛡️ پشتیبانی ۲۴ ساعته")
    
    return "\n".join(details)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """🤖 *راهنمای ربات دانلودر*

با استفاده از این ربات می‌توانید فایل‌های ویدیویی را از سایت‌های مختلف دانلود کنید.

*دستورات اصلی:*
/start - شروع کار با ربات
/help - نمایش این راهنما
/buy - مشاهده پلن‌های اشتراک
/status - مشاهده وضعیت اشتراک

*نحوه استفاده:*
۱. لینک ویدیوی مورد نظر را برای ربات ارسال کنید.
۲. ربات لینک را بررسی و کیفیت‌های موجود را نمایش می‌دهد.
۳. کیفیت مورد نظر را انتخاب کنید.
۴. فایل با کیفیت انتخابی دانلود می‌شود.

*محدودیت‌های اشتراک رایگان:*
- حداکثر ۵ دانلود در روز
- حداکثر حجم فایل: ۵۰ مگابایت
- کیفیت حداکثر ۷۲۰p
- دارای واترمارک

برای حذف محدودیت‌ها می‌توانید از منوی خرید اشتراک، پلن مورد نظر خود را انتخاب کنید.

📞 پشتیبانی: @your_support_username"""
    
    # Create inline keyboard for quick actions
    keyboard = [
        [
            InlineKeyboardButton("🛒 خرید اشتراک", callback_data="buy_plan"),
            InlineKeyboardButton("📊 وضعیت اشتراک", callback_data="subscription_status")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send message
    if update.callback_query:
        await update.callback_query.message.edit_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help button callback"""
    query = update.callback_query
    await query.answer()
    await help_command(update, context)

# Create command handler
help_handler = CommandHandler("help", help_command)

# Create callback query handler
help_callback_handler = CallbackQueryHandler(help_callback, pattern="^help$")
