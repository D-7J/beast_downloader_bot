from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..config import subscription_config
from ..utils import messages, keyboards
from ..utils.decorators import track_user, log_action, typing_action
from ..utils.helpers import format_time_ago

@track_user
@log_action("profile")
@typing_action
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /profile"""
    await show_profile(update, context)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پروفایل کاربر"""
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    # دریافت اطلاعات کاربر
    user = await mongo_manager.get_user(user_id)
    if not user:
        await send_or_edit_message(
            update,
            "❌ خطا در دریافت اطلاعات کاربر!",
            reply_markup=keyboards.Keyboards.main_menu()
        )
        return
    
    # دریافت آمار کاربر
    user_stats = await mongo_manager.get_user_stats(user_id)
    
    # دریافت فعالیت امروز
    activity = await redis_manager.get_user_activity(user_id)
    
    # اطلاعات اشتراک
    plan = subscription_config.plans[user.subscription.value]
    daily_limit = plan['daily_limit'] if plan['daily_limit'] != -1 else '∞'
    concurrent_limit = plan['concurrent_downloads']
    
    # محاسبه آمار دانلودها
    download_stats = user_stats.get('download_stats', [])
    total_downloads = sum(stat.get('count', 0) for stat in download_stats)
    successful_downloads = next((stat.get('count', 0) for stat in download_stats if stat['_id'] == 'completed'), 0)
    failed_downloads = next((stat.get('count', 0) for stat in download_stats if stat['_id'] == 'failed'), 0)
    
    # محاسبه حجم کل
    total_size = sum(stat.get('total_size', 0) for stat in download_stats if stat.get('total_size'))
    
    # زمان انقضای اشتراک
    subscription_expires = 'نامحدود' if not user.subscription_expires else user.subscription_expires.strftime('%Y/%m/%d')
    if user.subscription_expires and user.subscription_expires < datetime.now():
        subscription_expires = f"منقضی شده ({user.subscription_expires.strftime('%Y/%m/%d')})"
    
    # دریافت username بات
    bot_username = (await context.bot.get_me()).username
    
    # ایجاد متن پروفایل
    profile_text = messages.USER_PROFILE.format(
        user_id=user_id,
        joined_date=user.joined_at.strftime('%Y/%m/%d'),
        subscription=plan['name'],
        subscription_expires=subscription_expires,
        total_downloads=total_downloads,
        total_size=messages.format_file_size(total_size),
        referral_score=user.referral_count * 5,  # هر دعوت 5 امتیاز
        referral_count=user.referral_count,
        downloads_today=activity.downloads_count,
        daily_limit=daily_limit,
        size_today=messages.format_file_size(activity.total_size),
        concurrent_downloads=await redis_manager.client.get(f"concurrent:{user_id}") or 0,
        concurrent_limit=concurrent_limit,
        bot_username=bot_username
    )
    
    # دکمه‌های پروفایل
    profile_keyboard = create_profile_keyboard(user)
    
    await send_or_edit_message(
        update,
        profile_text,
        reply_markup=profile_keyboard,
        parse_mode='Markdown'
    )

def create_profile_keyboard(user) -> InlineKeyboardMarkup:
    """ایجاد کیبورد پروفایل"""
    buttons = []
    
    # دکمه ارتقا اشتراک
    if user.subscription.value == 'free' or (user.subscription_expires and user.subscription_expires < datetime.now()):
        buttons.append([
            InlineKeyboardButton("💎 ارتقای اشتراک", callback_data='subscription')
        ])
    elif user.subscription_expires:
        # دکمه تمدید اشتراک
        days_left = (user.subscription_expires - datetime.now()).days
        if days_left <= 7:
            buttons.append([
                InlineKeyboardButton(f"🔄 تمدید اشتراک ({days_left} روز مانده)", callback_data='subscription')
            ])
    
    # سایر دکمه‌ها
    buttons.extend([
        [
            InlineKeyboardButton("📊 آمار دقیق", callback_data='detailed_stats'),
            InlineKeyboardButton("🎁 دعوت دوستان", callback_data='referral_info')
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات", callback_data='user_settings'),
            InlineKeyboardButton("📥 دانلودهای من", callback_data='my_downloads')
        ],
        [
            InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')
        ]
    ])
    
    return InlineKeyboardMarkup(buttons)

