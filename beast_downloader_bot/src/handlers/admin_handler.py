import os
import io
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TelegramError
from loguru import logger
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
import pandas as pd

from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..database.models import PaymentStatus
from ..config import bot_config, subscription_config
from ..utils import messages, keyboards
from ..utils.decorators import admin_only, log_action, typing_action
from ..utils.helpers import format_file_size, split_large_text

# تنظیم فونت فارسی برای نمودارها
try:
    font_path = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    if os.path.exists(font_path):
        font_manager.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = 'Liberation Sans'
except:
    pass

# States for conversation
BROADCAST_MESSAGE = 1
USER_SEARCH = 2
SETTING_VALUE = 3

@admin_only
@log_action("admin_panel")
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل مدیریت اصلی"""
    await update.message.reply_text(
        "👨‍💼 **پنل مدیریت**\n\nیک گزینه را انتخاب کنید:",
        reply_markup=keyboards.Keyboards.admin_panel(),
        parse_mode='Markdown'
    )

@admin_only
@log_action("admin_stats")
@typing_action
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /stats برای ادمین"""
    await show_stats(update, context)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار کلی بات"""
    # دریافت آمار از MongoDB
    stats = await mongo_manager.get_dashboard_stats()
    
    # دریافت آمار Redis
    active_users = await redis_manager.get_active_users_count()
    queue_stats = await redis_manager.get_queue_stats()
    
    # آمار فضای دیسک
    from ..services.file_manager import FileManager
    file_manager = FileManager()
    storage_stats = await file_manager.get_storage_stats()
    
    # فرمت کردن آمار
    stats_text = messages.ADMIN_STATS.format(
        total_users=stats['total_users'],
        active_users=stats['active_users'],
        online_users=active_users,
        new_users_today=stats.get('new_users_today', 0),
        free_users=stats['subscription_stats'].get('free', 0),
        bronze_users=stats['subscription_stats'].get('bronze', 0),
        silver_users=stats['subscription_stats'].get('silver', 0),
        gold_users=stats['subscription_stats'].get('gold', 0),
        total_downloads=stats['total_downloads'],
        downloads_today=stats['today_downloads'],
        successful_today=stats.get('successful_today', 0),
        failed_today=stats.get('failed_today', 0),
        revenue_today=stats.get('revenue_today', 0),
        revenue_month=stats['monthly_revenue'],
        total_revenue=stats.get('total_revenue', 0),
        gold_queue=queue_stats.get('gold', 0),
        silver_queue=queue_stats.get('silver', 0),
        bronze_queue=queue_stats.get('bronze', 0),
        free_queue=queue_stats.get('free', 0),
        last_update=datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    )
    
    # اضافه کردن آمار فضا
    stats_text += f"\n\n💾 **فضای ذخیره‌سازی:**\n"
    stats_text += f"├ استفاده شده: {format_file_size(storage_stats['total_size'])}\n"
    stats_text += f"├ فایل‌های موقت: {format_file_size(storage_stats['temp_size'])}\n"
    stats_text += f"└ فضای آزاد: {format_file_size(storage_stats['disk_free'])} ({100 - storage_stats['disk_usage_percent']:.1f}%)"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 بروزرسانی", callback_data='admin_stats'),
            InlineKeyboardButton("📊 نمودارها", callback_data='admin_charts')
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='admin_panel')]
    ])
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            stats_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            stats_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

async def show_charts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش نمودارهای آماری"""
    query = update.callback_query
    await query.answer("در حال تولید نمودارها...")
    
    try:
        # دریافت آمار 30 روز اخیر
        stats = await mongo_manager.get_statistics(days=30)
        
        if not stats:
            await query.message.reply_text("📊 داده‌ای برای نمایش وجود ندارد.")
            return
        
        # تبدیل به DataFrame
        df = pd.DataFrame([s.to_dict() for s in stats])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # ایجاد نمودارها
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('آمار 30 روز اخیر', fontsize=16)
        
        # 1. نمودار دانلودها
        ax1.plot(df['date'], df['total_downloads'], 'b-', label='کل')
        ax1.plot(df['date'], df['successful_downloads'], 'g-', label='موفق')
        ax1.plot(df['date'], df['failed_downloads'], 'r-', label='ناموفق')
        ax1.set_title('دانلودها')
        ax1.set_xlabel('تاریخ')
        ax1.set_ylabel('تعداد')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. نمودار کاربران
        ax2.plot(df['date'], df['new_users'], 'purple', marker='o')
        ax2.set_title('کاربران جدید')
        ax2.set_xlabel('تاریخ')
        ax2.set_ylabel('تعداد')
        ax2.grid(True, alpha=0.3)
        
        # 3. نمودار درآمد
        ax3.bar(df['date'], df['revenue'] / 1000, color='green', alpha=0.7)
        ax3.set_title('درآمد (هزار تومان)')
        ax3.set_xlabel('تاریخ')
        ax3.set_ylabel('مبلغ')
        ax3.grid(True, alpha=0.3)
        
        # 4. نمودار حجم دانلود
        ax4.fill_between(df['date'], df['total_size'] / (1024**3), color='blue', alpha=0.5)
        ax4.set_title('حجم دانلود (گیگابایت)')
        ax4.set_xlabel('تاریخ')
        ax4.set_ylabel('حجم')
        ax4.grid(True, alpha=0.3)
        
        # فرمت تاریخ
        for ax in [ax1, ax2, ax3, ax4]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        # ذخیره و ارسال
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        await query.message.reply_photo(
            photo=buffer,
            caption="📊 نمودارهای آماری 30 روز اخیر",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='admin_stats')
            ]])
        )
        
    except Exception as e:
        logger.error(f"Error generating charts: {str(e)}")
        await query.message.reply_text(
            "❌ خطا در تولید نمودارها.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='admin_stats')
            ]])
        )

