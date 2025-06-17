import functools
import asyncio
from typing import Callable, Any, Optional
from datetime import datetime
from telegram import Update, User
from telegram.ext import ContextTypes
from loguru import logger

from ..config import bot_config
from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..database.models import User as UserModel, SubscriptionType
from . import messages

def admin_only(func: Callable) -> Callable:
    """دکوریتور برای محدود کردن دستور به ادمین‌ها"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in bot_config.admin_ids:
            await update.message.reply_text(
                "⛔ این دستور فقط برای ادمین‌ها قابل استفاده است."
            )
            logger.warning(f"Unauthorized admin access attempt by user {user.id if user else 'Unknown'}")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def premium_only(min_subscription: SubscriptionType = SubscriptionType.BRONZE):
    """دکوریتور برای محدود کردن به کاربران پرمیوم"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            user = await mongo_manager.get_user(user_id)
            
            if not user or user.subscription.value < min_subscription.value:
                await update.message.reply_text(
                    f"💎 این قابلیت فقط برای کاربران {min_subscription.value} و بالاتر فعال است.\n\n"
                    "برای ارتقای اشتراک از /subscription استفاده کنید."
                )
                return
            
            if user.subscription_expires and user.subscription_expires < datetime.now():
                await update.message.reply_text(
                    "⏰ اشتراک شما منقضی شده است.\n"
                    "برای تمدید از /subscription استفاده کنید."
                )
                return
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator

def track_user(func: Callable) -> Callable:
    """دکوریتور برای ثبت و بروزرسانی اطلاعات کاربر"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return await func(update, context, *args, **kwargs)
        
        # ایجاد یا بروزرسانی کاربر
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'language_code': user.language_code or 'fa'
        }
        
        db_user = await mongo_manager.get_or_create_user(user_data)
        
        # ذخیره در context برای استفاده در هندلر
        context.user_data['db_user'] = db_user
        
        # بررسی بن بودن
        if db_user.is_banned:
            await update.message.reply_text(
                f"🚫 حساب شما مسدود شده است.\n"
                f"دلیل: {db_user.ban_reason}\n\n"
                f"برای رفع مسدودیت با پشتیبانی تماس بگیرید."
            )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def rate_limit(max_calls: int = 10, window: int = 60):
    """دکوریتور برای محدود کردن تعداد درخواست‌ها"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            action = func.__name__
            
            allowed, ttl = await redis_manager.check_rate_limit(
                user_id, action, max_calls, window
            )
            
            if not allowed:
                await update.message.reply_text(
                    f"⏳ تعداد درخواست‌های شما بیش از حد مجاز است.\n"
                    f"لطفاً {ttl} ثانیه دیگر تلاش کنید."
                )
                return
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator

def log_action(action_type: str = "general"):
    """دکوریتور برای لاگ کردن اکشن‌های کاربر"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            start_time = datetime.now()
            
            try:
                result = await func(update, context, *args, **kwargs)
                
                # لاگ موفقیت
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"Action: {action_type} | "
                    f"User: {user.id if user else 'Unknown'} | "
                    f"Function: {func.__name__} | "
                    f"Duration: {duration:.2f}s | "
                    f"Status: Success"
                )
                
                return result
                
            except Exception as e:
                # لاگ خطا
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Action: {action_type} | "
                    f"User: {user.id if user else 'Unknown'} | "
                    f"Function: {func.__name__} | "
                    f"Duration: {duration:.2f}s | "
                    f"Error: {str(e)}"
                )
                
                # ارسال پیام خطا به کاربر
                try:
                    await update.message.reply_text(
                        "❌ متأسفانه خطایی رخ داد.\n"
                        "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                    )
                except:
                    pass
                
                raise
        
        return wrapper
    return decorator

def maintenance_check(func: Callable) -> Callable:
    """دکوریتور برای بررسی حالت تعمیر و نگهداری"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # بررسی حالت maintenance از Redis
        maintenance_data = await redis_manager.client.get("maintenance_mode")
        
        if maintenance_data:
            data = eval(maintenance_data)  # در حالت واقعی از json استفاده کنید
            if data.get('enabled', False):
                user = update.effective_user
                # ادمین‌ها می‌توانند در حالت maintenance کار کنند
                if user and user.id in bot_config.admin_ids:
                    return await func(update, context, *args, **kwargs)
                
                estimated_time = data.get('estimated_time', 'نامشخص')
                await update.message.reply_text(
                    messages.ERROR_MAINTENANCE.format(estimated_time=estimated_time)
                )
                return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def typing_action(func: Callable) -> Callable:
    """دکوریتور برای نمایش حالت تایپ کردن"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.effective_chat.id
        
        # ارسال typing action
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # اجرای تابع اصلی
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def async_error_handler(func: Callable) -> Callable:
    """دکوریتور برای مدیریت خطاهای async"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except asyncio.CancelledError:
            logger.info(f"Task {func.__name__} was cancelled")
            raise
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {str(e)}")
            # می‌توانید اینجا به Sentry یا سیستم مانیتورینگ دیگر ارسال کنید
            raise
    
    return wrapper

def callback_query_handler(answer: bool = True):
    """دکوریتور برای هندل کردن callback query"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            query = update.callback_query
            
            if answer and query:
                await query.answer()
            
            try:
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in callback handler: {str(e)}")
                if query:
                    await query.answer(
                        "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                        show_alert=True
                    )
                raise
        
        return wrapper
    return decorator

def require_private_chat(func: Callable) -> Callable:
    """دکوریتور برای محدود کردن به چت خصوصی"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type != 'private':
            await update.message.reply_text(
                "🔒 این دستور فقط در چت خصوصی قابل استفاده است.\n"
                "لطفاً در PV ربات این دستور را ارسال کنید."
            )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def measure_performance(func: Callable) -> Callable:
    """دکوریتور برای اندازه‌گیری عملکرد"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = asyncio.get_event_loop().time()
        
        try:
            result = await func(*args, **kwargs)
            duration = asyncio.get_event_loop().time() - start_time
            
            if duration > 1.0:  # اگر بیش از 1 ثانیه طول کشید
                logger.warning(
                    f"Slow function: {func.__name__} took {duration:.2f} seconds"
                )
            
            return result
            
        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            logger.error(
                f"Function {func.__name__} failed after {duration:.2f} seconds: {str(e)}"
            )
            raise
    
    return wrapper