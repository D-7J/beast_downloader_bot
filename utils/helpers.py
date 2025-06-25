from datetime import datetime, timedelta
from typing import Optional, Union
import re

def format_size(size_bytes: Union[int, float, None]) -> str:
    """Convert size in bytes to human readable format"""
    if size_bytes is None:
        return "نامشخص"
    
    size_bytes = float(size_bytes)
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.1f} {units[i]}"

def format_timedelta(delta: timedelta) -> str:
    """Format a timedelta as a human-readable string"""
    total_seconds = int(delta.total_seconds())
    
    # Calculate days, hours, minutes, seconds
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} روز")
    if hours > 0:
        parts.append(f"{hours} ساعت")
    if minutes > 0 and days == 0:  # Only show minutes if less than a day
        parts.append(f"{minutes} دقیقه")
    if seconds > 0 and total_seconds < 60:  # Only show seconds if less than a minute
        parts.append(f"{seconds} ثانیه")
    
    return " و ".join(parts) if parts else "چند لحظه"

def get_readable_time(seconds: Union[int, float]) -> str:
    """Convert seconds to a human-readable time string"""
    return format_timedelta(timedelta(seconds=seconds))

def format_price(price: Union[int, float]) -> str:
    """Format price with thousand separators"""
    return f"{int(price):,}"

def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))

def truncate(text: str, max_length: int = 50, ellipsis: str = "...") -> str:
    """Truncate text and add ellipsis if needed"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis

def parse_human_readable_size(size_str: str) -> Optional[int]:
    """Parse human-readable size string to bytes"""
    if not size_str:
        return None
    
    # Remove any whitespace and make lowercase
    size_str = size_str.strip().lower()
    
    # Extract number and unit
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([kmgt]?b?)?$', size_str)
    if not match:
        return None
    
    number = float(match.group(1))
    unit = match.group(2) or 'b'
    
    # Remove 'b' if present (e.g., 'mb' -> 'm')
    if len(unit) > 1 and unit.endswith('b'):
        unit = unit[0]
    
    # Convert to bytes
    units = {'': 1, 'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4}
    multiplier = units.get(unit.lower(), 1)
    
    return int(number * multiplier)
