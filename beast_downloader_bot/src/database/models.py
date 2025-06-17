from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from bson import ObjectId

class SubscriptionType(Enum):
    FREE = "free"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"

class DownloadStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PaymentStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

@dataclass
class User:
    """مدل کاربر"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "fa"
    subscription: SubscriptionType = SubscriptionType.FREE
    subscription_expires: Optional[datetime] = None
    total_downloads: int = 0
    total_size_downloaded: int = 0  # بایت
    joined_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_banned: bool = False
    ban_reason: Optional[str] = None
    referrer_id: Optional[int] = None
    referral_count: int = 0
    settings: Dict[str, Any] = field(default_factory=dict)
    _id: Optional[ObjectId] = None
    
    def to_dict(self) -> dict:
        """تبدیل به دیکشنری برای ذخیره در MongoDB"""
        data = {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'language_code': self.language_code,
            'subscription': self.subscription.value,
            'subscription_expires': self.subscription_expires,
            'total_downloads': self.total_downloads,
            'total_size_downloaded': self.total_size_downloaded,
            'joined_at': self.joined_at,
            'last_activity': self.last_activity,
            'is_banned': self.is_banned,
            'ban_reason': self.ban_reason,
            'referrer_id': self.referrer_id,
            'referral_count': self.referral_count,
            'settings': self.settings
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """ایجاد از دیکشنری MongoDB"""
        data['subscription'] = SubscriptionType(data.get('subscription', 'free'))
        data['_id'] = data.get('_id')
        return cls(**data)
    
    @property
    def full_name(self) -> str:
        """نام کامل کاربر"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts) or f"User {self.user_id}"
    
    @property
    def is_premium(self) -> bool:
        """آیا کاربر اشتراک دارد"""
        if self.subscription == SubscriptionType.FREE:
            return False
        if self.subscription_expires and self.subscription_expires < datetime.now():
            return False
        return True

@dataclass
class Download:
    """مدل دانلود"""
    user_id: int
    url: str
    platform: str  # youtube, instagram, etc.
    title: Optional[str] = None
    duration: Optional[int] = None  # ثانیه
    file_size: Optional[int] = None  # بایت
    format: Optional[str] = None  # mp4, mp3, etc.
    quality: Optional[str] = None  # 720p, 1080p, etc.
    status: DownloadStatus = DownloadStatus.PENDING
    file_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0  # درصد
    speed: Optional[str] = None  # سرعت دانلود
    eta: Optional[int] = None  # زمان باقی‌مانده (ثانیه)
    task_id: Optional[str] = None  # Celery task ID
    metadata: Dict[str, Any] = field(default_factory=dict)
    _id: Optional[ObjectId] = None
    
    def to_dict(self) -> dict:
        data = {
            'user_id': self.user_id,
            'url': self.url,
            'platform': self.platform,
            'title': self.title,
            'duration': self.duration,
            'file_size': self.file_size,
            'format': self.format,
            'quality': self.quality,
            'status': self.status.value,
            'file_path': self.file_path,
            'thumbnail_url': self.thumbnail_url,
            'error_message': self.error_message,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'progress': self.progress,
            'speed': self.speed,
            'eta': self.eta,
            'task_id': self.task_id,
            'metadata': self.metadata
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Download':
        data['status'] = DownloadStatus(data.get('status', 'pending'))
        data['_id'] = data.get('_id')
        return cls(**data)
    
    @property
    def is_completed(self) -> bool:
        return self.status == DownloadStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        return self.status == DownloadStatus.FAILED
    
    @property
    def download_time(self) -> Optional[int]:
        """زمان دانلود (ثانیه)"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

@dataclass
class Payment:
    """مدل پرداخت"""
    user_id: int
    amount: int  # تومان
    subscription_type: SubscriptionType
    status: PaymentStatus = PaymentStatus.PENDING
    authority: Optional[str] = None  # شناسه پرداخت زرین‌پال
    ref_id: Optional[str] = None  # شماره مرجع
    card_pan: Optional[str] = None  # شماره کارت
    created_at: datetime = field(default_factory=datetime.now)
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    _id: Optional[ObjectId] = None
    
    def to_dict(self) -> dict:
        data = {
            'user_id': self.user_id,
            'amount': self.amount,
            'subscription_type': self.subscription_type.value,
            'status': self.status.value,
            'authority': self.authority,
            'ref_id': self.ref_id,
            'card_pan': self.card_pan,
            'created_at': self.created_at,
            'paid_at': self.paid_at,
            'expires_at': self.expires_at,
            'description': self.description,
            'metadata': self.metadata
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Payment':
        data['subscription_type'] = SubscriptionType(data.get('subscription_type', 'free'))
        data['status'] = PaymentStatus(data.get('status', 'pending'))
        data['_id'] = data.get('_id')
        return cls(**data)

@dataclass
class Statistics:
    """آمار روزانه"""
    date: datetime
    total_users: int = 0
    new_users: int = 0
    active_users: int = 0
    total_downloads: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    total_size: int = 0  # بایت
    platform_stats: Dict[str, int] = field(default_factory=dict)
    subscription_stats: Dict[str, int] = field(default_factory=dict)
    revenue: int = 0  # تومان
    _id: Optional[ObjectId] = None
    
    def to_dict(self) -> dict:
        data = {
            'date': self.date,
            'total_users': self.total_users,
            'new_users': self.new_users,
            'active_users': self.active_users,
            'total_downloads': self.total_downloads,
            'successful_downloads': self.successful_downloads,
            'failed_downloads': self.failed_downloads,
            'total_size': self.total_size,
            'platform_stats': self.platform_stats,
            'subscription_stats': self.subscription_stats,
            'revenue': self.revenue
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Statistics':
        data['_id'] = data.get('_id')
        return cls(**data)

@dataclass
class UserActivity:
    """فعالیت کاربر برای محدودیت روزانه"""
    user_id: int
    date: str  # YYYY-MM-DD
    downloads_count: int = 0
    total_size: int = 0  # بایت
    last_download: Optional[datetime] = None
    
    @property
    def redis_key(self) -> str:
        """کلید Redis"""
        return f"activity:{self.user_id}:{self.date}"