async def show_users_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کاربران"""
    query = update.callback_query
    
    management_text = """
👥 **مدیریت کاربران**

انتخاب کنید:
    """
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 جستجوی کاربر", callback_data='admin_search_user'),
            InlineKeyboardButton("🏆 کاربران برتر", callback_data='admin_top_users')
        ],
        [
            InlineKeyboardButton("🚫 کاربران مسدود", callback_data='admin_banned_users'),
            InlineKeyboardButton("💎 کاربران پرمیوم", callback_data='admin_premium_users')
        ],
        [
            InlineKeyboardButton("📊 گزارش کاربران", callback_data='admin_users_report'),
            InlineKeyboardButton("🔙 بازگشت", callback_data='admin_panel')
        ]
    ])
    
    await query.message.edit_text(
        management_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@admin_only
async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /user برای دریافت اطلاعات کاربر"""
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً آیدی کاربر را وارد کنید.\n"
            "مثال: `/user 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        user_id = int(context.args[0])
        await show_user_info(update, context, user_id)
    except ValueError:
        await update.message.reply_text("❌ آیدی کاربر باید عدد باشد!")

async def show_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """نمایش اطلاعات کامل کاربر"""
    user = await mongo_manager.get_user(user_id)
    
    if not user:
        await send_message(update, "❌ کاربر یافت نشد!")
        return
    
    # دریافت آمار کاربر
    stats = await mongo_manager.get_user_stats(user_id)
    activity = await redis_manager.get_user_activity(user_id)
    
    # ایجاد متن اطلاعات
    info_text = f"""
👤 **اطلاعات کاربر**

🆔 **آیدی:** `{user_id}`
📝 **نام:** {user.full_name}
🔖 **یوزرنیم:** @{user.username or 'ندارد'}
💎 **اشتراک:** {user.subscription.value}
📅 **عضویت:** {user.joined_at.strftime('%Y/%m/%d')}
🕐 **آخرین فعالیت:** {user.last_activity.strftime('%Y/%m/%d %H:%M')}

📊 **آمار:**
- کل دانلودها: {user.total_downloads}
- حجم کل: {format_file_size(user.total_size_downloaded)}
- دانلود امروز: {activity.downloads_count}
- دعوت‌ها: {user.referral_count}

🚫 **وضعیت:** {'❌ مسدود' if user.is_banned else '✅ فعال'}
    """
    
    if user.is_banned and user.ban_reason:
        info_text += f"\n📝 **دلیل مسدودیت:** {user.ban_reason}"
    
    # دکمه‌های مدیریت
    buttons = []
    
    if user.is_banned:
        buttons.append([InlineKeyboardButton("✅ رفع مسدودیت", callback_data=f'admin_unban_{user_id}')])
    else:
        buttons.append([InlineKeyboardButton("🚫 مسدود کردن", callback_data=f'admin_ban_{user_id}')])
    
    buttons.extend([
        [
            InlineKeyboardButton("💎 تغییر اشتراک", callback_data=f'admin_change_sub_{user_id}'),
            InlineKeyboardButton("📥 دانلودها", callback_data=f'admin_user_downloads_{user_id}')
        ],
        [
            InlineKeyboardButton("💬 ارسال پیام", callback_data=f'admin_message_user_{user_id}'),
            InlineKeyboardButton("🗑 حذف کاربر", callback_data=f'admin_delete_user_{user_id}')
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='admin_users')]
    ])
    
    await send_message(
        update,
        info_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )

