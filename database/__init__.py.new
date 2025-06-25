"""
Database package for Beast Downloader Bot.

This package contains all database-related code including models, schemas, and CRUD operations.
"""

# Import models to ensure they are registered with SQLAlchemy
from .models import (
    Base,
    engine,
    SessionLocal,
    get_db,
    User,
    Subscription,
    Payment,
    PaymentStatus,
    Download,
    init_db,
)

# Import CRUD operations
from .crud import (
    get_user,
    create_user,
    get_or_create_user,
    get_user_subscription,
    update_subscription_plan,
    record_download,
    create_payment,
    complete_payment,
    get_user_downloads,
    get_user_payments,
    get_all_users,
    get_all_payments,
    get_all_downloads,
)

# Import schemas
from .schemas import (
    SubscriptionPlan,
    PaymentStatus as PaymentStatusEnum,
    UserBase,
    UserCreate,
    UserUpdate,
    UserInDBBase,
    User as UserSchema,
    SubscriptionBase,
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionInDBBase,
    Subscription as SubscriptionSchema,
    PaymentBase,
    PaymentCreate,
    PaymentUpdate,
    PaymentInDBBase,
    Payment as PaymentSchema,
    DownloadBase,
    DownloadCreate,
    DownloadUpdate,
    DownloadInDBBase,
    Download as DownloadSchema,
    UserWithSubscription,
    UserWithDetails,
    PaymentWithSubscription,
    DownloadWithUser,
    PaymentCreateRequest,
    PaymentCompleteRequest,
    DownloadCreateRequest,
    AdminUserStats,
    AdminDashboardStats,
)

__all__ = [
    # Database models
    'Base',
    'engine',
    'SessionLocal',
    'get_db',
    'User',
    'Subscription',
    'Payment',
    'PaymentStatus',
    'Download',
    'init_db',
    
    # CRUD operations
    'get_user',
    'create_user',
    'get_or_create_user',
    'get_user_subscription',
    'update_subscription_plan',
    'record_download',
    'create_payment',
    'complete_payment',
    'get_user_downloads',
    'get_user_payments',
    'get_all_users',
    'get_all_payments',
    'get_all_downloads',
    
    # Enums
    'SubscriptionPlan',
    'PaymentStatusEnum',
    
    # Schemas
    'UserBase',
    'UserCreate',
    'UserUpdate',
    'UserInDBBase',
    'UserSchema',
    'SubscriptionBase',
    'SubscriptionCreate',
    'SubscriptionUpdate',
    'SubscriptionInDBBase',
    'SubscriptionSchema',
    'PaymentBase',
    'PaymentCreate',
    'PaymentUpdate',
    'PaymentInDBBase',
    'PaymentSchema',
    'DownloadBase',
    'DownloadCreate',
    'DownloadUpdate',
    'DownloadInDBBase',
    'DownloadSchema',
    'UserWithSubscription',
    'UserWithDetails',
    'PaymentWithSubscription',
    'DownloadWithUser',
    'PaymentCreateRequest',
    'PaymentCompleteRequest',
    'DownloadCreateRequest',
    'AdminUserStats',
    'AdminDashboardStats',
]