async def show_detailed_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار دقیق کاربر"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # دریافت آمار از MongoDB
    stats = await mongo_manager.get_user_detailed_stats(user_id)
    
    # آمار به تفکیک پلتفرم
    platform_stats = stats.get('platform_stats', {})
    platform_text = ""
    for platform, data in platform_stats.items():
        platform_text += f"• {platform}: {data['count']} دانلود ({messages.format_file_size(data['size'])})\n"
    
    # آمار به تفکیک ماه
    monthly_stats = stats.get('monthly_stats', [])
    monthly_text = ""
    for month_data in monthly_stats[-6:]:  # 6 ماه اخیر
        month = month_data['_id']
        monthly_text += f"• {month}: {month_data['count']} دانلود\n"
    
    # آمار به تفکیک فرمت
    format_stats = stats.get('format_stats', {})
    format_text = ""
    for fmt, count in format_stats.items():
        format_text += f"• {fmt.upper()}: {count} فایل\n"
    
    detailed_text = f"""
📊 **آمار دقیق حساب شما**

**📅 آمار کلی:**
• عضویت: {format_time_ago(stats['joined_at'])}
• کل دانلودها: {stats['total_downloads']}
• حجم کل: {messages.format_file_size(stats['total_size'])}
• میانگین روزانه: {stats['daily_average']:.1f} دانلود

**🌐 به تفکیک پلتفرم:**
{platform_text or '• هنوز دانلودی نداشته‌اید'}

**📈 آمار ماهانه (6 ماه اخیر):**
{monthly_text or '• هنوز دانلودی نداشته‌اید'}

**📁 به تفکیک فرمت:**
{format_text or '• هنوز دانلودی نداشته‌اید'}

**⏱ زمان‌های اوج فعالیت:**
• بیشترین ساعت: {stats.get('peak_hour', 'نامشخص')}
• بیشترین روز هفته: {stats.get('peak_day', 'نامشخص')}
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 نمودار آمار", callback_data='stats_chart')],
        [InlineKeyboardButton("🔙 بازگشت به پروفایل", callback_data='profile')]
    ])
    
    await query.message.edit_text(
        detailed_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def show_referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش اطلاعات دعوت دوستان"""
    query = update.callback_query
    user = await mongo_manager.get_user(query.from_user.id)
    
    # دریافت لیست کاربران دعوت شده
    referred_users = await mongo_manager.get_referred_users(query.from_user.id)
    
    # محاسبه امتیازات
    total_score = user.referral_count * 5
    used_score = user.metadata.get('used_referral_score', 0)
    available_score = total_score - used_score
    
    # لیست کاربران دعوت شده
    referred_list = ""
    for idx, referred in enumerate(referred_users[:10], 1):  # حداکثر 10 نفر
        status = "✅ فعال" if referred.get('is_active') else "⏳ غیرفعال"
        referred_list += f"{idx}. {referred.get('first_name', 'کاربر')} - {status}\n"
    
    if user.referral_count > 10:
        referred_list += f"\n... و {user.referral_count - 10} نفر دیگر"
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={query.from_user.id}"
    
    referral_text = f"""
🎁 **سیستم دعوت دوستان**

**📊 آمار شما:**
• تعداد دعوت‌ها: {user.referral_count} نفر
• امتیاز کل: {total_score}
• امتیاز استفاده شده: {used_score}
• امتیاز قابل استفاده: {available_score}

**🎯 مزایای دعوت:**
✅ به ازای هر دعوت موفق:
  • شما: 5 دانلود رایگان
  • دوست شما: 3 دانلود رایگان
  • تخفیف 10% برای خرید اشتراک (هر دو)

**👥 کاربران دعوت شده:**
{referred_list or "هنوز کسی را دعوت نکرده‌اید"}

**🔗 لینک اختصاصی شما:**
`{referral_link}`

برای کپی روی لینک کلیک کنید 👆
    """
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 اشتراک‌گذاری", 
                url=f"https://t.me/share/url?url={referral_link}&text=🤖 با این ربات فوق‌العاده می‌تونی از یوتیوب، اینستاگرام و +50 سایت دیگه ویدیو دانلود کنی!"),
            InlineKeyboardButton("📋 کپی لینک", callback_data='copy_referral_link')
        ],
        [InlineKeyboardButton("🎁 استفاده از امتیاز", callback_data='use_referral_score')],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='profile')]
    ])
    
    await query.message.edit_text(
        referral_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def show_user_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش تنظیمات کاربر"""
    query = update.callback_query
    user = await mongo_manager.get_user(query.from_user.id)
    
    # تنظیمات فعلی
    settings = user.settings or {}
    
    settings_text = """
⚙️ **تنظیمات حساب**

انتخاب کنید:
    """
    
    # ایجاد دکمه‌های تنظیمات
    buttons = []
    
    # کیفیت پیش‌فرض
    current_quality = settings.get('default_quality', 'بهترین')
    buttons.append([
        InlineKeyboardButton(
            f"🎥 کیفیت پیش‌فرض: {current_quality}",
            callback_data='setting_quality'
        )
    ])
    
    # زبان
    current_lang = settings.get('language', 'fa')
    lang_name = {'fa': 'فارسی', 'en': 'English'}.get(current_lang, 'فارسی')
    buttons.append([
        InlineKeyboardButton(
            f"🌐 زبان: {lang_name}",
            callback_data='setting_language'
        )
    ])
    
    # اعلان‌ها
    notifications = settings.get('notifications', True)
    notif_status = "✅ فعال" if notifications else "❌ غیرفعال"
    buttons.append([
        InlineKeyboardButton(
            f"🔔 اعلان‌ها: {notif_status}",
            callback_data='setting_notifications'
        )
    ])
    
    # حذف واترمارک (فقط برای کاربران پرمیوم)
    if user.subscription.value != 'free':
        watermark = settings.get('add_watermark', False)
        watermark_status = "✅ با واترمارک" if watermark else "❌ بدون واترمارک"
        buttons.append([
            InlineKeyboardButton(
                f"💧 واترمارک: {watermark_status}",
                callback_data='setting_watermark'
            )
        ])
    
    # حذف حساب
    buttons.extend([
        [InlineKeyboardButton("🗑 حذف حساب", callback_data='delete_account')],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='profile')]
    ])
    
    await query.message.edit_text(
        settings_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )

async def update_user_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, setting: str):
    """بروزرسانی تنظیمات کاربر"""
    query = update.callback_query
    user_id = query.from_user.id
    
    user = await mongo_manager.get_user(user_id)
    settings = user.settings or {}
    
    if setting == 'quality':
        # تغییر کیفیت پیش‌فرض
        qualities = ['بهترین', '1080p', '720p', '480p']
        current = settings.get('default_quality', 'بهترین')
        current_idx = qualities.index(current) if current in qualities else 0
        new_quality = qualities[(current_idx + 1) % len(qualities)]
        settings['default_quality'] = new_quality
        
        await query.answer(f"کیفیت پیش‌فرض: {new_quality}")
    
    elif setting == 'language':
        # تغییر زبان
        current = settings.get('language', 'fa')
        new_lang = 'en' if current == 'fa' else 'fa'
        settings['language'] = new_lang
        
        lang_name = {'fa': 'فارسی', 'en': 'English'}.get(new_lang)
        await query.answer(f"زبان تغییر یافت: {lang_name}")
    
    elif setting == 'notifications':
        # تغییر وضعیت اعلان‌ها
        current = settings.get('notifications', True)
        settings['notifications'] = not current
        
        status = "فعال" if not current else "غیرفعال"
        await query.answer(f"اعلان‌ها {status} شد")
    
    elif setting == 'watermark':
        # تغییر واترمارک
        current = settings.get('add_watermark', False)
        settings['add_watermark'] = not current
        
        status = "اضافه می‌شود" if not current else "اضافه نمی‌شود"
        await query.answer(f"واترمارک {status}")
    
    # ذخیره تنظیمات
    user.settings = settings
    await mongo_manager.update_user(user)
    
    # بازگشت به صفحه تنظیمات
    await show_user_settings(update, context)

async def handle_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست حذف حساب"""
    query = update.callback_query
    
    confirm_text = """
⚠️ **هشدار: حذف حساب**

با حذف حساب:
• تمام اطلاعات شما حذف خواهد شد
• دانلودهای قبلی از دسترس خارج می‌شوند
• اشتراک فعال لغو می‌شود (بدون بازگشت وجه)
• امتیازات دعوت از بین می‌روند

آیا مطمئن هستید؟
    """
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله، حذف کن", callback_data='confirm_delete_account'),
            InlineKeyboardButton("❌ خیر", callback_data='user_settings')
        ]
    ])
    
    await query.message.edit_text(
        confirm_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def confirm_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأیید و حذف حساب"""
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        # حذف از MongoDB
        await mongo_manager.delete_user(user_id)
        
        # حذف از Redis
        await redis_manager.flush_user_cache(user_id)
        
        # پیام خداحافظی
        await query.message.edit_text(
            "✅ حساب شما با موفقیت حذف شد.\n\n"
            "متأسفیم که می‌روید. امیدواریم دوباره برگردید! 👋"
        )
        
        logger.info(f"User {user_id} deleted their account")
        
    except Exception as e:
        logger.error(f"Error deleting account {user_id}: {str(e)}")
        await query.answer("❌ خطا در حذف حساب. لطفاً با پشتیبانی تماس بگیرید.", show_alert=True)

async def send_or_edit_message(update: Update, text: str, **kwargs):
    """ارسال یا ویرایش پیام بر اساس نوع update"""
    if update.callback_query:
        await update.callback_query.message.edit_text(text, **kwargs)
    else:
        await update.message.reply_text(text, **kwargs)