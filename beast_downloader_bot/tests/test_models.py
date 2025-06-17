import pytest
from datetime import datetime, timedelta
from bson import ObjectId

from src.database.models import (
    User, Download, Payment, Statistics,
    SubscriptionType, DownloadStatus, PaymentStatus
)

class TestUserModel:
    """تست‌های مدل User"""
    
    def test_create_user(self):
        """تست ایجاد کاربر جدید"""
        user = User(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User"
        )
        
        assert user.user_id == 123456789
        assert user.username == "testuser"
        assert user.subscription == SubscriptionType.FREE
        assert user.total_downloads == 0
        assert isinstance(user.joined_at, datetime)
    
    def test_user_full_name(self):
        """تست نام کامل کاربر"""
        user1 = User(user_id=1, first_name="John", last_name="Doe")
        assert user1.full_name == "John Doe"
        
        user2 = User(user_id=2, first_name="Jane")
        assert user2.full_name == "Jane"
        
        user3 = User(user_id=3)
        assert user3.full_name == "User 3"
    
    def test_user_is_premium(self):
        """تست بررسی پرمیوم بودن"""
        # کاربر رایگان
        free_user = User(user_id=1)
        assert free_user.is_premium == False
        
        # کاربر با اشتراک فعال
        premium_user = User(
            user_id=2,
            subscription=SubscriptionType.GOLD,
            subscription_expires=datetime.now() + timedelta(days=30)
        )
        assert premium_user.is_premium == True
        
        # کاربر با اشتراک منقضی شده
        expired_user = User(
            user_id=3,
            subscription=SubscriptionType.SILVER,
            subscription_expires=datetime.now() - timedelta(days=1)
        )
        assert expired_user.is_premium == False
    
    def test_user_to_dict(self):
        """تست تبدیل به دیکشنری"""
        user = User(
            user_id=123,
            username="test",
            subscription=SubscriptionType.BRONZE
        )
        
        data = user.to_dict()
        assert data['user_id'] == 123
        assert data['username'] == "test"
        assert data['subscription'] == "bronze"
        assert 'joined_at' in data
    
    def test_user_from_dict(self):
        """تست ایجاد از دیکشنری"""
        data = {
            'user_id': 456,
            'username': 'fromdict',
            'subscription': 'silver',
            'total_downloads': 10,
            'joined_at': datetime.now()
        }
        
        user = User.from_dict(data)
        assert user.user_id == 456
        assert user.username == 'fromdict'
        assert user.subscription == SubscriptionType.SILVER
        assert user.total_downloads == 10

class TestDownloadModel:
    """تست‌های مدل Download"""
    
    def test_create_download(self):
        """تست ایجاد دانلود"""
        download = Download(
            user_id=123,
            url="https://youtube.com/watch?v=test",
            platform="youtube",
            title="Test Video"
        )
        
        assert download.user_id == 123
        assert download.platform == "youtube"
        assert download.status == DownloadStatus.PENDING
        assert download.progress == 0
    
    def test_download_is_completed(self):
        """تست بررسی تکمیل دانلود"""
        download = Download(user_id=1, url="test", platform="test")
        assert download.is_completed == False
        
        download.status = DownloadStatus.COMPLETED
        assert download.is_completed == True
    
    def test_download_time_calculation(self):
        """تست محاسبه زمان دانلود"""
        download = Download(user_id=1, url="test", platform="test")
        assert download.download_time is None
        
        download.started_at = datetime.now()
        download.completed_at = download.started_at + timedelta(seconds=30)
        assert download.download_time == 30

class TestPaymentModel:
    """تست‌های مدل Payment"""
    
    def test_create_payment(self):
        """تست ایجاد پرداخت"""
        payment = Payment(
            user_id=123,
            amount=50000,
            subscription_type=SubscriptionType.BRONZE
        )
        
        assert payment.user_id == 123
        assert payment.amount == 50000
        assert payment.subscription_type == SubscriptionType.BRONZE
        assert payment.status == PaymentStatus.PENDING
    
    def test_payment_serialization(self):
        """تست سریال‌سازی پرداخت"""
        payment = Payment(
            user_id=123,
            amount=100000,
            subscription_type=SubscriptionType.SILVER,
            authority="TEST123"
        )
        
        data = payment.to_dict()
        assert data['user_id'] == 123
        assert data['amount'] == 100000
        assert data['subscription_type'] == 'silver'
        assert data['authority'] == 'TEST123'
        
        # بازسازی از دیکشنری
        payment2 = Payment.from_dict(data)
        assert payment2.user_id == payment.user_id
        assert payment2.amount == payment.amount

class TestStatisticsModel:
    """تست‌های مدل Statistics"""
    
    def test_create_statistics(self):
        """تست ایجاد آمار"""
        stats = Statistics(
            date=datetime.now(),
            total_users=100,
            new_users=5,
            total_downloads=50
        )
        
        assert stats.total_users == 100
        assert stats.new_users == 5
        assert stats.total_downloads == 50
        assert stats.revenue == 0
    
    def test_statistics_with_platform_stats(self):
        """تست آمار با اطلاعات پلتفرم"""
        stats = Statistics(
            date=datetime.now(),
            platform_stats={
                'youtube': 30,
                'instagram': 20,
                'twitter': 10
            }
        )
        
        assert stats.platform_stats['youtube'] == 30
        assert stats.platform_stats['instagram'] == 20
        assert len(stats.platform_stats) == 3

class TestEnums:
    """تست Enum ها"""
    
    def test_subscription_types(self):
        """تست انواع اشتراک"""
        assert SubscriptionType.FREE.value == "free"
        assert SubscriptionType.BRONZE.value == "bronze"
        assert SubscriptionType.SILVER.value == "silver"
        assert SubscriptionType.GOLD.value == "gold"
        
        # مقایسه
        assert SubscriptionType.GOLD.value > SubscriptionType.FREE.value
    
    def test_download_status(self):
        """تست وضعیت‌های دانلود"""
        assert DownloadStatus.PENDING.value == "pending"
        assert DownloadStatus.PROCESSING.value == "processing"
        assert DownloadStatus.COMPLETED.value == "completed"
        assert DownloadStatus.FAILED.value == "failed"
        assert DownloadStatus.CANCELLED.value == "cancelled"
    
    def test_payment_status(self):
        """تست وضعیت‌های پرداخت"""
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.PAID.value == "paid"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.REFUNDED.value == "refunded"