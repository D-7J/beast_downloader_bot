import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Dict, Any, List

# Load environment variables
load_dotenv()

@dataclass
class BotConfig:
    """تنظیمات بات تلگرام"""
    token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: list = None
    webhook_url: str = os.getenv("WEBHOOK_URL", "")
    use_webhook: bool = os.getenv("USE_WEBHOOK", "False").lower() == "true"
    
    def __post_init__(self):
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        self.admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

@dataclass
class DatabaseConfig:
    """تنظیمات دیتابیس"""
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "downloader_bot")
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

@dataclass
class DownloadConfig:
    """تنظیمات دانلود"""
    download_dir: str = os.getenv("DOWNLOAD_DIR", "./data/downloads")
    temp_dir: str = os.getenv("TEMP_DIR", "./data/temp")
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "2147483648"))  # 2GB
    cleanup_after_hours: int = int(os.getenv("CLEANUP_HOURS", "24"))
    concurrent_downloads: int = int(os.getenv("CONCURRENT_DOWNLOADS", "3"))
    
    # کیفیت‌های پیش‌فرض
    video_quality: str = os.getenv("DEFAULT_VIDEO_QUALITY", "720")
    audio_quality: str = os.getenv("DEFAULT_AUDIO_QUALITY", "192")
    
    # محدودیت‌های پلتفرم
    platform_limits: Dict[str, int] = {
        'youtube': 4 * 1024 * 1024 * 1024,  # 4GB
        'instagram': 1 * 1024 * 1024 * 1024,  # 1GB
        'twitter': 512 * 1024 * 1024,  # 512MB
        'tiktok': 200 * 1024 * 1024,  # 200MB
    }

@dataclass
class SubscriptionConfig:
    """تنظیمات اشتراک‌ها"""
    plans: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        self.plans = {
            'free': {
                'name': 'رایگان',
                'daily_limit': 5,
                'max_file_size': 50 * 1024 * 1024,  # 50MB
                'max_duration': 600,  # 10 دقیقه
                'concurrent_downloads': 1,
                'features': ['دانلود ویدیو', 'دانلود صوت'],
                'price': 0
            },
            'bronze': {
                'name': 'برنزی',
                'daily_limit': 50,
                'max_file_size': 200 * 1024 * 1024,  # 200MB
                'max_duration': 1800,  # 30 دقیقه
                'concurrent_downloads': 2,
                'features': ['دانلود ویدیو', 'دانلود صوت', 'اولویت در صف', 'بدون واترمارک'],
                'price': 50000,
                'duration_days': 30
            },
            'silver': {
                'name': 'نقره‌ای',
                'daily_limit': 150,
                'max_file_size': 500 * 1024 * 1024,  # 500MB
                'max_duration': 3600,  # 60 دقیقه
                'concurrent_downloads': 3,
                'features': ['همه امکانات برنزی', 'دانلود زیرنویس', 'انتخاب کیفیت دلخواه'],
                'price': 100000,
                'duration_days': 30
            },
            'gold': {
                'name': 'طلایی',
                'daily_limit': -1,  # نامحدود
                'max_file_size': 2 * 1024 * 1024 * 1024,  # 2GB
                'max_duration': -1,  # نامحدود
                'concurrent_downloads': 5,
                'features': ['همه امکانات', 'دانلود پلی‌لیست', 'دانلود نامحدود', 'پشتیبانی اختصاصی'],
                'price': 200000,
                'duration_days': 30
            }
        }

