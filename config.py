import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")

# Redis configuration (for rate limiting and caching)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Admin user IDs (comma-separated)
ADMIN_IDS = [int(id_str) for id_str in os.getenv("ADMIN_IDS", "").split(",") if id_str]

from enum import Enum, auto

# Subscription plans
class SubscriptionPlans(str, Enum):
    FREE = "free"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    
    def __str__(self):
        return self.value

# Plan limits
PLAN_LIMITS = {
    SubscriptionPlans.FREE: {
        "daily_downloads": 5,
        "max_file_size": 50 * 1024 * 1024,  # 50MB
        "max_quality": "720p",
        "watermark": True,
        "price": 0,
    },
    SubscriptionPlans.BRONZE: {
        "daily_downloads": 50,
        "max_file_size": 200 * 1024 * 1024,  # 200MB
        "max_quality": "1080p",
        "watermark": False,
        "price": 50000,  # 50,000 Toman
    },
    SubscriptionPlans.SILVER: {
        "daily_downloads": 150,
        "max_file_size": 500 * 1024 * 1024,  # 500MB
        "max_quality": "1080p+",
        "watermark": False,
        "price": 100000,  # 100,000 Toman
    },
    SubscriptionPlans.GOLD: {
        "daily_downloads": float('inf'),  # Unlimited
        "max_file_size": 2 * 1024 * 1024 * 1024,  # 2GB
        "max_quality": "4K",
        "watermark": False,
        "price": 200000,  # 200,000 Toman
    },
}

# Payment configuration
PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER", "")
PAYMENT_CARD_OWNER = os.getenv("PAYMENT_CARD_OWNER", "")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join("logs", "bot.log")

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)
