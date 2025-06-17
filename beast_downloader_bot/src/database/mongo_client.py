import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel
from bson import ObjectId
from loguru import logger

from ..config import db_config
from .models import User, Download, Payment, Statistics, SubscriptionType, DownloadStatus, PaymentStatus

class MongoManager:
    """مدیریت اتصال و عملیات MongoDB"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        
    async def connect(self):
        """اتصال به MongoDB"""
        try:
            self.client = AsyncIOMotorClient(db_config.mongo_uri)
            self.db = self.client[db_config.mongo_db_name]
            
            # تست اتصال
            await self.client.server_info()
            logger.info("Connected to MongoDB successfully")
            
            # ایجاد ایندکس‌ها
            await self._create_indexes()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """قطع اتصال"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def _create_indexes(self):
        """ایجاد ایندکس‌های مورد نیاز"""
        # ایندکس‌های کاربران
        user_indexes = [
            IndexModel([("user_id", ASCENDING)], unique=True),
            IndexModel([("username", ASCENDING)]),
            IndexModel([("subscription", ASCENDING)]),
            IndexModel([("joined_at", DESCENDING)]),
            IndexModel([("referrer_id", ASCENDING)]),
        ]
        await self.db.users.create_indexes(user_indexes)
        
        # ایندکس‌های دانلودها
        download_indexes = [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("platform", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("task_id", ASCENDING)]),
        ]
        await self.db.downloads.create_indexes(download_indexes)
        
        # ایندکس‌های پرداخت‌ها
        payment_indexes = [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("authority", ASCENDING)], unique=True, sparse=True),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
        await self.db.payments.create_indexes(payment_indexes)
        
        # ایندکس‌های آمار
        stats_indexes = [
            IndexModel([("date", DESCENDING)], unique=True),
        ]
        await self.db.statistics.create_indexes(stats_indexes)
        
        logger.info("Database indexes created successfully")
    
    # ==================== User Methods ====================
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """دریافت کاربر"""
        doc = await self.db.users.find_one({"user_id": user_id})
        return User.from_dict(doc) if doc else None
    
    async def create_user(self, user: User) -> User:
        """ایجاد کاربر جدید"""
        doc = user.to_dict()
        result = await self.db.users.insert_one(doc)
        user._id = result.inserted_id
        
        # بروزرسانی آمار
        await self._increment_daily_stat('new_users', 1)
        
        return user
    
    async def update_user(self, user: User) -> bool:
        """بروزرسانی کاربر"""
        user.last_activity = datetime.now()
        doc = user.to_dict()
        
        result = await self.db.users.update_one(
            {"user_id": user.user_id},
            {"$set": doc}
        )
        return result.modified_count > 0
    
    async def get_or_create_user(self, user_data: dict) -> User:
        """دریافت یا ایجاد کاربر"""
        user = await self.get_user(user_data['user_id'])
        
        if not user:
            user = User(**user_data)
            user = await self.create_user(user)
        else:
            # بروزرسانی اطلاعات
            for key, value in user_data.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)
            await self.update_user(user)
        
        return user
    
    async def update_subscription(self, user_id: int, subscription_type: SubscriptionType, days: int = 30) -> bool:
        """بروزرسانی اشتراک کاربر"""
        expires_at = datetime.now() + timedelta(days=days)
        
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "subscription": subscription_type.value,
                    "subscription_expires": expires_at,
                    "last_activity": datetime.now()
                }
            }
        )
        
        # بروزرسانی آمار
        await self._increment_daily_stat(f'subscription_stats.{subscription_type.value}', 1)
        
        return result.modified_count > 0
    
    async def ban_user(self, user_id: int, reason: str) -> bool:
        """مسدود کردن کاربر"""
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "is_banned": True,
                    "ban_reason": reason,
                    "last_activity": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    
    async def get_user_stats(self, user_id: int) -> dict:
        """آمار کاربر"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$lookup": {
                    "from": "downloads",
                    "let": {"user_id": "$user_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$user_id", "$$user_id"]}}},
                        {
                            "$group": {
                                "_id": "$status",
                                "count": {"$sum": 1},
                                "total_size": {"$sum": "$file_size"}
                            }
                        }
                    ],
                    "as": "download_stats"
                }
            },
            {
                "$lookup": {
                    "from": "payments",
                    "let": {"user_id": "$user_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {"$eq": ["$user_id", "$$user_id"]},
                                "status": PaymentStatus.PAID.value
                            }
                        },
                        {
                            "$group": {
                                "_id": None,
                                "total_payments": {"$sum": 1},
                                "total_amount": {"$sum": "$amount"}
                            }
                        }
                    ],
                    "as": "payment_stats"
                }
            }
        ]
        
        result = await self.db.users.aggregate(pipeline).to_list(1)
        return result[0] if result else {}
    
    # ==================== Download Methods ====================
    
    async def create_download(self, download: Download) -> Download:
        """ایجاد رکورد دانلود"""
        doc = download.to_dict()
        result = await self.db.downloads.insert_one(doc)
        download._id = result.inserted_id
        
        # بروزرسانی آمار
        await self._increment_daily_stat('total_downloads', 1)
        await self._increment_daily_stat(f'platform_stats.{download.platform}', 1)
        
        return download
    
    async def get_download(self, download_id: str) -> Optional[Download]:
        """دریافت دانلود"""
        doc = await self.db.downloads.find_one({"_id": ObjectId(download_id)})
        return Download.from_dict(doc) if doc else None
    
    async def update_download(self, download: Download) -> bool:
        """بروزرسانی دانلود"""
        doc = download.to_dict()
        result = await self.db.downloads.update_one(
            {"_id": download._id},
            {"$set": doc}
        )
        
        # بروزرسانی آمار
        if download.status == DownloadStatus.COMPLETED:
            await self._increment_daily_stat('successful_downloads', 1)
            if download.file_size:
                await self._increment_daily_stat('total_size', download.file_size)
        elif download.status == DownloadStatus.FAILED:
            await self._increment_daily_stat('failed_downloads', 1)
        
        return result.modified_count > 0
    
    async def get_user_downloads(self, user_id: int, limit: int = 10, skip: int = 0) -> List[Download]:
        """دریافت دانلودهای کاربر"""
        cursor = self.db.downloads.find(
            {"user_id": user_id}
        ).sort("created_at", DESCENDING).skip(skip).limit(limit)
        
        downloads = []
        async for doc in cursor:
            downloads.append(Download.from_dict(doc))
        
        return downloads
    
    async def get_active_downloads(self) -> List[Download]:
        """دریافت دانلودهای در حال انجام"""
        cursor = self.db.downloads.find({
            "status": {"$in": [DownloadStatus.PENDING.value, DownloadStatus.PROCESSING.value]}
        }).sort("created_at", ASCENDING)
        
        downloads = []
        async for doc in cursor:
            downloads.append(Download.from_dict(doc))
        
        return downloads
    
    async def cleanup_old_downloads(self, hours: int = 24) -> int:
        """پاکسازی دانلودهای قدیمی"""
        cutoff_date = datetime.now() - timedelta(hours=hours)
        
        result = await self.db.downloads.delete_many({
            "created_at": {"$lt": cutoff_date},
            "status": {"$in": [DownloadStatus.COMPLETED.value, DownloadStatus.FAILED.value]}
        })
        
        return result.deleted_count
    
    # ==================== Payment Methods ====================
    
    async def create_payment(self, payment: Payment) -> Payment:
        """ایجاد پرداخت"""
        doc = payment.to_dict()
        result = await self.db.payments.insert_one(doc)
        payment._id = result.inserted_id
        return payment
    
    async def get_payment_by_authority(self, authority: str) -> Optional[Payment]:
        """دریافت پرداخت با authority"""
        doc = await self.db.payments.find_one({"authority": authority})
        return Payment.from_dict(doc) if doc else None
    
    async def update_payment(self, payment: Payment) -> bool:
        """بروزرسانی پرداخت"""
        doc = payment.to_dict()
        result = await self.db.payments.update_one(
            {"_id": payment._id},
            {"$set": doc}
        )
        
        # بروزرسانی آمار درآمد
        if payment.status == PaymentStatus.PAID:
            await self._increment_daily_stat('revenue', payment.amount)
        
        return result.modified_count > 0
    
    # ==================== Statistics Methods ====================
    
    async def _increment_daily_stat(self, field: str, value: int = 1):
        """افزایش آمار روزانه"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        await self.db.statistics.update_one(
            {"date": today},
            {
                "$inc": {field: value},
                "$setOnInsert": {"date": today}
            },
            upsert=True
        )
    
    async def get_statistics(self, days: int = 7) -> List[Statistics]:
        """دریافت آمار"""
        start_date = datetime.now() - timedelta(days=days)
        
        cursor = self.db.statistics.find(
            {"date": {"$gte": start_date}}
        ).sort("date", DESCENDING)
        
        stats = []
        async for doc in cursor:
            stats.append(Statistics.from_dict(doc))
        
        return stats
    
    async def get_dashboard_stats(self) -> dict:
        """آمار داشبورد ادمین"""
        # آمار کلی
        total_users = await self.db.users.count_documents({})
        active_users = await self.db.users.count_documents({
            "last_activity": {"$gte": datetime.now() - timedelta(days=7)}
        })
        
        # آمار دانلودها
        total_downloads = await self.db.downloads.count_documents({})
        today_downloads = await self.db.downloads.count_documents({
            "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
        })
        
        # آمار اشتراک‌ها
        subscription_stats = {}
        for sub_type in SubscriptionType:
            count = await self.db.users.count_documents({"subscription": sub_type.value})
            subscription_stats[sub_type.value] = count
        
        # درآمد ماه جاری
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pipeline = [
            {
                "$match": {
                    "status": PaymentStatus.PAID.value,
                    "paid_at": {"$gte": month_start}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$amount"}
                }
            }
        ]
        revenue_result = await self.db.payments.aggregate(pipeline).to_list(1)
        monthly_revenue = revenue_result[0]['total'] if revenue_result else 0
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_downloads": total_downloads,
            "today_downloads": today_downloads,
            "subscription_stats": subscription_stats,
            "monthly_revenue": monthly_revenue
        }

# نمونه singleton
mongo_manager = MongoManager()