@dataclass
class PaymentConfig:
    """تنظیمات پرداخت"""
    provider: str = os.getenv("PAYMENT_PROVIDER", "card_to_card")  # تغییر پیش‌فرض به کارت به کارت
    
    # تنظیمات کارت به کارت
    card_numbers: List[Dict[str, str]] = None
    admin_notification: bool = True
    payment_timeout_minutes: int = 30
    
    # تنظیمات زرین‌پال (برای استفاده آینده)
    zarinpal_merchant: str = os.getenv("ZARINPAL_MERCHANT", "")
    zarinpal_sandbox: bool = os.getenv("ZARINPAL_SANDBOX", "True").lower() == "true"
    
    # تنظیمات سایر درگاه‌ها (برای استفاده آینده)
    idpay_api_key: str = os.getenv("IDPAY_API_KEY", "")
    idpay_sandbox: bool = os.getenv("IDPAY_SANDBOX", "True").lower() == "true"
    
    payping_token: str = os.getenv("PAYPING_TOKEN", "")
    
    nextpay_api_key: str = os.getenv("NEXTPAY_API_KEY", "")
    
    nowpayments_api_key: str = os.getenv("NOWPAYMENTS_API_KEY", "")
    nowpayments_ipn_secret: str = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
    
    # آدرس callback (برای درگاه‌هایی که نیاز دارند)
    callback_url: str = os.getenv("PAYMENT_CALLBACK_URL", "")
    
    def __post_init__(self):
        # بارگذاری کارت‌ها از env یا تنظیمات پیش‌فرض
        cards_env = os.getenv("PAYMENT_CARDS", "")
        if cards_env:
            # فرمت: "number:owner:bank:sheba|number:owner:bank:sheba"
            self.card_numbers = []
            for card_str in cards_env.split("|"):
                parts = card_str.split(":")
                if len(parts) >= 3:
                    self.card_numbers.append({
                        'number': parts[0],
                        'owner': parts[1],
                        'bank': parts[2],
                        'sheba': parts[3] if len(parts) > 3 else ''
                    })
        else:
            # کارت‌های پیش‌فرض (می‌تونید تغییر بدید)
            self.card_numbers = [
                {
                    'number': '6037-9976-1234-5678',
                    'owner': 'علی رضایی',
                    'bank': 'بانک ملی',
                    'sheba': 'IR120570000000123456789012'
                }
            ]

@dataclass
class CeleryConfig:
    """تنظیمات Celery"""
    broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    task_time_limit: int = int(os.getenv("TASK_TIME_LIMIT", "3600"))  # 1 hour
    task_soft_time_limit: int = int(os.getenv("TASK_SOFT_TIME_LIMIT", "3300"))

@dataclass
class LogConfig:
    """تنظیمات لاگ"""
    level: str = os.getenv("LOG_LEVEL", "INFO")
    file_path: str = os.getenv("LOG_FILE", "./logs/bot.log")
    max_size: str = os.getenv("LOG_MAX_SIZE", "10MB")
    backup_count: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    sentry_dsn: str = os.getenv("SENTRY_DSN", "")

# ایجاد نمونه‌های کانفیگ
bot_config = BotConfig()
db_config = DatabaseConfig()
download_config = DownloadConfig()
subscription_config = SubscriptionConfig()
payment_config = PaymentConfig()
celery_config = CeleryConfig()
log_config = LogConfig()

# تنظیمات yt-dlp
YDL_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': os.path.join(download_config.download_dir, '%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'no_color': True,
    'noprogress': True,
    'age_limit': 0,
    'prefer_ffmpeg': True,
    'ffmpeg_location': os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg"),
    'concurrent_fragment_downloads': 5,
    'http_chunk_size': 10485760,  # 10MB chunks
    'retries': 5,
    'fragment_retries': 5,
    'skip_unavailable_fragments': True,
    'keepvideo': False,
    'overwrites': True,
    'continuedl': True,
    'noresizebuffer': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Accept-Encoding': 'gzip,deflate',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
    },
    # محدودیت سرعت برای جلوگیری از بن شدن
    'ratelimit': 5000000,  # 5MB/s
    'sleep_interval': 1,
    'max_sleep_interval': 5,
}

# تنظیمات برای پلتفرم‌های خاص
PLATFORM_OPTIONS = {
    'instagram': {
        'cookiefile': os.getenv("INSTAGRAM_COOKIES", ""),
        'username': os.getenv("INSTAGRAM_USERNAME", ""),
        'password': os.getenv("INSTAGRAM_PASSWORD", ""),
    },
    'twitter': {
        'username': os.getenv("TWITTER_USERNAME", ""),
        'password': os.getenv("TWITTER_PASSWORD", ""),
    }
}

# ایجاد دایرکتوری‌ها
os.makedirs(download_config.download_dir, exist_ok=True)
os.makedirs(download_config.temp_dir, exist_ok=True)
os.makedirs(os.path.dirname(log_config.file_path), exist_ok=True)