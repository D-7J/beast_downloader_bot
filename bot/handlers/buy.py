from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode

from database import create_payment, get_user, get_user_subscription, update_subscription_plan
from config import PLAN_LIMITS, SubscriptionPlans, PAYMENT_CARD_NUMBER, PAYMENT_CARD_OWNER
from utils.helpers import format_price

# Helper function to get plan details for display
def get_plan_display_info(plan):
    plan_names = {
        SubscriptionPlans.FREE: "رایگان",
        SubscriptionPlans.BRONZE: "برنزی",
        SubscriptionPlans.SILVER: "نقره‌ای",
        SubscriptionPlans.GOLD: "طلایی"
    }
    
    plan_info = PLAN_LIMITS.get(plan, {})
    
    return {
        "name": plan_names.get(plan, plan),
        "price": plan_info.get("price", 0),
        "daily_downloads": plan_info.get("daily_downloads", 0),
        "max_file_size": plan_info.get("max_file_size", 0) / (1024 * 1024),  # Convert to MB
        "max_quality": plan_info.get("max_quality", "نامعلوم"),
        "watermark": plan_info.get("watermark", False)
    }

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available subscription plans"""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    
    # Get user from database
    db = context.bot_data["db"]
    user = get_user(db, update.effective_user.id)
    
    if not user:
        print(f"User not found for telegram_id: {update.effective_user.id}")
        print(f"All users in DB: {[u.telegram_id for u in db.query(User).all()]}")
        error_text = "خطا در یافتن اطلاعات کاربر. لطفا دوباره امتحان کنید."
        if query:
            await query.answer(error_text, show_alert=True)
        else:
            await update.message.reply_text(error_text)
        return
    
    # Get user's current subscription
    current_subscription = get_user_subscription(db, user.id)
    
    # Prepare plan details
    plans_info = []
    for plan in [SubscriptionPlans.BRONZE, SubscriptionPlans.SILVER, SubscriptionPlans.GOLD]:
        plan_info = get_plan_display_info(plan)
        plans_info.append(plan_info)
    
    # Prepare message text
    text = "🎟️ *پلن‌های اشتراک*\n\n"
    
    for plan_info in plans_info:
        # Skip if no price (shouldn't happen for paid plans)
        if not plan_info["price"]:
            continue
            
        text += f"🔸 *{plan_info['name']}* - {format_price(plan_info['price'])} تومان\n"
        
        # Add plan features
        downloads = "نامحدود" if plan_info["daily_downloads"] == float('inf') else plan_info["daily_downloads"]
        text += f"• دانلود روزانه: {downloads}\n"
        text += f"• حداکثر حجم فایل: {plan_info['max_file_size']} مگابایت\n"
        text += f"• حداکثر کیفیت: {plan_info['max_quality']}\n"
        text += "• بدون واترمارک\n"
        
        # Add special features for premium plans
        if plan_info['name'] == "نقره‌ای":
            text += "• امکان انتخاب فرمت خروجی\n"
            text += "• دانلود زیرنویس\n"
            text += "• سرعت دانلود بالاتر\n"
        elif plan_info['name'] == "طلایی":
            text += "• امکان دانلود پلی‌لیست\n"
            text += "• دانلود همزمان ۵ فایل\n"
            text += "• سریع‌ترین سرعت ممکن\n"
            text += "• پشتیبانی ۲۴ ساعته\n"
        
        text += "\n"
    
    # Add payment instructions
    text += "\n💳 *روش پرداخت:*\n"
    text += f"۱. مبلغ اشتراک مورد نظر را به شماره کارت زیر واریز کنید:\n"
    text += f"`{PAYMENT_CARD_NUMBER}`\n\n"
    text += f"۲. پس از واریز، رسید پرداخت را برای پشتیبانی ارسال کنید.\n"
    text += f"۳. اشتراک شما پس از تایید پرداخت فعال می‌شود.\n\n"
    text += f"👤 صاحب حساب: {PAYMENT_CARD_OWNER}\n"
    text += "📞 پشتیبانی: @your_support_username"
    
    # Create inline keyboard for plan selection
    keyboard = []
    for plan_info in plans_info:
        if not plan_info["price"]:  # Skip free plan
            continue
            
        plan_name = plan_info["name"]
        plan_enum = {
            "برنزی": SubscriptionPlans.BRONZE,
            "نقره‌ای": SubscriptionPlans.SILVER,
            "طلایی": SubscriptionPlans.GOLD
        }.get(plan_name)
        
        # Check if user already has this plan
        is_current_plan = (
            current_subscription and 
            current_subscription.plan == plan_enum and 
            current_subscription.is_active and
            (not current_subscription.end_date or current_subscription.end_date > datetime.utcnow())
        )
        
        button_text = f"✅ {plan_name}" if is_current_plan else plan_name
        
        keyboard.append([
            InlineKeyboardButton(
                f"{button_text} - {format_price(plan_info['price'])} تومان",
                callback_data=f"select_plan:{plan_enum}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="start")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or update message
    if query:
        await query.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        await query.answer()
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plan selection"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get selected plan
        plan = query.data.split(":")[1]
        
        # Get plan info
        plan_info = get_plan_display_info(plan)
        
        # Create payment record
        db = context.bot_data["db"]
        user = get_user(db, update.effective_user.id)
        
        if not user:
            # Add debug logging
            print(f"User not found for telegram_id: {update.effective_user.id}")
            print(f"All users in DB: {[u.telegram_id for u in db.query(User).all()]}")
            await query.answer("خطا در یافتن اطلاعات کاربر. لطفا دوباره امتحان کنید.", show_alert=True)
            return
        
        # Create payment record
        payment = create_payment(
            db=db,
            user_id=user.id,
            amount=plan_info["price"],
            plan=plan
        )
        
        # Prepare payment instructions
        text = f"💳 *پرداخت اشتراک {plan_info['name']}*\n\n"
        text += f"مبلغ قابل پرداخت: *{format_price(plan_info['price'])} تومان*\n\n"
        text += "لطفا مبلغ فوق را به شماره کارت زیر واریز کنید:\n"
        text += f"`{PAYMENT_CARD_NUMBER}`\n\n"
        text += f"👤 صاحب حساب: {PAYMENT_CARD_OWNER}\n\n"
        text += "پس از واریز، رسید پرداخت را برای پشتیبانی ارسال کنید.\n"
        text += "پس از تایید پرداخت، اشتراک شما فعال خواهد شد.\n\n"
        text += f"شناسه پرداخت: `{payment.id}`\n"
        
        # Send the payment instructions by editing the message
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Error in select_plan: {e}")
        import traceback
        traceback.print_exc()
        await query.answer("خطا در پردازش درخواست. لطفا دوباره امتحان کنید.", show_alert=True)

# Command handler for /buy
def buy_handler():
    """Handler for the /buy command."""
    return CommandHandler('buy', buy_plan)

# Create callback query handlers
buy_plan_callback = CallbackQueryHandler(buy_plan, pattern="^buy_plan$")
select_plan_callback = CallbackQueryHandler(select_plan, pattern="^select_plan:")
