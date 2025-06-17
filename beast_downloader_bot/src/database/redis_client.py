import json
import asyncio
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from loguru import logger

from ..config import db_config, subscription_config
from .models import UserActivity, SubscriptionType

class RedisManager:
    """مدیریت اتصال و عملیات Redis"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
    async def connect(self):
        """اتصال به Redis"""
        try:
            self.client = redis.Redis(
                host=db_config.redis_host,
                port=db_config.redis_port,
                password=db_config.redis_password if db_config.redis_password else None,
                db=db_config.redis_db,
                decode_responses=True
            )
            
            # تست اتصال
            await self.client.ping()
            logger.info("Connected to Redis successfully")
            
            # راه‌اندازی PubSub
            self.pubsub = self.client.pubsub()
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """قطع اتصال"""
        if self.pubsub:
            await self.pubsub.close()
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")
    
    # ==================== User Activity Methods ====================
    
    async def get_user_activity(self, user_id: int, date: Optional[str] = None) -> UserActivity:
        """دریافت فعالیت روزانه کاربر"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        activity = UserActivity(user_id=user_id, date=date)
        key = activity.redis_key
        
        data = await self.client.hgetall(key)
        if data:
            activity.downloads_count = int(data.get('downloads_count', 0))
            activity.total_size = int(data.get('total_size', 0))
            if data.get('last_download'):
                activity.last_download = datetime.fromisoformat(data['last_download'])
        
        return activity
    
    async def increment_user_downloads(self, user_id: int, file_size: int = 0) -> UserActivity:
        """افزایش تعداد دانلود کاربر"""
        date = datetime.now().strftime('%Y-%m-%d')
        activity = UserActivity(user_id=user_id, date=date)
        key = activity.redis_key
        
        # افزایش شمارنده‌ها
        pipe = self.client.pipeline()
        pipe.hincrby(key, 'downloads_count', 1)
        if file_size > 0:
            pipe.hincrby(key, 'total_size', file_size)
        pipe.hset(key, 'last_download', datetime.now().isoformat())
        pipe.expire(key, 86400 * 2)  # نگهداری 2 روز
        
        await pipe.execute()
        
        # دریافت مقادیر جدید
        return await self.get_user_activity(user_id, date)
    
    async def check_user_limit(self, user_id: int, subscription: SubscriptionType) -> tuple[bool, str, Dict[str, Any]]:
        """بررسی محدودیت کاربر"""
        activity = await self.get_user_activity(user_id)
        plan = subscription_config.plans[subscription.value]
        daily_limit = plan['daily_limit']
        
        # بررسی محدودیت روزانه
        if daily_limit != -1 and activity.downloads_count >= daily_limit:
            return False, f"شما به محدودیت روزانه {daily_limit} دانلود رسیده‌اید.", {
                'current': activity.downloads_count,
                'limit': daily_limit,
                'reset_time': self._get_reset_time()
            }
        
        # بررسی محدودیت همزمان
        concurrent_key = f"concurrent:{user_id}"
        current_concurrent = await self.client.get(concurrent_key)
        current_concurrent = int(current_concurrent) if current_concurrent else 0
        concurrent_limit = plan['concurrent_downloads']
        
        if current_concurrent >= concurrent_limit:
            return False, f"شما {current_concurrent} دانلود همزمان دارید. حداکثر مجاز: {concurrent_limit}", {
                'current_concurrent': current_concurrent,
                'concurrent_limit': concurrent_limit
            }
        
        return True, "", {
            'downloads_today': activity.downloads_count,
            'daily_limit': daily_limit,
            'size_today': activity.total_size,
            'concurrent': current_concurrent,
            'concurrent_limit': concurrent_limit
        }
    
    async def set_concurrent_download(self, user_id: int, increment: bool = True) -> int:
        """تنظیم تعداد دانلود همزمان"""
        key = f"concurrent:{user_id}"
        
        if increment:
            value = await self.client.incr(key)
            await self.client.expire(key, 3600)  # 1 ساعت
        else:
            value = await self.client.decr(key)
            if value <= 0:
                await self.client.delete(key)
        
        return max(0, value)
    
    # ==================== Cache Methods ====================
    
    async def cache_video_info(self, url: str, info: dict, ttl: int = 3600) -> None:
        """کش اطلاعات ویدیو"""
        key = f"video_info:{self._hash_url(url)}"
        await self.client.setex(key, ttl, json.dumps(info))
    
    async def get_cached_video_info(self, url: str) -> Optional[dict]:
        """دریافت اطلاعات کش شده"""
        key = f"video_info:{self._hash_url(url)}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def cache_download_link(self, download_id: str, file_info: dict, ttl: int = 3600) -> None:
        """کش لینک دانلود"""
        key = f"download_link:{download_id}"
        await self.client.setex(key, ttl, json.dumps(file_info))
    
    async def get_cached_download_link(self, download_id: str) -> Optional[dict]:
        """دریافت لینک کش شده"""
        key = f"download_link:{download_id}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    # ==================== Rate Limiting ====================
    
    async def check_rate_limit(self, user_id: int, action: str, limit: int, window: int) -> tuple[bool, int]:
        """بررسی rate limit"""
        key = f"rate_limit:{action}:{user_id}"
        current = await self.client.incr(key)
        
        if current == 1:
            await self.client.expire(key, window)
        
        if current > limit:
            ttl = await self.client.ttl(key)
            return False, ttl
        
        return True, 0
    
    # ==================== Queue Methods ====================
    
    async def add_to_download_queue(self, user_id: int, download_data: dict) -> int:
        """اضافه کردن به صف دانلود"""
        # تعیین اولویت بر اساس اشتراک
        subscription = download_data.get('subscription', 'free')
        priority = {
            'gold': 1,
            'silver': 2,
            'bronze': 3,
            'free': 4
        }.get(subscription, 4)
        
        queue_key = f"download_queue:{priority}"
        score = datetime.now().timestamp()
        
        await self.client.zadd(queue_key, {json.dumps(download_data): score})
        
        # دریافت موقعیت در صف
        position = await self.client.zrank(queue_key, json.dumps(download_data))
        return position + 1 if position is not None else 1
    
    async def get_queue_position(self, download_id: str) -> Optional[int]:
        """دریافت موقعیت در صف"""
        for priority in range(1, 5):
            queue_key = f"download_queue:{priority}"
            
            # جستجو در صف
            members = await self.client.zrange(queue_key, 0, -1)
            for i, member in enumerate(members):
                data = json.loads(member)
                if data.get('download_id') == download_id:
                    return i + 1
        
        return None
    
    # ==================== Session Management ====================
    
    async def save_user_session(self, user_id: int, session_data: dict, ttl: int = 86400) -> None:
        """ذخیره session کاربر"""
        key = f"session:{user_id}"
        await self.client.setex(key, ttl, json.dumps(session_data))
    
    async def get_user_session(self, user_id: int) -> Optional[dict]:
        """دریافت session کاربر"""
        key = f"session:{user_id}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def delete_user_session(self, user_id: int) -> None:
        """حذف session کاربر"""
        key = f"session:{user_id}"
        await self.client.delete(key)
    
    # ==================== Stats Methods ====================
    
    async def increment_platform_stats(self, platform: str) -> None:
        """افزایش آمار پلتفرم"""
        today = datetime.now().strftime('%Y-%m-%d')
        key = f"stats:platform:{today}"
        await self.client.hincrby(key, platform, 1)
        await self.client.expire(key, 86400 * 7)  # نگهداری 7 روز
    
    async def get_platform_stats(self, date: Optional[str] = None) -> dict:
        """دریافت آمار پلتفرم‌ها"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        key = f"stats:platform:{date}"
        return await self.client.hgetall(key)
    
    # ==================== Notification Methods ====================
    
    async def publish_download_update(self, user_id: int, download_id: str, data: dict) -> None:
        """انتشار بروزرسانی دانلود"""
        channel = f"download_updates:{user_id}"
        message = {
            'download_id': download_id,
            'timestamp': datetime.now().isoformat(),
            **data
        }
        await self.client.publish(channel, json.dumps(message))
    
    async def subscribe_to_download_updates(self, user_id: int):
        """اشتراک در بروزرسانی‌های دانلود"""
        channel = f"download_updates:{user_id}"
        await self.pubsub.subscribe(channel)
        return self.pubsub
    
    # ==================== Helper Methods ====================
    
    def _hash_url(self, url: str) -> str:
        """هش کردن URL برای استفاده در کلید"""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_reset_time(self) -> str:
        """زمان ریست محدودیت روزانه"""
        tomorrow = datetime.now() + timedelta(days=1)
        reset_time = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        hours_left = (reset_time - datetime.now()).seconds // 3600
        minutes_left = ((reset_time - datetime.now()).seconds % 3600) // 60
        
        return f"{hours_left} ساعت و {minutes_left} دقیقه"
    
    # ==================== Admin Methods ====================
    
    async def get_active_users_count(self) -> int:
        """تعداد کاربران آنلاین"""
        keys = await self.client.keys("session:*")
        return len(keys)
    
    async def get_queue_stats(self) -> dict:
        """آمار صف‌های دانلود"""
        stats = {}
        for priority, name in [(1, 'gold'), (2, 'silver'), (3, 'bronze'), (4, 'free')]:
            queue_key = f"download_queue:{priority}"
            count = await self.client.zcard(queue_key)
            stats[name] = count
        
        return stats
    
    async def flush_user_cache(self, user_id: int) -> int:
        """پاک کردن کش کاربر"""
        pattern = f"*:{user_id}*"
        keys = await self.client.keys(pattern)
        
        if keys:
            return await self.client.delete(*keys)
        return 0

# نمونه singleton
redis_manager = RedisManager()