from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..utils import messages, keyboards
from ..utils.decorators import track_user, log_action, typing_action, maintenance_check
from ..config import bot_config

@track_user
@log_action("start")
@typing_action
@maintenance_check
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start"""
    user = update.effective_user
    args = context.args
    
    # بررسی لینک رفرال
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id != user.id:
            # ثبت رفرال
            referrer = await mongo_manager.get_user(referrer_id)
            if referrer:
                await mongo_manager.update_user_referral(referrer_id, user.id)
                # پیام به معرف
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 کاربر جدیدی با لینک دعوت شما ثبت‌نام کرد!\n"
                             f"👤 {user.first_name}\n\n"
                             f"🎁 شما 5 دانلود رایگان دریافت کردید!"
                    )
                except:
                    pass
    
    # دریافت اطلاعات کاربر از دیتابیس
    db_user = context.user_data.get('db_user')
    if not db_user:
        db_user = await mongo_manager.get_or_create_user({
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'language_code': user.language_code or 'fa',
            'referrer_id': referrer_id
        })
    
    # دریافت آمار روزانه
    activity = await redis_manager.get_user_activity(user.id)
    plan = bot_config.subscription_config.plans[db_user.subscription.value]
    daily_limit = plan['daily_limit'] if plan['daily_limit'] != -1 else '∞'
    
    # ارسال پیام خوش‌آمدگویی
    welcome_text = messages.WELCOME_MESSAGE.format(
        first_name=user.first_name,
        subscription=plan['name'],
        downloads_today=activity.downloads_count,
        daily_limit=daily_limit
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=keyboards.Keyboards.main_menu(),
        parse_mode='Markdown'
    )
    
    # ارسال Reply Keyboard
    await update.message.reply_text(
        "از دکمه‌های زیر استفاده کنید:",
        reply_markup=keyboards.ReplyKeyboards.main_menu()
    )

@track_user
@log_action("help")
@typing_action
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /help"""
    await update.message.reply_text(
        messages.HELP_MESSAGE,
        reply_markup=keyboards.Keyboards.back_button(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

@track_user
@log_action("support")
async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /support"""
    support_text = """
🆘 **پشتیبانی**

برای ارتباط با پشتیبانی از روش‌های زیر استفاده کنید:

📱 **پشتیبانی آنلاین:** @YourSupportBot
📧 **ایمیل:** support@yourdomain.com
📢 **کانال اطلاع‌رسانی:** @YourChannelUsername

⏰ **ساعات پاسخگویی:**
شنبه تا پنج‌شنبه: 9 صبح تا 9 شب
جمعه: 10 صبح تا 6 بعدازظهر

💡 قبل از تماس با پشتیبانی، لطفاً بخش /help را مطالعه کنید.
    """
    
    await update.message.reply_text(
        support_text,
        reply_markup=keyboards.Keyboards.back_button(),
        parse_mode='Markdown'
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی (غیر URL)"""
    text = update.message.text.strip()
    
    # بررسی دکمه‌های Reply Keyboard
    if text == "📥 دانلودهای من":
        await show_my_downloads(update, context)
    elif text == "👤 پروفایل":
        from . import profile_handler
        await profile_handler.profile_command(update, context)
    elif text == "💎 خرید اشتراک":
        from . import payment_handler
        await payment_handler.subscription_command(update, context)
    elif text == "📚 راهنما":
        await help_command(update, context)
    elif text == "🔗 دعوت دوستان":
        await share_bot(update, context)
    else:
        # پیام پیش‌فرض
        await update.message.reply_text(
            "🔗 لطفاً لینک ویدیو را ارسال کنید یا از منو استفاده کنید.",
            reply_markup=keyboards.Keyboards.main_menu()
        )

@track_user
@log_action("my_downloads")
async def show_my_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست دانلودهای کاربر"""
    user_id = update.effective_user.id
    
    # دریافت دانلودهای اخیر
    downloads = await mongo_manager.get_user_downloads(user_id, limit=50)
    
    if not downloads:
        await update.message.reply_text(
            "📭 شما هنوز هیچ دانلودی نداشته‌اید.\n\n"
            "🔗 برای شروع، لینک ویدیو را ارسال کنید!",
            reply_markup=keyboards.Keyboards.main_menu()
        )
        return
    
    # ایجاد صفحه‌بندی
    keyboard = keyboards.Keyboards.user_downloads_pagination(downloads, page=1)
    
    await update.message.reply_text(
        f"📥 **دانلودهای شما** (آخرین 50 مورد)\n\n"
        f"برای مشاهده جزئیات روی هر دانلود کلیک کنید:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@track_user
@log_action("share_bot")
async def share_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اشتراک‌گذاری ربات"""
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    
    share_text = f"""
🎁 **دعوت از دوستان**

با دعوت دوستان خود از مزایای زیر بهره‌مند شوید:

✅ به ازای هر دعوت موفق: **5 دانلود رایگان**
✅ دوست شما: **3 دانلود رایگان اضافه**
✅ تخفیف 10% برای خرید اشتراک (هر دو نفر)

📊 تعداد دعوت‌های شما: **{context.user_data.get('db_user').referral_count}**

🔗 **لینک اختصاصی شما:**
`https://t.me/{bot_username}?start={user.id}`

برای کپی روی لینک کلیک کنید 👆
    """
    
    await update.message.reply_text(
        share_text,
        reply_markup=keyboards.Keyboards.share_bot(bot_username, user.id),
        parse_mode='Markdown'
    )