import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from collections import defaultdict

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

# Helper functions
def get_basic_stats(db: Session) -> Dict[str, Any]:
    """Get basic statistics about users, subscriptions, and downloads."""
    from database import User, Subscription, Download, Payment
    
    stats = {}
    
    # User counts
    stats['total_users'] = db.query(User).count()
    
    # Subscription stats
    stats['active_subscriptions'] = db.query(Subscription).filter(
        Subscription.is_active == True,
        Subscription.end_date > datetime.utcnow()
    ).count()
    
    # Payment stats
    payment_stats = db.query(
        func.sum(Payment.amount).label('total_earnings'),
        func.count().label('total_payments')
    ).filter(
        Payment.status == 'completed'
    ).first()
    
    stats['total_earnings'] = payment_stats.total_earnings or 0
    stats['total_payments'] = payment_stats.total_payments or 0
    
    # Download stats
    stats['total_downloads'] = db.query(Download).count()
    
    # Downloads by type
    downloads_by_type = db.query(
        Download.content_type,
        func.count(Download.id).label('count')
    ).group_by(Download.content_type).all()
    
    stats['downloads_by_type'] = dict(downloads_by_type)
    
    return stats

# Command Handlers
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics."""
    db = next(context.bot_data['db_session_generator']())
    try:
        stats = get_basic_stats(db)
        
        text = ("📊 *آمار ربات*\n\n"
               f"👥 تعداد کل کاربران: {stats['total_users']:,}\n"
               f"✅ اشتراک‌های فعال: {stats['active_subscriptions']:,}\n"
               f"💰 درآمد کل: {format_price(stats['total_earnings'])}\n"
               f"💳 تعداد پرداخت‌ها: {stats['total_payments']:,}\n"
               f"📥 تعداد کل دانلودها: {stats['total_downloads']:,}\n\n")
        
        # Add downloads by type
        if stats['downloads_by_type']:
            text += "📥 *تعداد دانلودها بر اساس نوع:*\n"
            for content_type, count in stats['downloads_by_type'].items():
                text += f"  • {content_type}: {count:,}\n"
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"Error in stats command: {e}", exc_info=True)
        await update.message.reply_text("❌ خطا در دریافت آمار. لطفاً دوباره تلاش کنید.")
    finally:
        db.close()

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List users with pagination."""
    db = next(context.bot_data['db_session_generator']())
    try:
        from database import User, Subscription
        
        # Get pagination parameters
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
        per_page = 10
        
        # Get users with subscription info
        users = db.query(
            User,
            Subscription
        ).outerjoin(
            Subscription, 
            (User.id == Subscription.user_id) & (Subscription.is_active == True)
        ).order_by(
            User.created_at.desc()
        ).limit(per_page).offset((page - 1) * per_page).all()
        
        total_users = db.query(User).count()
        
        # Format user list
        text = f"👥 *لیست کاربران* (صفحه {page:,})\n\n"
        
        for i, (user, subscription) in enumerate(users, 1):
            user_info = f"{i + (page-1)*per_page}. "
            user_info += f"<a href='tg://user?id={user.telegram_id}'>{user.full_name or 'بدون نام'}</a>"
            
            if user.username:
                user_info += f" (@{user.username})"
                
            if subscription:
                user_info += f"\n   📅 اشتراک: {subscription.plan.name} (تا {subscription.end_date.strftime('%Y-%m-%d')})"
            else:
                user_info += "\n   ⭕ بدون اشتراک"
                
            text += user_info + "\n\n"
        
        # Add pagination buttons
        total_pages = (total_users + per_page - 1) // per_page
        
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ صفحه قبل", callback_data=f"admin_users_{page-1}"))
        if page < total_pages:
            if keyboard:  # If there's a previous button, add next to the same row
                keyboard.append(InlineKeyboardButton("صفحه بعد ➡️", callback_data=f"admin_users_{page+1}"))
            else:
                keyboard = [InlineKeyboardButton("صفحه بعد ➡️", callback_data=f"admin_users_{page+1}")]
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in list_users command: {e}", exc_info=True)
        await update.message.reply_text("❌ خطا در دریافت لیست کاربران. لطفاً دوباره تلاش کنید.")
    finally:
        db.close()

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast a message to all users."""
    if not context.args:
        await update.message.reply_text(
            "✍️ لطفاً پیام خود را بعد از دستور بنویسید. مثال:\n"
            "`/broadcast سلام به همه کاربران عزیز!`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Ask for confirmation
    message_text = ' '.join(context.args)
    keyboard = [
        [
            InlineKeyboardButton("✅ تایید ارسال", callback_data=f"broadcast_confirm_{message_text[:30]}..."),
            InlineKeyboardButton("❌ انصراف", callback_data="broadcast_cancel")
        ]
    ]
    
    await update.message.reply_text(
        f"⚠️ آیا مطمئن هستید که می‌خواهید این پیام را برای همه کاربران ارسال کنید؟\n\n{message_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle broadcast confirmation."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "broadcast_cancel":
        await query.message.edit_text("❌ ارسال پیام همگانی لغو شد.")
        return
    
    # Extract message text from callback data
    message_text = query.data.replace("broadcast_confirm_", "").strip()
    
    # Get all users
    db = next(context.bot_data['db_session_generator']())
    try:
        from database import User
        users = db.query(User).all()
        total_users = len(users)
        
        # Send message to each user
        success = 0
        failed = 0
        
        await query.message.edit_text(f"🔄 در حال ارسال پیام به {total_users} کاربر...")
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                success += 1
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                logger.error(f"Error sending broadcast to user {user.id}: {e}")
                failed += 1
                
        # Send report
        report = (
            f"✅ ارسال پیام همگانی به پایان رسید\n\n"
            f"📊 آمار ارسال:\n"
            f"• تعداد کل کاربران: {total_users}\n"
            f"• ارسال موفق: {success}\n"
            f"• ارسال ناموفق: {failed}"
        )
        
        await query.message.edit_text(report)
        
    except Exception as e:
        logger.error(f"Error in broadcast_confirm: {e}", exc_info=True)
        await query.message.edit_text("❌ خطا در ارسال پیام همگانی. لطفاً دوباره تلاش کنید.")
    finally:
        db.close()

async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin button callbacks."""
    query = update.callback_query
    await query.answer()
    
    # Extract action and data from callback data
    callback_data = query.data.split('_', 1)
    if len(callback_data) < 2:
        return
        
    action = callback_data[1].split('_')[0]
    
    if action == 'payments':
        await admin_payments(update, context)
    elif action == 'stats':
        await admin_stats(update, context)
    elif action == 'users':
        await list_users(update, context)
    elif action == 'broadcast':
        await broadcast(update, context)
    else:
        await admin_panel(update, context)

# Create command handlers
admin_handler = CommandHandler("admin", admin_panel)
stats_handler = CommandHandler("stats", stats)
users_handler = CommandHandler("users", list_users)
broadcast_handler = CommandHandler("broadcast", broadcast, filters=filters.ChatType.PRIVATE)

# Create callback query handlers
admin_callback_handler = CallbackQueryHandler(admin_button, pattern="^admin_")
confirm_payment_handler = CallbackQueryHandler(confirm_payment, pattern="^confirm_payment_")
broadcast_callback_handler = CallbackQueryHandler(broadcast_confirm, pattern="^broadcast_")

# Export handlers
handlers = [
    admin_handler,
    stats_handler,
    users_handler,
    broadcast_handler,
    admin_callback_handler,
    confirm_payment_handler,
    broadcast_callback_handler,
]

# Admin commands for bot setup
ADMIN_COMMANDS = [
    BotCommand("admin", "پنل مدیریت"),
    BotCommand("stats", "آمار ربات"),
    BotCommand("users", "لیست کاربران"),
    BotCommand("broadcast", "ارسال پیام همگانی"),
]
