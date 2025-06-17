import pytest
import os
import tempfile
from datetime import datetime, timedelta

from src.utils.helpers import (
    sanitize_filename,
    format_file_size,
    format_duration,
    format_time_ago,
    parse_duration,
    parse_speed_string,
    is_video_file,
    is_audio_file,
    truncate_text,
    extract_hashtags,
    generate_random_string,
    convert_seconds_to_timestamp,
    split_large_text
)

class TestFileHelpers:
    """تست‌های مربوط به فایل"""
    
    @pytest.mark.parametrize("filename,expected", [
        ("normal_file.mp4", "normal_file.mp4"),
        ("file:with:colons.mp4", "file_with_colons.mp4"),
        ("file/with/slashes.mp4", "file_with_slashes.mp4"),
        ("file<with>brackets.mp4", "file_with_brackets.mp4"),
        ("file|with|pipes.mp4", "file_with_pipes.mp4"),
        ("   spaces   .mp4", "spaces   .mp4"),
        ("", "download_"),  # نام خالی
        ("." * 50, "download_"),  # فقط نقطه
        ("a" * 300 + ".mp4", "a" * 196 + "....mp4"),  # نام طولانی
    ])
    def test_sanitize_filename(self, filename, expected):
        result = sanitize_filename(filename)
        if expected == "download_":
            assert result.startswith("download_")
        else:
            assert result == expected
    
    @pytest.mark.parametrize("size,expected", [
        (0, "0.0 B"),
        (1023, "1023.0 B"),
        (1024, "1.0 KB"),
        (1024 * 1024, "1.0 MB"),
        (1024 * 1024 * 1024, "1.0 GB"),
        (1536 * 1024 * 1024, "1.5 GB"),
        (1024 * 1024 * 1024 * 1024, "1.0 TB"),
    ])
    def test_format_file_size(self, size, expected):
        assert format_file_size(size) == expected
    
    @pytest.mark.parametrize("path,expected", [
        ("video.mp4", True),
        ("video.MP4", True),
        ("movie.mkv", True),
        ("clip.avi", True),
        ("audio.mp3", False),
        ("document.pdf", False),
        ("archive.zip", False),
    ])
    def test_is_video_file(self, path, expected):
        # توجه: این تست فقط بر اساس پسوند است
        # در محیط واقعی magic type نیز بررسی می‌شود
        assert is_video_file(path) == expected
    
    @pytest.mark.parametrize("path,expected", [
        ("song.mp3", True),
        ("audio.MP3", True),
        ("music.m4a", True),
        ("sound.ogg", True),
        ("podcast.flac", True),
        ("video.mp4", False),
        ("image.jpg", False),
    ])
    def test_is_audio_file(self, path, expected):
        assert is_audio_file(path) == expected

