from datetime import datetime, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from ..database.mongo_client import mongo_manager
from ..database.models import Payment, PaymentStatus, SubscriptionType
from ..config import subscription_config, bot_config
from ..services.card_payment import CardToCardPayment
from ..utils import messages, keyboards
from ..utils.decorators import track_user, log_action, typing_action

# Instance از سیستم کارت به کارت
card_payment_system = CardToCardPayment()

@track_user
@log_action("subscription")
@typing_action
async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پلن‌های اشتراک"""
    await update.message.reply_text(
        messages.SUBSCRIPTION_PLANS,
        reply_markup=keyboards.Keyboards.subscription_plans(),
        parse_mode='Markdown'
    )

async def handle_buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_key: str):
    """مدیریت خرید پلن - مستقیم به کارت به کارت"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # بررسی پلن
    if plan_key not in subscription_config.plans:
        await query.answer("پلن نامعتبر است!", show_alert=True)
        return
    
    plan = subscription_config.plans[plan_key]
    
    # ایجاد پرداخت
    try:
        payment = Payment(
            user_id=user_id,
            amount=plan['price'],
            subscription_type=SubscriptionType(plan_key),
            description=f"خرید اشتراک {plan['name']}"
        )
        
        # ایجاد اطلاعات پرداخت کارت به کارت
        payment_info = await card_payment_system.create_payment_info(payment)
        
        # ذخیره پرداخت در دیتابیس
        payment = await mongo_manager.create_payment(payment)
        
        # تولید تصویر پرداخت
        payment_image = await card_payment_system.generate_payment_image(payment_info)
        
        if payment_image:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "✅ پرداخت کردم", 
                    callback_data=f"confirm_payment_{payment._id}"
                )],
                [InlineKeyboardButton(
                    "❌ انصراف", 
                    callback_data=f"cancel_payment_{payment._id}"
                )]
            ])
            
            await query.message.delete()
            await query.message.reply_photo(
                photo=payment_image,
                caption=f"💳 **فاکتور پرداخت**\n\n"
                       f"📦 پلن: {plan['name']}\n"
                       f"⏰ مهلت پرداخت: 30 دقیقه\n\n"
                       f"لطفاً پس از واریز وجه، دکمه «پرداخت کردم» را بزنید.",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            # نمایش متنی در صورت خطا در تولید تصویر
            await show_text_payment_info(query, payment, payment_info)
            
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        await query.answer("خطا در ایجاد فاکتور پرداخت!", show_alert=True)

async def show_text_payment_info(query, payment: Payment, payment_info: dict):
    """نمایش اطلاعات پرداخت به صورت متن"""
    card = payment_info['card']
    
    text = f"""
💳 **فاکتور پرداخت کارت به کارت**

💰 **مبلغ:** `{payment.amount:,}` تومان

🏦 **اطلاعات حساب:**
شماره کارت: `{card['number']}`
صاحب حساب: {card['owner']}
بانک: {card['bank']}

📝 **کد پیگیری:** `{payment_info['tracking_code']}`

⏰ **مهلت پرداخت:** 30 دقیقه

⚠️ **توجه:**
- مبلغ را دقیقاً به همین شماره کارت واریز کنید
- کد پیگیری را یادداشت کنید
- پس از واریز دکمه «پرداخت کردم» را بزنید
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ پرداخت کردم", 
            callback_data=f"confirm_payment_{payment._id}"
        )],
        [InlineKeyboardButton(
            "❌ انصراف", 
            callback_data=f"cancel_payment_{payment._id}"
        )]
    ])
    
    await query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def handle_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: str):
    """تایید پرداخت توسط کاربر"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # دریافت پرداخت
    payment = await mongo_manager.get_payment(payment_id)
    
    if not payment:
        await query.answer("پرداخت یافت نشد!", show_alert=True)
        return
    
    if payment.user_id != user_id:
        await query.answer("این پرداخت متعلق به شما نیست!", show_alert=True)
        return
    
    if payment.status != PaymentStatus.PENDING:
        await query.answer("این پرداخت قبلاً پردازش شده است!", show_alert=True)
        return
    
    # بررسی انقضا
    expires_at = datetime.fromisoformat(payment.metadata['expires_at'])
    if datetime.now() > expires_at:
        await query.answer("مهلت پرداخت منقضی شده است!", show_alert=True)
        return
    
    # ثبت تایید کاربر
    payment.metadata['user_confirmed'] = True
    payment.metadata['confirmed_at'] = datetime.now().isoformat()
    await mongo_manager.update_payment(payment)
    
    # ارسال به ادمین برای بررسی
    await send_to_admin_verification(payment, query.from_user)
    
    # پیام به کاربر
    await query.message.edit_caption(
        caption="✅ **درخواست شما ثبت شد**\n\n"
               "پرداخت شما در صف بررسی قرار گرفت.\n"
               "معمولاً بررسی کمتر از 5 دقیقه طول می‌کشد.\n\n"
               f"کد پیگیری: `{payment.metadata['tracking_code']}`\n\n"
               "💡 در صورت تایید، پیام فعال‌سازی دریافت خواهید کرد.",
        parse_mode='Markdown'
    )

async def send_to_admin_verification(payment: Payment, user):
    """ارسال پرداخت به ادمین‌ها برای تایید"""
    from telegram import Bot
    bot = Bot(token=bot_config.token)
    
    # اطلاعات کاربر
    user_info = await mongo_manager.get_user(payment.user_id)
    
    text = f"""
🔔 **پرداخت جدید در انتظار تایید**

👤 **کاربر:**
- نام: {user.full_name}
- یوزرنیم: @{user.username or 'ندارد'}
- آیدی: `{user.id}`
- تعداد خرید قبلی: {user_info.metadata.get('purchase_count', 0)}

💰 **اطلاعات پرداخت:**
- مبلغ: **{payment.amount:,}** تومان
- پلن: {payment.subscription_type.value}
- کد پیگیری: `{payment.metadata['tracking_code']}`
- شماره کارت: `{payment.metadata['card_number']}`

⏰ زمان: {datetime.now().strftime('%Y/%m/%d - %H:%M')}

لطفاً پس از بررسی تراکنش، یکی از گزینه‌ها را انتخاب کنید:
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تایید پرداخت", 
                callback_data=f"admin_approve_{payment._id}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ رد پرداخت", 
                callback_data=f"admin_reject_{payment._id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 مشاهده کاربر", 
                callback_data=f"admin_view_user_{user.id}"
            )
        ]
    ])
    
    # ارسال به همه ادمین‌ها
    for admin_id in bot_config.admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send to admin {admin_id}: {str(e)}")

async def handle_cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: str):
    """لغو پرداخت"""
    query = update.callback_query
    
    payment = await mongo_manager.get_payment(payment_id)
    if payment and payment.user_id == query.from_user.id:
        payment.status = PaymentStatus.FAILED
        payment.metadata['cancelled_by_user'] = True
        await mongo_manager.update_payment(payment)
    
    await query.message.delete()
    await query.answer("پرداخت لغو شد.", show_alert=True)

async def handle_successful_payment(user_id: int, payment: Payment):
    """فعال‌سازی اشتراک پس از تایید پرداخت"""
    try:
        # فعال‌سازی اشتراک
        plan = subscription_config.plans[payment.subscription_type.value]
        duration_days = plan.get('duration_days', 30)
        
        success = await mongo_manager.update_subscription(
            user_id,
            payment.subscription_type,
            duration_days
        )
        
        if success:
            # افزایش تعداد خرید کاربر
            user = await mongo_manager.get_user(user_id)
            purchase_count = user.metadata.get('purchase_count', 0) + 1
            user.metadata['purchase_count'] = purchase_count
            user.metadata['last_purchase'] = datetime.now().isoformat()
            await mongo_manager.update_user(user)
            
            # پاداش معرف
            if user.referrer_id:
                await add_referral_bonus(user.referrer_id)
            
            logger.info(f"Payment {payment._id} activated for user {user_id}")
            return True
            
    except Exception as e:
        logger.error(f"Error activating subscription: {str(e)}")
        return False

async def add_referral_bonus(referrer_id: int):
    """اضافه کردن پاداش معرفی"""
    try:
        # 5 دانلود رایگان
        from ..database.redis_client import redis_manager
        
        key = f"bonus_downloads:{referrer_id}"
        current = await redis_manager.client.get(key)
        current = int(current) if current else 0
        
        await redis_manager.client.setex(
            key,
            86400 * 30,  # 30 روز
            current + 5
        )
        
        # اطلاع‌رسانی
        from telegram import Bot
        bot = Bot(token=bot_config.token)
        
        await bot.send_message(
            chat_id=referrer_id,
            text="🎁 **پاداش معرفی!**\n\n"
                 "یکی از کاربران معرفی شده شما اشتراک خرید.\n"
                 "5 دانلود رایگان به حساب شما اضافه شد! 🎉",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error adding referral bonus: {str(e)}")