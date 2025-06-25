"""
Middleware for enforcing subscription plan limits and features.
"""
from typing import Callable, Awaitable, Dict, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import logging

from database import (
    get_user_subscription,
    SubscriptionPlan,
    record_download,
)
from config import config, PLAN_LIMITS

logger = logging.getLogger(__name__)

class SubscriptionMiddleware:
    """Middleware to enforce subscription plan limits."""
    
    def __init__(self, handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]):
        self.handler = handler

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Skip middleware for commands that don't require subscription checks
        if update.message and update.message.text and update.message.text.startswith('/'):
            command = update.message.text.split(' ')[0].lower()
            if command in ['/start', '/help', 'buy']:
                return await self.handler(update, context)
        
        # Get user ID
        user_id = update.effective_user.id if update.effective_user else None
        if not user_id:
            logger.warning("No user ID in update")
            return await update.message.reply_text(
                "❌ خطا در احراز هویت کاربر. لطفا دوباره تلاش کنید."
            )
        
        # Get user's subscription
        db = next(context.bot_data['db_session_generator']())
        try:
            subscription = get_user_subscription(db, user_id)
            
            if not subscription or not subscription.is_active:
                return await update.message.reply_text(
                    "❌ اشتراک فعالی ندارید. لطفا با استفاده از دستور /buy اشتراک تهیه کنید."
                )
            
            # Check if subscription has expired
            if subscription.end_date and subscription.end_date < datetime.utcnow():
                subscription.is_active = False
                db.commit()
                return await update.message.reply_text(
                    "❌ اشتراک شما به پایان رسیده است. لطفا اشتراک جدید خریداری کنید."
                )
            
            # Store subscription in context for use in handlers
            context.user_data['subscription'] = subscription
            
            # Proceed to the handler
            return await self.handler(update, context)
            
        except Exception as e:
            logger.error(f"Error in subscription middleware: {e}", exc_info=True)
            return await update.message.reply_text(
                "❌ خطایی در بررسی اشتراک شما رخ داد. لطفا دوباره تلاش کنید."
            )
        finally:
            db.close()

class DownloadLimitMiddleware:
    """Middleware to enforce download limits based on subscription plan."""
    
    def __init__(self, handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]):
        self.handler = handler

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Only process messages that might contain download requests
        if not update.message or not update.message.text:
            return await self.handler(update, context)
            
        user_id = update.effective_user.id
        db = next(context.bot_data['db_session_generator']())
        
        try:
            # Get user's subscription
            subscription = get_user_subscription(db, user_id)
            if not subscription:
                return await update.message.reply_text(
                    "❌ اشتراک فعالی ندارید. لطفا با استفاده از دستور /buy اشتراک تهیه کنید."
                )
            
            # Check if user can download
            can_download, reason = self._can_download(subscription)
            if not can_download:
                return await update.message.reply_text(f"❌ {reason}")
            
            # Proceed to the download handler
            return await self.handler(update, context)
            
        except Exception as e:
            logger.error(f"Error in download limit middleware: {e}", exc_info=True)
            return await update.message.reply_text(
                "❌ خطایی در بررسی محدودیت‌های دانلود رخ داد. لطفا دوباره تلاش کنید."
            )
        finally:
            db.close()
    
    def _can_download(self, subscription) -> tuple[bool, Optional[str]]:
        """Check if user can download based on their subscription."""
        plan_limits = PLAN_LIMITS.get(subscription.plan, {})
        
        # Reset daily downloads if needed
        now = datetime.utcnow()
        if subscription.last_download_reset.date() < now.date():
            subscription.daily_downloads_used = 0
            subscription.last_download_reset = now
        
        # Check daily download limit
        if (subscription.plan != SubscriptionPlan.GOLD and 
            subscription.daily_downloads_used >= plan_limits.get("daily_downloads", 0)):
            return False, "تعداد دانلود روزانه شما به پایان رسیده است. لطفا اشتراک خود را ارتقا دهید."
        
        return True, None

def setup_middlewares(application):
    """Set up all middleware for the application."""
    # Wrap handlers with middleware
    for handler in application.handlers[0]:
        # Skip command handlers that don't need middleware
        if any(cmd in ['start', 'help', 'buy'] for cmd in handler.commands):
            continue
            
        # Apply middleware to message handlers
        if hasattr(handler, 'filters') and handler.filters is not None:
            original_callback = handler.callback
            
            # Create middleware chain
            async def middleware_chain(update, context, handler=original_callback):
                # Create inner function for middleware composition
                async def inner(update, context):
                    return await handler(update, context)
                
                # Apply middleware in order
                wrapped = SubscriptionMiddleware(inner)
                wrapped = DownloadLimitMiddleware(wrapped)
                return await wrapped(update, context)
            
            # Replace the original callback with the middleware chain
            handler.callback = lambda update, context, mw_chain=middleware_chain: mw_chain(update, context)
