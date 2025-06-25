"""
Test cases for the buy plan and payment confirmation flow.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock, ANY

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.models import User, Subscription, Payment, PaymentStatus, Base
from database import get_db
from bot.handlers.buy import buy_plan, select_plan
from bot.handlers.admin import confirm_payment
from config import SubscriptionPlans, PLAN_LIMITS
from telegram.constants import ParseMode

# Set up test database
TEST_DATABASE_URL = "sqlite:///:memory:"

# Mock the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Test data
TEST_USER_ID = 12345
TEST_CHAT_ID = 12345

class MockUser:
    def __init__(self, id, is_bot=False, first_name="", last_name="", username=None):
        self.id = id
        self.is_bot = is_bot
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.language_code = 'en'

class MockChat:
    def __init__(self, id, type='private'):
        self.id = id
        self.type = type

class MockMessage:
    def __init__(self, text=None, chat=None, from_user=None, message_id=1, reply_markup=None):
        self.message_id = message_id
        self.date = datetime.now()
        self.chat = chat or MockChat(TEST_CHAT_ID)
        self.from_user = from_user or MockUser(TEST_USER_ID, first_name="Test", last_name="User", username="testuser")
        self.text = text
        self.reply_markup = reply_markup
        self.reply_text = AsyncMock()
        self.reply_markdown = AsyncMock()
        self.reply_html = AsyncMock()
        self.reply_photo = AsyncMock()

class MockCallbackQuery:
    def __init__(self, data, message=None, from_user=None, id="test_query"):
        self.id = id
        self.from_user = from_user or MockUser(TEST_USER_ID, first_name="Test", last_name="User", username="testuser")
        self.message = message or MockMessage()
        self.data = data
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()

def create_mock_update(callback_data=None, message_text=None):
    """Create a mock Telegram Update object for testing."""
    update = AsyncMock()
    update.effective_user = AsyncMock()
    update.effective_user.id = TEST_USER_ID
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_user.username = "testuser"
    update.effective_user.full_name = "Test User"
    
    # Create message mock
    message = AsyncMock()
    message.chat_id = TEST_CHAT_ID
    message.message_id = 123
    message.from_user = update.effective_user
    message.text = message_text
    
    update.message = message
    
    # If callback_data is provided, set up a callback query
    if callback_data:
        update.callback_query = MockCallbackQuery(data=callback_data, message=message)
    
    return update

@pytest.fixture
def update():
    """Create a mock update object with a test user."""
    return create_mock_update("/buy")

@pytest.fixture
def context():
    """Create a mock context with bot_data and admin_ids."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot_data = {
        'admin_ids': [54321],  # Different from test user ID
    }
    
    # Mock bot methods
    context.bot.send_message = AsyncMock()
    context.bot.send_photo = AsyncMock()
    context.bot.answer_callback_query = AsyncMock()
    context.bot.edit_message_reply_markup = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    
    # Add async context manager support
    context.__aenter__ = AsyncMock(return_value=context)
    context.__aexit__ = AsyncMock(return_value=None)
    
    return context

# Create engine and session factory
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a new database session with a test database."""
    # Create the database tables
    Base.metadata.create_all(bind=engine)
    
    # Create a new session
    db = TestingSessionLocal()
    
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def app_db():
    """Fixture that yields a database session and cleans up afterward."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

# Mock FastAPI app for testing (if needed)
# app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_buy_plan_initial(update, context, db_session):
    """Test initial buy plan command shows available plans."""
    # Setup test user in database
    user = User(
        telegram_id=TEST_USER_ID,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    
    # Mock the update object
    update.callback_query = None
    update.message.text = "/buy"
    
    # Set up the database in context
    context.bot_data["db"] = db_session
    
    # Call the function
    await buy_plan(update, context)
    
    # Verify the response
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "اشتراک" in args[0]  # Check for subscription related text
    
    # Check that the reply markup contains buttons
    reply_markup = kwargs.get('reply_markup')
    assert reply_markup is not None
    
    # Get the inline keyboard from the reply markup
    inline_keyboard = reply_markup.inline_keyboard
    assert len(inline_keyboard) > 0  # At least one row of buttons
    
    # Check that we have buttons for different plans
    plan_texts = ["برنز", "نقره‌ای", "طلایی"]  # Persian names for plans
    found_plans = 0
    for row in inline_keyboard:
        for button in row:
            if any(plan in button.text for plan in plan_texts):
                found_plans += 1
    
    assert found_plans >= 1  # At least one plan button should be present

@pytest.mark.asyncio
async def test_select_plan(update, context, db_session):
    """Test selecting a plan shows payment instructions."""
    # Setup test user in database
    user = User(
        telegram_id=TEST_USER_ID,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    
    # Mock the update object for callback query
    update = create_mock_update(callback_data="select_plan:bronze")
    
    # Set up the database in context
    context.bot_data["db"] = db_session
    
    # Call the function
    await select_plan(update, context)
    
    # Verify the response
    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()
    
    # Get the arguments passed to edit_message_text
    call_args = update.callback_query.edit_message_text.call_args
    kwargs = call_args.kwargs
    text = kwargs['text']
    
    # Check the response contains the expected plan information
    assert "برنز" in text  # Bronze in Persian
    assert "50,000" in text  # Price
    
    # Check that a payment record was created
    payment = db_session.query(Payment).filter_by(user_id=user.id).first()
    assert payment is not None
    assert str(payment.plan) == "bronze"
    assert payment.status == PaymentStatus.PENDING

@pytest.mark.asyncio
async def test_confirm_payment(update, context, db_session):
    """Test admin confirming a payment."""
    # Setup test user and payment in database
    user = User(
        telegram_id=TEST_USER_ID,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    
    # Create a test payment
    payment = Payment(
        user_id=user.id,
        amount=50000,
        plan=SubscriptionPlans.BRONZE,
        status=PaymentStatus.PENDING,
        transaction_id="TEST123",
        description="Test payment"
    )
    db_session.add(payment)
    db_session.commit()
    
    # Create admin user
    admin_user = User(
        telegram_id=54321,
        username="adminuser",
        first_name="Admin",
        last_name="User",
        is_admin=True
    )
    db_session.add(admin_user)
    db_session.commit()
    
    # Mock the update object with a callback query
    update = create_mock_update(callback_data=f"confirm_payment:{payment.id}")
    
    # Set up the database in context
    context.bot_data["db"] = db_session
    
    # Mock bot.send_message
    context.bot.send_message = AsyncMock()
    
    # Call the function
    await confirm_payment(update, context)
    
    # Verify the responses
    update.callback_query.answer.assert_called_once()
    
    # Check that send_message was called for user notification
    context.bot.send_message.assert_any_call(
        chat_id=user.telegram_id,
        text=ANY,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Check that payment was updated
    updated_payment = db_session.query(Payment).filter_by(id=payment.id).first()
    assert updated_payment.status == PaymentStatus.COMPLETED
