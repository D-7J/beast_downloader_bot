from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from typing import List, Optional

from . import models, schemas
from config import SubscriptionPlans, PLAN_LIMITS

def get_user(db: Session, user_id: int):
    """Get user by telegram ID"""
    return db.query(models.User).filter(models.User.telegram_id == user_id).first()

def create_user(db: Session, user_data: dict):
    """Create a new user"""
    db_user = models.User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create free subscription for new user
    subscription = models.Subscription(
        user_id=db_user.id,
        plan=SubscriptionPlans.FREE,
        is_active=True,
        last_download_reset=datetime.utcnow()
    )
    db.add(subscription)
    db.commit()
    
    return db_user

def get_or_create_user(db: Session, user_data: dict):
    """Get user if exists, otherwise create a new one"""
    db_user = get_user(db, user_data['telegram_id'])
    if db_user:
        # Update user info if needed
        update_data = {}
        for field in ['username', 'first_name', 'last_name']:
            if field in user_data and getattr(db_user, field) != user_data[field]:
                update_data[field] = user_data[field]
        
        if update_data:
            for key, value in update_data.items():
                setattr(db_user, key, value)
            db.commit()
            db.refresh(db_user)
        
        return db_user
    return create_user(db, user_data)

def get_user_subscription(db: Session, user_id: int):
    """Get user's active subscription"""
    return db.query(models.Subscription).filter(
        models.Subscription.user_id == user_id,
        models.Subscription.is_active == True,
        or_(
            models.Subscription.end_date.is_(None),
            models.Subscription.end_date > datetime.utcnow()
        )
    ).first()

def update_subscription_plan(db: Session, user_id: int, plan: SubscriptionPlans, duration_days: int = 30):
    """Update user's subscription plan"""
    now = datetime.utcnow()
    end_date = now + timedelta(days=duration_days)
    
    subscription = get_user_subscription(db, user_id)
    if not subscription:
        # Create new subscription if none exists
        subscription = models.Subscription(
            user_id=user_id,
            plan=plan,
            start_date=now,
            end_date=end_date,
            is_active=True,
            last_download_reset=now
        )
        db.add(subscription)
    else:
        # Extend existing subscription
        if subscription.end_date and subscription.end_date > now:
            end_date = subscription.end_date + timedelta(days=duration_days)
        
        subscription.plan = plan
        subscription.start_date = now
        subscription.end_date = end_date
        subscription.is_active = True
        subscription.daily_downloads_used = 0
        subscription.last_download_reset = now
    
    db.commit()
    db.refresh(subscription)
    return subscription

def record_download(db: Session, user_id: int, file_url: str, file_name: str, file_size: int) -> models.Download:
    """Record a download in the database"""
    # Get user's subscription
    subscription = get_user_subscription(db, user_id)
    if not subscription:
        raise ValueError("User does not have an active subscription")
    
    # Update download count
    subscription.daily_downloads_used += 1
    
    # Create download record
    download = models.Download(
        user_id=user_id,
        file_url=file_url,
        file_name=file_name,
        file_size=file_size,
        status="completed"
    )
    
    db.add(download)
    db.commit()
    db.refresh(download)
    
    return download

def create_payment(db: Session, user_id: int, amount: int, plan: SubscriptionPlans) -> models.Payment:
    """Create a new payment record"""
    payment = models.Payment(
        user_id=user_id,
        amount=amount,
        plan=plan,
        status=models.PaymentStatus.PENDING
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    return payment

def complete_payment(db: Session, payment_id: int, transaction_id: str) -> models.Payment:
    """Mark a payment as completed"""
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        return None
    
    payment.status = models.PaymentStatus.COMPLETED
    payment.transaction_id = transaction_id
    payment.payment_date = datetime.utcnow()
    
    # Update user's subscription
    update_subscription_plan(db, payment.user_id, payment.plan)
    
    db.commit()
    db.refresh(payment)
    return payment

def get_user_downloads(db: Session, user_id: int, limit: int = 10) -> List[models.Download]:
    """Get user's download history"""
    return db.query(models.Download)\
        .filter(models.Download.user_id == user_id)\
        .order_by(models.Download.download_date.desc())\
        .limit(limit)\
        .all()

def get_user_payments(db: Session, user_id: int, limit: int = 10) -> List[models.Payment]:
    """Get user's payment history"""
    return db.query(models.Payment)\
        .filter(models.Payment.user_id == user_id)\
        .order_by(models.Payment.payment_date.desc())\
        .limit(limit)\
        .all()

# Admin functions
def get_all_users(db: Session, skip: int = 0, limit: int = 100):
    """Get all users (for admin)"""
    return db.query(models.User).offset(skip).limit(limit).all()

def get_all_payments(db: Session, skip: int = 0, limit: int = 100):
    """Get all payments (for admin)"""
    return db.query(models.Payment).offset(skip).limit(limit).all()

def get_all_downloads(db: Session, skip: int = 0, limit: int = 100):
    """Get all downloads (for admin)"""
    return db.query(models.Download).offset(skip).limit(limit).all()
