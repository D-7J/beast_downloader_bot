import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from database import (
    get_user,
    get_user_subscription,
    get_all_users,
    get_all_payments,
    complete_payment,
    update_subscription_plan,
    get_user_downloads,
    get_all_downloads,
    get_user_payments
)
from config import PLAN_LIMITS, SubscriptionPlans
from utils.helpers import format_price, format_timedelta

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id not in context.bot_data["admin_ids"]:
        await update.message.reply_text("⛔️ دسترسی ممنوع!")
        return
    
    # Get stats
    db = context.bot_data["db"]
    users = get_all_users(db)
    payments = get_all_payments(db)
    downloads = get_all_downloads(db)
    
    # Calculate stats
    total_users = len(users)
    active_subscriptions = sum(1 for user in users if get_user_subscription(db, user.id) and get_user_subscription(db, user.id).is_active)
    total_earnings = sum(p.amount for p in payments if p.status == "completed")
    total_downloads = len(downloads)
    
    # Prepare message
    text = f"👑 *پنل مدیریت*\n\n"
    text += f"👥 تعداد کاربران: {total_user}\n"
    text += f"✅ اشتراک‌های فعال: {active_subscriptions}\n"
    text += f"💰 درآمد کل: {format_price(total_earnings)} تومان\n"
    text += f"📥 تعداد کل دانلودها: {total_downloads}\n\n"
    
    # Add recent payments
    recent_payments = sorted([p for p in payments if p.status == "completed"], key=lambda x: x.payment_date, reverse=True)[:5]
    if recent_payments:
        text += "💳 *آخرین پرداخت‌ها:*\n"
        for i, payment in enumerate(recent_payments, 1):
            user = get_user(db, payment.user_id)
            username = f"@{user.username}" if user.username else f"کاربر #{user.telegram_id}"
            text += f"{i}. {username} - {format_price(payment.amount)} تومان ({payment.plan})\n"
    
    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats"),
            InlineKeyboardButton("💳 مدیریت پرداخت‌ها", callback_data="admin_payments")
        ],
        [
            InlineKeyboardButton("📥 مدیریت دانلودها", callback_data="admin_downloads"),
            InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("🔙 منوی اصلی", callback_data="start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or update message
    if update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        await update.callback_query.answer()
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics"""
    query = update.callback_query
    await query.answer()
    
    # Get all users
    db = context.bot_data["db"]
    users = get_all_users(db)
    
    # Calculate stats
    total_users = len(users)
    
    # Group by subscription plan
    plan_counts = {}
    active_subscriptions = 0
    for user in users:
        sub = get_user_subscription(db, user.id)
        if sub and sub.is_active:
            active_subscriptions += 1
            plan_name = sub.plan
            plan_counts[plan_name] = plan_counts.get(plan_name, 0) + 1
    
    # Prepare message
    text = "📊 *آمار کاربران*\n\n"
    text += f"👥 تعداد کل کاربران: {total_user}\n"
    text += f"✅ اشتراک‌های فعال: {active_subscriptions}\n\n"
    
    # Add plan distribution
    text += "📊 توزیع پلن‌ها:\n"
    for plan, count in plan_counts.items():
        text += f"• {plan}: {count} کاربر ({count/total_users*100:.1f}%)\n"
    
    # Add user growth (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users = sum(1 for user in users if user.join_date >= week_ago)
    text += f"\n📈 کاربران جدید (۷ روز اخیر): {new_users}"
    
    # Create back button
    keyboard = [
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Update message
    await query.message.edit_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show payment management"""
    query = update.callback_query
    await query.answer()
    
    # Get pending payments
    db = context.bot_data["db"]
    payments = get_all_payments(db)
    pending_payments = [p for p in payments if p.status == "pending"]
    
    # Prepare message
    text = "💳 *مدیریت پرداخت‌ها*\n\n"
    
    if not pending_payments:
        text += "هیچ پرداخت در انتظار تاییدی وجود ندارد."
    else:
        text += "🔍 *پرداخت‌های در انتظار تایید:*\n\n"
        for i, payment in enumerate(pending_payments, 1):
            user = get_user(db, payment.user_id)
            username = f"@{user.username}" if user.username else f"کاربر #{user.telegram_id}"
            text += f"{i}. {username}\n"
            text += f"   مبلغ: {format_price(payment.amount)} تومان\n"
            text += f"   پلن: {payment.plan}\n"
            text += f"   شناسه پرداخت: `{payment.id}`\n\n"
    
    # Create inline keyboard
    keyboard = []
    
    # Add buttons for each pending payment
    for i, payment in enumerate(pending_payments[:5], 1):  # Max 5 buttons
        keyboard.append([
            InlineKeyboardButton(
                f"✅ تایید پرداخت #{payment.id}",
                callback_data=f"confirm_payment:{payment.id}"
            )
        ])
    
    # Add navigation buttons
    keyboard.append([
        InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_payments"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="admin")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Update message
    await query.message.edit_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm a payment"""
    query = update.callback_query
    await query.answer()
    
    # Get payment ID from callback data
    payment_id = int(query.data.split(":")[1])
    
    # Find and update payment
    db = context.bot_data["db"]
    
    try:
        # Mark payment as completed
        payment = complete_payment(
            db=db,
            payment_id=payment_id,
            transaction_id=f"MANUAL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        
        if not payment:
            raise ValueError("Payment not found")
        
        # Get user info
        user = get_user(db, payment.user_id)
        
        # Send success message to admin
        success_text = f"✅ پرداخت با موفقیت تایید شد.\n\n"
        success_text += f"👤 کاربر: {user.first_name} (@{user.username or 'N/A'})\n"
        success_text += f"💳 مبلغ: {format_price(payment.amount)} تومان\n"
        success_text += f"📝 پلن: {payment.plan}\n"
        success_text += f"🆔 شناسه پرداخت: {payment.id}"
        
        await query.message.reply_text(
            success_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=f"✅ پرداخت شما با موفقیت تایید شد!\n\n"
                     f"اشتراک {payment.plan} شما فعال شد.\n"
                     f"لطفا از منوی اصلی گزینه 'وضعیت اشتراک' را انتخاب کنید.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send notification to user {user.telegram_id}: {e}")
            await query.message.reply_text(f"⚠️ خطا در ارسال پیام به کاربر: {e}")
        
        # Update payment list
        await admin_payments(update, context)
        
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        await query.answer("❌ خطا در تایید پرداخت. لطفا دوباره امتحان کنید.", show_alert=True)

# Create command handler
admin_handler = CommandHandler("admin", admin_panel)

# Create callback query handlers
admin_callback = CallbackQueryHandler(admin_panel, pattern="^admin$")
admin_stats_callback = CallbackQueryHandler(admin_stats, pattern="^admin_stats$")
admin_payments_callback = CallbackQueryHandler(admin_payments, pattern="^admin_payments$")
confirm_payment_callback = CallbackQueryHandler(confirm_payment, pattern="^confirm_payment:")
