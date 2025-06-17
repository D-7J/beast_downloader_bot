import os
import re
import hashlib
import aiofiles
from typing import Optional, Union
from datetime import datetime, timedelta
import unicodedata
from pathlib import Path
import magic
from loguru import logger

def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    تمیز کردن نام فایل از کاراکترهای غیرمجاز
    """
    # حذف کاراکترهای کنترلی و نرمال‌سازی
    filename = unicodedata.normalize('NFKD', filename)
    filename = ''.join(c for c in filename if unicodedata.category(c) != 'Cc')
    
    # جایگزینی کاراکترهای غیرمجاز
    # در ویندوز: < > : " / \ | ? *
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, '_', filename)
    
    # حذف نقطه و فاصله از ابتدا و انتها
    filename = filename.strip('. ')
    
    # محدود کردن طول
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        name = name[:max_length - len(ext) - 3] + '...'
        filename = name + ext
    
    # اگر خالی شد
    if not filename:
        filename = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    return filename

async def get_file_hash(filepath: str, algorithm: str = 'md5') -> str:
    """
    محاسبه هش فایل به صورت async
    """
    hash_func = getattr(hashlib, algorithm)()
    
    async with aiofiles.open(filepath, 'rb') as f:
        while chunk := await f.read(8192):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()

def get_file_type(filepath: str) -> str:
    """
    تشخیص نوع فایل با python-magic
    """
    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(filepath)
        return file_type
    except Exception as e:
        logger.error(f"Error detecting file type: {str(e)}")
        # Fallback به پسوند
        ext = Path(filepath).suffix.lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska',
            '.avi': 'video/x-msvideo',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg',
            '.jpg': 'image/jpeg',
            '.png': 'image/png',
        }
        return mime_types.get(ext, 'application/octet-stream')

def format_time_ago(dt: datetime) -> str:
    """
    تبدیل تاریخ به فرمت "x زمان پیش"
    """
    now = datetime.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return "همین الان"
    elif diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} دقیقه پیش"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} ساعت پیش"
    elif diff < timedelta(days=30):
        days = diff.days
        return f"{days} روز پیش"
    elif diff < timedelta(days=365):
        months = int(diff.days / 30)
        return f"{months} ماه پیش"
    else:
        years = int(diff.days / 365)
        return f"{years} سال پیش"

def parse_duration(duration_str: str) -> int:
    """
    تبدیل رشته زمان به ثانیه
    مثال: "1:23:45" -> 5025
    """
    parts = duration_str.strip().split(':')
    parts = [int(p) for p in parts if p.isdigit()]
    
    if len(parts) == 3:  # HH:MM:SS
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:  # MM:SS
        return parts[0] * 60 + parts[1]
    elif len(parts) == 1:  # SS
        return parts[0]
    else:
        return 0

def estimate_download_time(file_size: int, speed: int) -> int:
    """
    تخمین زمان دانلود (ثانیه)
    file_size: bytes
    speed: bytes per second
    """
    if speed <= 0:
        return 0
    
    return int(file_size / speed)

def parse_speed_string(speed_str: str) -> int:
    """
    تبدیل رشته سرعت به بایت بر ثانیه
    مثال: "1.5 MB/s" -> 1572864
    """
    try:
        # پیدا کردن عدد و واحد
        match = re.match(r'([\d.]+)\s*([KMGT]?)B/s', speed_str, re.IGNORECASE)
        if not match:
            return 0
        
        value = float(match.group(1))
        unit = match.group(2).upper()
        
        multipliers = {
            '': 1,
            'K': 1024,
            'M': 1024 ** 2,
            'G': 1024 ** 3,
            'T': 1024 ** 4
        }
        
        return int(value * multipliers.get(unit, 1))
        
    except Exception:
        return 0

def is_video_file(filepath: str) -> bool:
    """
    بررسی ویدیو بودن فایل
    """
    video_extensions = {
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
        '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.ogv'
    }
    
    ext = Path(filepath).suffix.lower()
    if ext in video_extensions:
        return True
    
    # بررسی با MIME type
    mime_type = get_file_type(filepath)
    return mime_type.startswith('video/')

def is_audio_file(filepath: str) -> bool:
    """
    بررسی صوتی بودن فایل
    """
    audio_extensions = {
        '.mp3', '.m4a', '.ogg', '.wav', '.flac', '.aac',
        '.wma', '.opus', '.oga', '.mid', '.midi', '.amr'
    }
    
    ext = Path(filepath).suffix.lower()
    if ext in audio_extensions:
        return True
    
    # بررسی با MIME type
    mime_type = get_file_type(filepath)
    return mime_type.startswith('audio/')

async def cleanup_old_files(directory: str, hours: int = 24) -> int:
    """
    پاکسازی فایل‌های قدیمی از دایرکتوری
    """
    if not os.path.exists(directory):
        return 0
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    deleted_count = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                # بررسی زمان تغییر فایل
                file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_mtime < cutoff_time:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.info(f"Deleted old file: {filepath}")
            except Exception as e:
                logger.error(f"Error deleting file {filepath}: {str(e)}")
    
    # حذف دایرکتوری‌های خالی
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    logger.info(f"Deleted empty directory: {dir_path}")
            except Exception as e:
                logger.error(f"Error deleting directory {dir_path}: {str(e)}")
    
    return deleted_count

def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    کوتاه کردن متن با حفظ کلمات کامل
    """
    if len(text) <= max_length:
        return text
    
    # پیدا کردن آخرین فاصله قبل از max_length
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # اگر فاصله در 80% انتهایی بود
        truncated = truncated[:last_space]
    
    return truncated.rstrip() + suffix

def extract_hashtags(text: str) -> list:
    """
    استخراج هشتگ‌ها از متن
    """
    # پترن برای هشتگ‌های فارسی و انگلیسی
    pattern = r'#[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\w]+'
    hashtags = re.findall(pattern, text)
    return list(set(hashtags))  # حذف تکراری‌ها

def generate_random_string(length: int = 8) -> str:
    """
    تولید رشته تصادفی
    """
    import string
    import random
    
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def convert_seconds_to_timestamp(seconds: int) -> str:
    """
    تبدیل ثانیه به فرمت timestamp
    مثال: 125 -> "2:05"
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

async def get_directory_size(directory: str) -> int:
    """
    محاسبه حجم کل یک دایرکتوری
    """
    total_size = 0
    
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(filepath)
            except Exception:
                pass
    
    return total_size

def is_valid_telegram_file_size(file_size: int, is_premium: bool = False) -> bool:
    """
    بررسی معتبر بودن حجم فایل برای تلگرام
    """
    max_size = 2 * 1024 * 1024 * 1024  # 2GB for normal users
    if is_premium:
        max_size = 4 * 1024 * 1024 * 1024  # 4GB for premium users
    
    return 0 < file_size <= max_size

def split_large_text(text: str, max_length: int = 4096) -> list:
    """
    تقسیم متن طولانی به چند بخش
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    # تقسیم بر اساس خطوط
    lines = text.split('\n')
    
    for line in lines:
        if len(current_part) + len(line) + 1 <= max_length:
            current_part += line + '\n'
        else:
            if current_part:
                parts.append(current_part.rstrip())
            current_part = line + '\n'
    
    if current_part:
        parts.append(current_part.rstrip())
    
    return parts