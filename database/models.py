from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Enum,
)
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import enum
from typing import Optional

from config import DATABASE_URL, SubscriptionPlans

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency to get DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    """User model for storing telegram user data"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    join_date = Column(DateTime(timezone=True), server_default=func.now())
    is_admin = Column(Boolean, default=False)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    downloads = relationship("Download", back_populates="user")
    payments = relationship("Payment", back_populates="user")

class Subscription(Base):
    """Subscription model for user subscriptions"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    plan = Column(Enum(SubscriptionPlans), default=SubscriptionPlans.FREE, nullable=False)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    daily_downloads_used = Column(Integer, default=0)
    last_download_reset = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="subscription")

    def reset_daily_downloads_if_needed(self):
        """Reset daily downloads counter if a new day has started"""
        now = datetime.utcnow()
        if now.date() > self.last_download_reset.date():
            self.daily_downloads_used = 0
            self.last_download_reset = now
            return True
        return False
    
    def can_download(self, file_size: int) -> tuple[bool, Optional[str]]:
        """Check if user can download a file with given size"""
        from config import PLAN_LIMITS
        
        if not self.is_active:
            return False, "اشتراک شما منقضی شده است. لطفا اشتراک جدید خریداری کنید."
        
        plan_limits = PLAN_LIMITS.get(self.plan, {})
        
        # Reset daily downloads if needed
        self.reset_daily_downloads_if_needed()
        
        # Check daily download limit
        if (self.plan != SubscriptionPlans.GOLD and 
            self.daily_downloads_used >= plan_limits.get("daily_downloads", 0)):
            return False, "تعداد دانلود روزانه شما به پایان رسیده است. لطفا اشتراک خود را ارتقا دهید."
        
        # Check file size limit
        if file_size > plan_limits.get("max_file_size", 0):
            return False, f"حجم فایل بیشتر از حد مجاز برای اشتراک شما است. (حداکثر: {plan_limits.get('max_file_size', 0) // (1024*1024)} مگابایت)"
        
        return True, None

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

class Payment(Base):
    """Payment model for tracking user payments"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # in Rials
    plan = Column(Enum(SubscriptionPlans), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_date = Column(DateTime(timezone=True), server_default=func.now())
    transaction_id = Column(String, unique=True, nullable=True)
    description = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payments")

class Download(Base):
    """Download history model"""
    __tablename__ = "downloads"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_url = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    download_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="completed")  # completed, failed, processing
    
    # Relationships
    user = relationship("User", back_populates="downloads")

# Create all tables
def init_db():
    """Initialize the database by creating all tables"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # Create all tables
    init_db()
    print("Database tables created successfully.")