async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش کاربران برتر"""
    query = update.callback_query
    
    # دریافت کاربران برتر
    top_by_downloads = await mongo_manager.get_top_users_by_downloads(limit=10)
    top_by_referrals = await mongo_manager.get_top_users_by_referrals(limit=10)
    
    top_text = "🏆 **کاربران برتر**\n\n"
    
    # برترین‌ها بر اساس دانلود
    top_text += "**📥 بیشترین دانلود:**\n"
    for idx, user in enumerate(top_by_downloads, 1):
        top_text += f"{idx}. {user.get('first_name', 'کاربر')} - {user.get('total_downloads')} دانلود\n"
    
    top_text += "\n**👥 بیشترین دعوت:**\n"
    for idx, user in enumerate(top_by_referrals, 1):
        top_text += f"{idx}. {user.get('first_name', 'کاربر')} - {user.get('referral_count')} نفر\n"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 بازگشت", callback_data='admin_users')
    ]])
    
    await query.message.edit_text(
        top_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@admin_only
@log_action("admin_broadcast")
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /broadcast"""
    await start_broadcast(update, context)

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند پیام همگانی"""
    await send_message(
        update,
        "📢 **ارسال پیام همگانی**\n\n"
        "لطفاً پیام خود را ارسال کنید:\n"
        "(برای لغو: /cancel)",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ لغو", callback_data='admin_panel')
        ]])
    )
    
    return BROADCAST_MESSAGE

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت و تأیید پیام همگانی"""
    message = update.message
    text = message.text
    
    # ذخیره پیام
    context.user_data['broadcast_message'] = text
    
    # دریافت تعداد کاربران
    user_count = await mongo_manager.db.users.count_documents({'is_banned': False})
    
    confirm_text = messages.BROADCAST_CONFIRM.format(
        message=text,
        user_count=user_count
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ارسال", callback_data='confirm_broadcast'),
            InlineKeyboardButton("❌ لغو", callback_data='cancel_broadcast')
        ]
    ])
    
    await message.reply_text(
        confirm_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اجرای پیام همگانی"""
    query = update.callback_query
    message = context.user_data.get('broadcast_message')
    
    if not message:
        await query.answer("❌ پیامی یافت نشد!", show_alert=True)
        return
    
    await query.message.edit_text("⏳ در حال ارسال پیام...")
    
    # دریافت لیست کاربران
    users = await mongo_manager.get_all_active_users()
    
    success_count = 0
    failed_count = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user['user_id'],
                text=message,
                parse_mode='Markdown'
            )
            success_count += 1
            
            # تاخیر برای جلوگیری از محدودیت تلگرام
            await asyncio.sleep(0.05)
            
        except TelegramError as e:
            failed_count += 1
            logger.error(f"Broadcast failed for user {user['user_id']}: {str(e)}")
    
    # گزارش نهایی
    report_text = f"""
✅ **پیام همگانی ارسال شد**

📊 **نتیجه:**
- موفق: {success_count} کاربر
- ناموفق: {failed_count} کاربر
- کل: {success_count + failed_count} کاربر

📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}
    """
    
    await query.message.edit_text(
        report_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 بازگشت", callback_data='admin_panel')
        ]]),
        parse_mode='Markdown'
    )

async def show_finance_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """گزارش مالی"""
    query = update.callback_query
    
    # دریافت آمار مالی
    finance_stats = await mongo_manager.get_finance_statistics()
    
    report_text = f"""
💰 **گزارش مالی**

