import pytest
from src.services.validator import URLValidator

class TestURLValidator:
    """تست‌های کلاس URLValidator"""
    
    def setup_method(self):
        """راه‌اندازی قبل از هر تست"""
        self.validator = URLValidator()
    
    # تست‌های YouTube
    @pytest.mark.parametrize("url,expected_valid,expected_platform", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True, "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", True, "youtube"),
        ("https://youtube.com/shorts/abcd1234567", True, "youtube"),
        ("youtube.com/watch?v=test123", True, "youtube"),  # بدون https
        ("https://m.youtube.com/watch?v=mobile123", True, "youtube"),
        ("https://youtube.com/embed/embed123", True, "youtube"),
    ])
    def test_youtube_urls(self, url, expected_valid, expected_platform):
        is_valid, platform, clean_url = self.validator.validate_and_clean(url)
        assert is_valid == expected_valid
        assert platform == expected_platform
        if is_valid:
            assert "utm_" not in clean_url  # پارامترهای tracking حذف شده باشند
    
    # تست‌های Instagram
    @pytest.mark.parametrize("url,expected_valid,expected_platform", [
        ("https://www.instagram.com/p/CfxKJNPJi8A/", True, "instagram"),
        ("https://instagram.com/reel/CfxKJNPJi8A/", True, "instagram"),
        ("https://www.instagram.com/tv/CfxKJNPJi8A/", True, "instagram"),
        ("instagram.com/stories/username/2890382904", True, "instagram"),
    ])
    def test_instagram_urls(self, url, expected_valid, expected_platform):
        is_valid, platform, clean_url = self.validator.validate_and_clean(url)
        assert is_valid == expected_valid
        assert platform == expected_platform
        if is_valid:
            assert clean_url.endswith('/') == False  # trailing slash حذف شده
    
    # تست‌های Twitter/X
    @pytest.mark.parametrize("url,expected_valid,expected_platform", [
        ("https://twitter.com/user/status/1234567890", True, "twitter"),
        ("https://x.com/user/status/1234567890", True, "twitter"),
        ("https://mobile.twitter.com/user/status/1234567890", True, "twitter"),
    ])
    def test_twitter_urls(self, url, expected_valid, expected_platform):
        is_valid, platform, clean_url = self.validator.validate_and_clean(url)
        assert is_valid == expected_valid
        assert platform == expected_platform
    
    # تست‌های URL نامعتبر
    @pytest.mark.parametrize("url", [
        "not a url",
        "http://",
        "ftp://example.com/file.zip",
        "https://google.com",  # سایت پشتیبانی نشده
        "",
        None,
    ])
    def test_invalid_urls(self, url):
        if url is None:
            url = ""
        is_valid, platform, clean_url = self.validator.validate_and_clean(url)
        assert is_valid == False
    
    # تست حذف پارامترهای tracking
    def test_remove_tracking_params(self):
        url = "https://youtube.com/watch?v=test123&utm_source=twitter&utm_medium=social&feature=share"
        is_valid, platform, clean_url = self.validator.validate_and_clean(url)
        
        assert is_valid == True
        assert "utm_source" not in clean_url
        assert "utm_medium" not in clean_url
        assert "feature" not in clean_url
        assert "v=test123" in clean_url  # پارامتر اصلی باقی مانده
    
    # تست تشخیص playlist
    def test_detect_playlist(self):
        playlist_url = "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        assert self.validator.is_playlist(playlist_url) == True
        
        video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert self.validator.is_playlist(video_url) == False
    
    # تست تشخیص live stream
    def test_detect_live_stream(self):
        live_url = "https://www.youtube.com/live/abc123"
        assert self.validator.is_live_stream(live_url) == True
        
        normal_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert self.validator.is_live_stream(normal_url) == False
    
    # تست استخراج video ID
    @pytest.mark.parametrize("url,platform,expected_id", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtube", "dQw4w9WgXcQ"),
        ("https://instagram.com/p/CfxKJNPJi8A/", "instagram", "CfxKJNPJi8A"),
        ("https://twitter.com/user/status/1234567890", "twitter", "1234567890"),
    ])
    def test_extract_video_id(self, url, platform, expected_id):
        video_id = self.validator.extract_video_id(url, platform)
        assert video_id == expected_id
    
    # تست پلتفرم‌های ایرانی
    @pytest.mark.parametrize("url,expected_platform", [
        ("https://www.aparat.com/v/aBcDe", "aparat"),
        ("https://namasha.com/v/xyz123", "namasha"),
        ("https://www.telewebion.com/episode/123456", "telewebion"),
    ])
    def test_iranian_platforms(self, url, expected_platform):
        is_valid, platform, clean_url = self.validator.validate_and_clean(url)
        assert is_valid == True
        assert platform == expected_platform