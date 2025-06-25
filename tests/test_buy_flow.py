"""
Test cases for the buy plan and payment confirmation flow.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from telegram import Update, Message, Chat, User as TelegramUser, CallbackQuery
from telegram.ext import CallbackContext, ContextTypes

from database import User, Subscription, Payment, init_db
from bot.handlers.buy import buy_plan, select_plan
from bot.handlers.admin import confirm_payment
from config import SubscriptionPlans

# Test data
TEST_USER = TelegramUser(
    id=12345,
    first_name="Test",
    last_name="User",
    username="testuser",
    is_bot=False
)

TEST_CHAT = Chat(id=12345, type='private')

def create_message(text: str = None, reply_markup=None):
    return Message(
        message_id=1,
        date=datetime.now(),
        chat=TEST_CHAT,
        text=text,
        reply_markup=reply_markup
    )

@pytest.fixture
def update():
    update = Update(
        update_id=1,
        message=create_message("/buy")
    )
    update.effective_user = TEST_USER
    return update

@pytest.fixture
def context(db_session):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {
        "db": db_session,
        "admin_ids": [54321]  # Admin user ID
    }
    context.args = []
    return context

@pytest.fixture
def db_session():
    # Setup test database
    engine, session_factory = init_db("sqlite:///:memory:")
    session = session_factory()
    
    # Create test user
    user = User(
        telegram_id=12345,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_active=True
    )
    session.add(user)
    session.commit()
    
    yield session
    session.close()

@pytest.mark.asyncio
async def test_buy_plan_initial(update, context, db_session):
    """Test initial buy plan command shows available plans."""
    await buy_plan(update, context)
    
    # Verify message was sent with plan options
    assert context.bot.send_message.called
    args, kwargs = context.bot.send_message.call_args
    assert "پلن‌های اشتراک" in kwargs['text']
    assert "برنزی" in kwargs['text']
    assert "نقره‌ای" in kwargs['text']
    assert "طلایی" in kwargs['text']

@pytest.mark.asyncio
async def test_select_plan(update, context, db_session):
    """Test selecting a plan shows payment instructions."""
    # Create a callback query for plan selection
    query = MagicMock(spec=CallbackQuery)
    query.data = "select_plan:BRONZE"
    query.message = create_message()
    update.callback_query = query
    
    await select_plan(update, context)
    
    # Verify payment instructions are shown
    assert query.message.edit_text.called
    args, kwargs = query.message.edit_text.call_args
    assert "پرداخت اشتراک برنزی" in kwargs['text']
    assert "تومان" in kwargs['text']
    
    # Verify a payment record was created
    payment = db_session.query(Payment).filter_by(user_id=12345).first()
    assert payment is not None
    assert payment.plan == "BRONZE"

@pytest.mark.asyncio
async def test_confirm_payment(update, context, db_session):
    """Test admin confirming a payment."""
    # Create a test payment
    from database import create_payment
    payment = create_payment(
        db=db_session,
        user_id=12345,
        amount=50000,
        plan="BRONZE"
    )
    db_session.commit()
    
    # Create a callback query for payment confirmation
    query = MagicMock(spec=CallbackQuery)
    query.data = f"confirm_payment:{payment.id}"
    query.message = create_message()
    update.callback_query = query
    update.effective_user = TelegramUser(id=54321, first_name="Admin", is_bot=False)
    
    await confirm_payment(update, context)
    
    # Verify payment was marked as completed
    db_session.refresh(payment)
    assert payment.status == "completed"
    assert payment.transaction_id.startswith("MANUAL-")
    
    # Verify subscription was created/updated
    subscription = db_session.query(Subscription).filter_by(user_id=12345).first()
    assert subscription is not None
    assert subscription.plan == "BRONZE"
    assert subscription.is_active is True
    assert subscription.end_date > datetime.utcnow()
    
    # Verify admin was notified
    assert context.bot.send_message.called
    
    # Verify user was notified
    # Note: In a real test, we'd need to mock the bot.send_message call to the user
    # This would require more extensive mocking of the Telegram API
