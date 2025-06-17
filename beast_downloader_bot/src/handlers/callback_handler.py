from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from . import download_handler, payment_handler, profile_handler, admin_handler
from ..utils.decorators import callback_query_handler
from ..utils import messages, keyboards

@callback_query_handler(answer=True)
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت مرکزی callback queries"""
    query = update.callback_query
    data = query.data
    
    try:
        # منوی اصلی
        if data == 'main_menu':
            await handle_main_menu(update, context)
        
        elif data == 'help':
            await handle_help(update, context)
        
        elif data == 'profile':
            await profile_handler.show_profile(update, context)
        
        elif data == 'my_downloads':
            await handle_my_downloads(update, context)
        
        elif data == 'subscription':
            await handle_subscription(update, context)
        
        # دانلود
        elif data.startswith('dl_'):
            await download_handler.handle_download_callback(update, context, data)
        
        elif data == 'cancel_download':
            await handle_cancel_download(update, context)
        
        elif data.startswith(('pause_dl_', 'cancel_dl_', 'status_dl_')):
            await handle_download_action(update, context, data)
        
        # صفحه‌بندی دانلودها
        elif data.startswith('dl_page_'):
            page = int(data.split('_')[2])
            await handle_downloads_page(update, context, page)
        
        elif data.startswith('view_dl_'):
            download_id = data.split('_', 2)[2]
            await handle_view_download(update, context, download_id)
        
        # پرداخت
        elif data.startswith('buy_plan_'):
            plan_key = data.split('_', 2)[2]
            await payment_handler.handle_buy_plan(update, context, plan_key)
        
        elif data.startswith('check_payment_'):
            payment_id = data.split('_', 2)[2]
            await payment_handler.handle_check_payment(update, context, payment_id)
        
        elif data.startswith('cancel_payment_'):
            payment_id = data.split('_', 2)[2]
            await payment_handler.handle_cancel_payment(update, context, payment_id)

        elif data.startswith('confirm_payment_'):
            payment_id = data.split('_', 2)[2]
            await payment_handler.handle_confirm_payment(update, context, payment_id)
        
        # ادمین - callbacks عمومی
        elif data.startswith('admin_'):
            if await is_admin(query.from_user.id):
                # callbacks پرداخت ادمین
                if data.startswith('admin_approve_'):
                    payment_id = data.split('_', 2)[2]
                    await admin_handler.approve_payment(update, context, payment_id)
                elif data.startswith('admin_reject_'):
                    payment_id = data.split('_', 2)[2]
                    await admin_handler.reject_payment(update, context, payment_id)
                elif data.startswith('admin_view_user_'):
                    user_id = int(data.split('_', 3)[3])
                    await admin_handler.show_user_info(update, context, user_id)
                else:
                    # سایر callbacks ادمین
                    await handle_admin_callback(update, context, data)
            else:
                await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        
        # سایر
        elif data == 'copy_referral_link':
            await handle_copy_referral(update, context)
        
        elif data == 'cancel_action':
            await query.message.delete()
        
        elif data == 'noop':
            # No operation - برای دکمه‌های غیرفعال
            pass
        
        else:
            logger.warning(f"Unhandled callback data: {data}")
            await query.answer("⚠️ این دکمه در حال حاضر فعال نیست.")
    
    except Exception as e:
        logger.error(f"Error in callback handler: {str(e)}")
        await query.answer("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.", show_alert=True)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی اصلی"""
    query = update.callback_query
    
    await query.message.edit_text(
        "🏠 منوی اصلی\n\nیک گزینه را انتخاب کنید:",
        reply_markup=keyboards.Keyboards.main_menu()
    )

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش راهنما"""
    query = update.callback_query
    
    await query.message.edit_text(
        messages.HELP_MESSAGE,
        reply_markup=keyboards.Keyboards.back_button(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def handle_my_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش دانلودهای کاربر"""
    query = update.callback_query
    user_id = query.from_user.id
    
    from ..database.mongo_client import mongo_manager
    
    downloads = await mongo_manager.get_user_downloads(user_id, limit=50)
    
    if not downloads:
        await query.message.edit_text(
            "📭 شما هنوز هیچ دانلودی نداشته‌اید.\n\n"
            "🔗 برای شروع، لینک ویدیو را ارسال کنید!",
            reply_markup=keyboards.Keyboards.back_button()
        )
        return
    
    keyboard = keyboards.Keyboards.user_downloads_pagination(downloads, page=1)
    
    await query.message.edit_text(
        f"📥 **دانلودهای شما** (آخرین 50 مورد)\n\n"
        f"برای مشاهده جزئیات روی هر دانلود کلیک کنید:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش صفحه اشتراک"""
    query = update.callback_query
    
    await query.message.edit_text(
        messages.SUBSCRIPTION_PLANS,
        reply_markup=keyboards.Keyboards.subscription_plans(),
        parse_mode='Markdown'
    )

async def handle_cancel_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو دانلود در حال انتخاب"""
    query = update.callback_query
    await query.message.delete()
    await query.answer("❌ انتخاب کیفیت لغو شد.")

async def handle_download_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """مدیریت عملیات دانلود"""
    query = update.callback_query
    parts = data.split('_')
    action = parts[0]
    download_id = '_'.join(parts[2:])  # ممکن است شامل _ باشد
    
    from ..database.mongo_client import mongo_manager
    from ..tasks.download_tasks import cancel_download
    
    if action == 'status':
        # نمایش وضعیت
        download = await mongo_manager.get_download(download_id)
        if download and download.user_id == query.from_user.id:
            status_text = f"""
📊 **وضعیت دانلود**

📹 عنوان: {download.title}
⚡ وضعیت: {download.status.value}
📊 پیشرفت: {download.progress}%
⏱ زمان سپری شده: {download.download_time or 0} ثانیه
📦 حجم: {messages.format_file_size(download.file_size) if download.file_size else 'نامشخص'}
            """
            await query.answer(status_text, show_alert=True)
        else:
            await query.answer("❌ دانلود یافت نشد!", show_alert=True)
    
    elif action == 'cancel':
        # لغو دانلود
        result = cancel_download.delay(download_id, query.from_user.id)
        await query.answer("⏳ در حال لغو دانلود...")
        await query.message.delete()
    
    elif action == 'pause':
        # توقف موقت (در حال حاضر پشتیبانی نمی‌شود)
        await query.answer("⚠️ توقف موقت در حال حاضر پشتیبانی نمی‌شود.", show_alert=True)

async def handle_downloads_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    """نمایش صفحه خاص از دانلودها"""
    query = update.callback_query
    user_id = query.from_user.id
    
    from ..database.mongo_client import mongo_manager
    
    downloads = await mongo_manager.get_user_downloads(user_id, limit=50)
    keyboard = keyboards.Keyboards.user_downloads_pagination(downloads, page=page)
    
    await query.message.edit_reply_markup(keyboard)

async def handle_view_download(update: Update, context: ContextTypes.DEFAULT_TYPE, download_id: str):
    """نمایش جزئیات دانلود"""
    query = update.callback_query
    
    from ..database.mongo_client import mongo_manager
    from ..database.models import DownloadStatus
    
    # جستجو با partial ID
    downloads = await mongo_manager.get_user_downloads(query.from_user.id, limit=50)
    download = None
    
    for dl in downloads:
        if str(dl._id).startswith(download_id):
            download = dl
            break
    
    if not download:
        await query.answer("❌ دانلود یافت نشد!", show_alert=True)
        return
    
    # ایکون وضعیت
    status_icons = {
        DownloadStatus.PENDING: '⏳',
        DownloadStatus.PROCESSING: '📥',
        DownloadStatus.COMPLETED: '✅',
        DownloadStatus.FAILED: '❌',
        DownloadStatus.CANCELLED: '🚫'
    }
    
    detail_text = f"""
{status_icons.get(download.status, '❓')} **جزئیات دانلود**

📹 **عنوان:** {download.title or 'نامشخص'}
🌐 **پلتفرم:** {download.platform}
📊 **وضعیت:** {download.status.value}
📅 **تاریخ:** {download.created_at.strftime('%Y/%m/%d %H:%M')}
    """
    
    if download.file_size:
        detail_text += f"\n📦 **حجم:** {messages.format_file_size(download.file_size)}"
    
    if download.duration:
        detail_text += f"\n⏱ **مدت:** {messages.format_duration(download.duration)}"
    
    if download.download_time:
        detail_text += f"\n⚡ **زمان دانلود:** {download.download_time} ثانیه"
    
    if download.error_message:
        detail_text += f"\n\n❌ **خطا:** {download.error_message}"
    
    # دکمه‌ها
    buttons = []
    
    if download.status == DownloadStatus.COMPLETED and download.file_path:
        # دکمه دانلود مجدد
        from ..database.redis_client import redis_manager
        cached = await redis_manager.get_cached_download_link(str(download._id))
        
        if cached:
            buttons.append([InlineKeyboardButton(
                "📥 دانلود مجدد",
                callback_data=f"redownload_{str(download._id)[:10]}"
            )])
    
    buttons.append([InlineKeyboardButton(
        "🔙 بازگشت",
        callback_data="my_downloads"
    )])
    
    await query.message.edit_text(
        detail_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )

async def handle_copy_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کپی لینک دعوت"""
    query = update.callback_query
    user_id = query.from_user.id
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    await query.answer(
        f"🔗 لینک دعوت:\n{referral_link}\n\n"
        "لینک کپی شد! آن را برای دوستان خود ارسال کنید.",
        show_alert=True
    )

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """مدیریت callback های ادمین"""
    action = data.replace('admin_', '')
    
    if action == 'stats':
        await admin_handler.show_stats(update, context)
    elif action == 'users':
        await admin_handler.show_users_management(update, context)
    elif action == 'broadcast':
        await admin_handler.start_broadcast(update, context)
    elif action == 'finance':
        await admin_handler.show_finance_report(update, context)
    elif action == 'settings':
        await admin_handler.show_settings(update, context)
    elif action == 'restart':
        await admin_handler.restart_bot(update, context)
    elif action == 'backup':
        await admin_handler.create_backup(update, context)
    elif action == 'charts':
        await admin_handler.show_charts(update, context)
    else:
        await update.callback_query.answer("⚠️ عملیات نامشخص")

async def is_admin(user_id: int) -> bool:
    """بررسی ادمین بودن"""
    from ..config import bot_config
    return user_id in bot_config.admin_ids