class TestTimeHelpers:
    """تست‌های مربوط به زمان"""
    
    @pytest.mark.parametrize("seconds,expected", [
        (0, "0 ثانیه"),
        (45, "45 ثانیه"),
        (60, "1:00"),
        (125, "2:05"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (7325, "2:02:05"),
    ])
    def test_format_duration(self, seconds, expected):
        assert format_duration(seconds) == expected
    
    def test_format_time_ago(self):
        """تست فرمت زمان گذشته"""
        now = datetime.now()
        
        # همین الان
        assert format_time_ago(now) == "همین الان"
        
        # 30 ثانیه پیش
        assert format_time_ago(now - timedelta(seconds=30)) == "همین الان"
        
        # 5 دقیقه پیش
        assert format_time_ago(now - timedelta(minutes=5)) == "5 دقیقه پیش"
        
        # 2 ساعت پیش
        assert format_time_ago(now - timedelta(hours=2)) == "2 ساعت پیش"
        
        # 3 روز پیش
        assert format_time_ago(now - timedelta(days=3)) == "3 روز پیش"
        
        # 2 ماه پیش
        assert format_time_ago(now - timedelta(days=60)) == "2 ماه پیش"
        
        # 1 سال پیش
        assert format_time_ago(now - timedelta(days=400)) == "1 سال پیش"
    
    @pytest.mark.parametrize("duration_str,expected", [
        ("1:23:45", 5025),
        ("23:45", 1425),
        ("45", 45),
        ("0:00", 0),
        ("", 0),
        ("invalid", 0),
    ])
    def test_parse_duration(self, duration_str, expected):
        assert parse_duration(duration_str) == expected
    
    @pytest.mark.parametrize("seconds,expected", [
        (0, "0:00"),
        (59, "0:59"),
        (60, "1:00"),
        (125, "2:05"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
    ])
    def test_convert_seconds_to_timestamp(self, seconds, expected):
        assert convert_seconds_to_timestamp(seconds) == expected

class TestTextHelpers:
    """تست‌های مربوط به متن"""
    
    def test_truncate_text(self):
        """تست کوتاه کردن متن"""
        # متن کوتاه
        short_text = "این یک متن کوتاه است"
        assert truncate_text(short_text, 100) == short_text
        
        # متن بلند
        long_text = "این یک متن بسیار طولانی است که باید کوتاه شود " * 10
        truncated = truncate_text(long_text, 50)
        assert len(truncated) <= 53  # 50 + 3 for "..."
        assert truncated.endswith("...")
        
        # حفظ کلمات کامل
        text = "این متن باید در جای مناسب قطع شود نه وسط کلمه"
        truncated = truncate_text(text, 20)
        assert not truncated.endswith("کلم...")  # نباید وسط کلمه قطع شود
    
    def test_extract_hashtags(self):
        """تست استخراج هشتگ"""
        text = "این یک متن با #هشتگ_فارسی و #english_hashtag و #۱۲۳ است"
        hashtags = extract_hashtags(text)
        
        assert "#هشتگ_فارسی" in hashtags
        assert "#english_hashtag" in hashtags
        assert "#۱۲۳" in hashtags
        assert len(hashtags) == 3
        
        # بدون هشتگ
        assert extract_hashtags("متن بدون هشتگ") == []
        
        # هشتگ‌های تکراری
        text_duplicate = "#تست #تست #دیگر"
        hashtags_unique = extract_hashtags(text_duplicate)
        assert len(hashtags_unique) == 2  # فقط یکتاها
    
    def test_generate_random_string(self):
        """تست تولید رشته تصادفی"""
        # طول پیش‌فرض
        random1 = generate_random_string()
        assert len(random1) == 8
        assert random1.isalnum()
        
        # طول دلخواه
        random2 = generate_random_string(16)
        assert len(random2) == 16
        
        # یکتا بودن
        random3 = generate_random_string()
        assert random1 != random3
    
    def test_split_large_text(self):
        """تست تقسیم متن بزرگ"""
        # متن کوتاه
        short = "متن کوتاه"
        assert split_large_text(short) == [short]
        
        # متن بلند
        long_text = "خط\n" * 1000
        parts = split_large_text(long_text, max_length=100)
        
        assert len(parts) > 1
        for part in parts:
            assert len(part) <= 100
        
        # بازسازی متن اصلی
        reconstructed = '\n'.join(parts)
        assert len(reconstructed.split('\n')) == len(long_text.split('\n'))

class TestSpeedHelpers:
    """تست‌های مربوط به سرعت"""
    
    @pytest.mark.parametrize("speed_str,expected", [
        ("1 B/s", 1),
        ("1 KB/s", 1024),
        ("1 MB/s", 1024 * 1024),
        ("1 GB/s", 1024 * 1024 * 1024),
        ("1.5 MB/s", int(1.5 * 1024 * 1024)),
        ("500 KB/s", 500 * 1024),
        ("invalid", 0),
        ("", 0),
    ])
    def test_parse_speed_string(self, speed_str, expected):
        assert parse_speed_string(speed_str) == expected