**📊 درآمد:**
- امروز: {finance_stats['today_revenue']:,} تومان
- این هفته: {finance_stats['week_revenue']:,} تومان
- این ماه: {finance_stats['month_revenue']:,} تومان
- کل: {finance_stats['total_revenue']:,} تومان

**💳 تراکنش‌ها:**
- امروز: {finance_stats['today_transactions']}
- این ماه: {finance_stats['month_transactions']}
- کل: {finance_stats['total_transactions']}

**📈 به تفکیک پلن:**
- برنزی: {finance_stats['bronze_revenue']:,} تومان ({finance_stats['bronze_count']} فروش)
- نقره‌ای: {finance_stats['silver_revenue']:,} تومان ({finance_stats['silver_count']} فروش)
- طلایی: {finance_stats['gold_revenue']:,} تومان ({finance_stats['gold_count']} فروش)

**📉 نرخ تبدیل:**
- بازدیدکننده به کاربر: {finance_stats['conversion_rate']:.1f}%
- کاربر رایگان به پرمیوم: {finance_stats['premium_conversion']:.1f}%

📅 آخرین بروزرسانی: {datetime.now().strftime('%Y/%m/%d %H:%M')}
    """
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 دانلود گزارش", callback_data='admin_download_finance'),
            InlineKeyboardButton("🔄 بروزرسانی", callback_data='admin_finance')
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='admin_panel')]
    ])
    
    await query.message.edit_text(
        report_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@admin_only
async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور تنظیم حالت تعمیر و نگهداری"""
    if not context.args:
        # نمایش وضعیت فعلی
        maintenance_data = await redis_manager.client.get("maintenance_mode")
        if maintenance_data:
            data = json.loads(maintenance_data)
            status = "✅ فعال" if data.get('enabled') else "❌ غیرفعال"
            await update.message.reply_text(
                f"🛠 **حالت تعمیر و نگهداری:** {status}\n\n"
                f"برای تغییر: `/maintenance on [زمان]` یا `/maintenance off`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("🛠 حالت تعمیر و نگهداری: ❌ غیرفعال")
        return
    
    action = context.args[0].lower()
    
    if action == 'on':
        estimated_time = ' '.join(context.args[1:]) if len(context.args) > 1 else "نامشخص"
        maintenance_data = {
            'enabled': True,
            'started_at': datetime.now().isoformat(),
            'estimated_time': estimated_time,
            'admin_id': update.effective_user.id
        }
        await redis_manager.client.setex(
            "maintenance_mode",
            86400,  # 24 ساعت
            json.dumps(maintenance_data)
        )
        await update.message.reply_text(
            f"✅ حالت تعمیر و نگهداری فعال شد.\n"
            f"زمان تقریبی: {estimated_time}"
        )
    
    elif action == 'off':
        await redis_manager.client.delete("maintenance_mode")
        await update.message.reply_text("✅ حالت تعمیر و نگهداری غیرفعال شد.")
    
    else:
        await update.message.reply_text("❌ دستور نامعتبر. از `on` یا `off` استفاده کنید.")

async def create_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ایجاد بکاپ از دیتابیس"""
    query = update.callback_query
    await query.answer("در حال ایجاد بکاپ...")
    
    try:
        from ..tasks.maintenance_tasks import backup_database
        
        # اجرای task بکاپ
        result = backup_database.delay()
        backup_info = result.get(timeout=60)  # 1 دقیقه timeout
        
        if backup_info.get('success'):
            await query.message.reply_document(
                document=open(backup_info['file_path'], 'rb'),
                caption=f"✅ **بکاپ دیتابیس**\n\n"
                        f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
                        f"📦 حجم: {format_file_size(backup_info['size'])}\n"
                        f"📊 رکوردها: {backup_info['records']:,}",
                parse_mode='Markdown'
            )
            
            # حذف فایل موقت
            os.remove(backup_info['file_path'])
        else:
            await query.message.reply_text("❌ خطا در ایجاد بکاپ!")
            
    except Exception as e:
        logger.error(f"Backup error: {str(e)}")
        await query.message.reply_text("❌ خطا در ایجاد بکاپ!")

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ری‌استارت بات"""
    query = update.callback_query
    
    confirm_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله", callback_data='confirm_restart'),
            InlineKeyboardButton("❌ خیر", callback_data='admin_panel')
        ]
    ])
    
    await query.message.edit_text(
        "⚠️ **ری‌استارت بات**\n\n"
        "آیا مطمئن هستید؟\n"
        "این عملیات باعث قطع موقت سرویس می‌شود.",
        reply_markup=confirm_keyboard,
        parse_mode='Markdown'
    )

