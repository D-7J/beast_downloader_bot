from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Common schemas
class SubscriptionPlan(str, Enum):
    FREE = "free"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

# User schemas
class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_admin: bool = False

class UserCreate(UserBase):
    pass

class UserUpdate(UserBase):
    pass

class UserInDBBase(UserBase):
    id: int
    join_date: datetime

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

# Subscription schemas
class SubscriptionBase(BaseModel):
    plan: SubscriptionPlan
    start_date: datetime
    end_date: Optional[datetime] = None
    is_active: bool = True
    daily_downloads_used: int = 0

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(SubscriptionBase):
    pass

class SubscriptionInDBBase(SubscriptionBase):
    id: int
    user_id: int
    last_download_reset: datetime

    class Config:
        from_attributes = True

class Subscription(SubscriptionInDBBase):
    pass

# Payment schemas
class PaymentBase(BaseModel):
    user_id: int
    amount: int
    plan: SubscriptionPlan
    status: PaymentStatus = PaymentStatus.PENDING
    transaction_id: Optional[str] = None
    description: Optional[str] = None

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(PaymentBase):
    pass

class PaymentInDBBase(PaymentBase):
    id: int
    payment_date: datetime

    class Config:
        from_attributes = True

class Payment(PaymentInDBBase):
    pass

# Download schemas
class DownloadBase(BaseModel):
    user_id: int
    file_url: str
    file_name: str
    file_size: int
    status: str = "completed"

class DownloadCreate(DownloadBase):
    pass

class DownloadUpdate(DownloadBase):
    pass

class DownloadInDBBase(DownloadBase):
    id: int
    download_date: datetime

    class Config:
        from_attributes = True

class Download(DownloadInDBBase):
    pass

# Response models
class UserWithSubscription(User):
    subscription: Optional[Subscription] = None

class UserWithDetails(User):
    subscription: Optional[Subscription] = None
    downloads: List[Download] = []
    payments: List[Payment] = []

class PaymentWithSubscription(Payment):
    subscription: Subscription

class DownloadWithUser(Download):
    user: User

# Request models
class PaymentCreateRequest(BaseModel):
    user_id: int
    plan: SubscriptionPlan
    amount: int = Field(..., description="Amount in Rials")
    description: Optional[str] = None

class PaymentCompleteRequest(BaseModel):
    payment_id: int
    transaction_id: str

class DownloadCreateRequest(BaseModel):
    user_id: int
    file_url: str
    file_name: str
    file_size: int

# Admin models
class AdminUserStats(BaseModel):
    total_users: int
    active_subscriptions: int
    total_downloads: int
    total_earnings: int

class AdminDashboardStats(AdminUserStats):
    recent_users: List[User]
    recent_payments: List[Payment]
    recent_downloads: List[Download]