async def confirm_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأیید و اجرای ری‌استارت"""
    query = update.callback_query
    
    await query.message.edit_text("🔄 در حال ری‌استارت...")
    
    # ارسال سیگنال برای ری‌استارت
    logger.info("Bot restart requested by admin")
    
    # می‌توانید از systemd یا supervisor استفاده کنید
    # os.system("sudo systemctl restart telegram-bot")
    
    # یا خروج از برنامه (اگر با auto-restart راه‌اندازی شده)
    import sys
    sys.exit(0)

# Helper functions
async def send_message(update: Update, text: str, **kwargs):
    """ارسال یا ویرایش پیام"""
    if update.callback_query:
        await update.callback_query.message.edit_text(text, **kwargs)
    else:
        await update.message.reply_text(text, **kwargs)

# توابع جدید برای تایید/رد پرداخت
async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: str):
    """تایید پرداخت توسط ادمین"""
    query = update.callback_query
    
    payment = await mongo_manager.get_payment(payment_id)
    if not payment:
        await query.answer("پرداخت یافت نشد!", show_alert=True)
        return
    
    if payment.status != PaymentStatus.PENDING:
        await query.answer("این پرداخت قبلاً پردازش شده!", show_alert=True)
        return
    
    # تایید پرداخت
    payment.status = PaymentStatus.PAID
    payment.paid_at = datetime.now()
    payment.ref_id = payment.metadata['tracking_code']
    payment.metadata['approved_by'] = query.from_user.id
    payment.metadata['approved_at'] = datetime.now().isoformat()
    
    await mongo_manager.update_payment(payment)
    
    # فعال‌سازی اشتراک
    from ..handlers.payment_handler import handle_successful_payment
    success = await handle_successful_payment(payment.user_id, payment)
    
    if success:
        # اطلاع به کاربر
        from telegram import Bot
        bot = Bot(token=bot_config.token)
        
        plan = subscription_config.plans[payment.subscription_type.value]
        expires_date = (datetime.now() + timedelta(days=30)).strftime('%Y/%m/%d')
        
        await bot.send_message(
            chat_id=payment.user_id,
            text=f"✅ **پرداخت شما تایید شد!**\n\n"
                 f"🎉 اشتراک {plan['name']} فعال شد.\n"
                 f"📅 اعتبار تا: {expires_date}\n"
                 f"📝 کد پیگیری: `{payment.metadata['tracking_code']}`\n\n"
                 f"از خرید شما متشکریم! 💙",
            parse_mode='Markdown'
        )
        
        await query.answer("✅ پرداخت تایید و اشتراک فعال شد")
    else:
        await query.answer("⚠️ پرداخت تایید شد اما خطا در فعال‌سازی اشتراک", show_alert=True)
    
    # حذف دکمه‌ها
    await query.message.edit_reply_markup(None)
    await query.message.reply_text("✅ پرداخت تایید شد.")

async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: str):
    """رد پرداخت توسط ادمین"""
    query = update.callback_query
    
    payment = await mongo_manager.get_payment(payment_id)
    if not payment:
        await query.answer("پرداخت یافت نشد!", show_alert=True)
        return
    
    # رد پرداخت
    payment.status = PaymentStatus.FAILED
    payment.metadata['rejected_by'] = query.from_user.id
    payment.metadata['rejected_at'] = datetime.now().isoformat()
    
    await mongo_manager.update_payment(payment)
    
    # اطلاع به کاربر
    from telegram import Bot
    bot = Bot(token=bot_config.token)
    
    await bot.send_message(
        chat_id=payment.user_id,
        text=f"❌ **پرداخت رد شد**\n\n"
             f"پرداخت شما با کد پیگیری `{payment.metadata['tracking_code']}` رد شد.\n\n"
             f"در صورت واریز وجه، لطفاً با پشتیبانی تماس بگیرید.\n"
             f"@YourSupportBot",
        parse_mode='Markdown'
    )
    
    await query.answer("❌ پرداخت رد شد")
    await query.message.edit_reply_markup(None)
    await query.message.reply_text("❌ پرداخت رد شد.")