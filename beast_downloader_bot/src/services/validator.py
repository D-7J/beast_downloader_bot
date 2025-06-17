import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Tuple, Optional
from loguru import logger

class URLValidator:
    """سرویس اعتبارسنجی و تمیز کردن URL"""
    
    # پترن‌های پلتفرم‌ها
    PLATFORM_PATTERNS = {
        'youtube': [
            re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'),
            re.compile(r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})'),
            re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})'),
            re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})'),
            re.compile(r'(?:https?://)?(?:www\.)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'),
        ],
        'instagram': [
            re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/reel/([a-zA-Z0-9_-]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/tv/([a-zA-Z0-9_-]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/stories/([^/]+)/([0-9]+)'),
        ],
        'twitter': [
            re.compile(r'(?:https?://)?(?:www\.)?twitter\.com/[^/]+/status/([0-9]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?x\.com/[^/]+/status/([0-9]+)'),
            re.compile(r'(?:https?://)?(?:mobile\.)?twitter\.com/[^/]+/status/([0-9]+)'),
        ],
        'tiktok': [
            re.compile(r'(?:https?://)?(?:www\.)?tiktok\.com/@[^/]+/video/([0-9]+)'),
            re.compile(r'(?:https?://)?(?:vm\.)?tiktok\.com/([a-zA-Z0-9]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?tiktok\.com/t/([a-zA-Z0-9]+)'),
        ],
        'facebook': [
            re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/.+/videos/([0-9]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/watch/?\?v=([0-9]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?fb\.watch/([a-zA-Z0-9_-]+)'),
        ],
        'reddit': [
            re.compile(r'(?:https?://)?(?:www\.)?reddit\.com/r/[^/]+/comments/([a-zA-Z0-9]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?redd\.it/([a-zA-Z0-9]+)'),
            re.compile(r'(?:https?://)?(?:v\.)?redd\.it/([a-zA-Z0-9]+)'),
        ],
        'pinterest': [
            re.compile(r'(?:https?://)?(?:www\.)?pinterest\.com/pin/([0-9]+)'),
            re.compile(r'(?:https?://)?(?:www\.)?pin\.it/([a-zA-Z0-9]+)'),
        ],
        'vimeo': [
            re.compile(r'(?:https?://)?(?:www\.)?vimeo\.com/([0-9]+)'),
            re.compile(r'(?:https?://)?player\.vimeo\.com/video/([0-9]+)'),
        ],
        'dailymotion': [
            re.compile(r'(?:https?://)?(?:www\.)?dailymotion\.com/video/([a-zA-Z0-9]+)'),
            re.compile(r'(?:https?://)?dai\.ly/([a-zA-Z0-9]+)'),
        ],
        'twitch': [
            re.compile(r'(?:https?://)?(?:www\.)?twitch\.tv/videos/([0-9]+)'),
            re.compile(r'(?:https?://)?clips\.twitch\.tv/([a-zA-Z0-9_-]+)'),
        ],
    }
    
    # پارامترهای غیرضروری URL
    UNNECESSARY_PARAMS = [
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'dclid', 'msclkid',
        'feature', 'app', 'list', 'index',
        'si', 'pp', 'ref', 'ref_src', 'ref_url'
    ]
    
    def validate_and_clean(self, url: str) -> Tuple[bool, str, str]:
        """
        اعتبارسنجی و تمیز کردن URL
        
        Returns:
            (is_valid, platform, clean_url)
        """
        try:
            # اضافه کردن https اگر نداشت
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # بررسی URL معتبر
            parsed = urlparse(url)
            if not parsed.netloc:
                return False, 'invalid', url
            
            # شناسایی پلتفرم
            platform = self._detect_platform(url)
            if platform == 'unknown':
                # بررسی آیا دامنه در لیست پشتیبانی شده است
                if not self._is_supported_domain(parsed.netloc):
                    return False, 'unknown', url
            
            # تمیز کردن URL
            clean_url = self._clean_url(url, platform)
            
            return True, platform, clean_url
            
        except Exception as e:
            logger.error(f"Error validating URL {url}: {str(e)}")
            return False, 'invalid', url
    
    def _detect_platform(self, url: str) -> str:
        """تشخیص پلتفرم از URL"""
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(url):
                    return platform
        
        # بررسی دامنه
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '').replace('m.', '')
        
        # پلتفرم‌های اضافی بر اساس دامنه
        domain_platforms = {
            'aparat.com': 'aparat',
            'namasha.com': 'namasha',
            'tamasha.com': 'tamasha',
            'telewebion.com': 'telewebion',
            '3soot.com': '3soot',
            'aparatchi.com': 'aparatchi',
        }
        
        for domain_key, platform in domain_platforms.items():
            if domain_key in domain:
                return platform
        
        return 'unknown'
    
    def _clean_url(self, url: str, platform: str) -> str:
        """تمیز کردن URL از پارامترهای اضافی"""
        try:
            parsed = urlparse(url)
            
            # YouTube: فقط نگه داشتن v و t
            if platform == 'youtube':
                query_params = parse_qs(parsed.query)
                cleaned_params = {}
                
                if 'v' in query_params:
                    cleaned_params['v'] = query_params['v'][0]
                if 't' in query_params:
                    cleaned_params['t'] = query_params['t'][0]
                
                # بازسازی URL
                return urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    urlencode(cleaned_params),
                    ''
                ))
            
            # Instagram: حذف querystring
            elif platform == 'instagram':
                return urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path.rstrip('/'),
                    '', '', ''
                ))
            
            # Twitter/X: حذف پارامترهای tracking
            elif platform == 'twitter':
                query_params = parse_qs(parsed.query)
                cleaned_params = {
                    k: v for k, v in query_params.items()
                    if k not in self.UNNECESSARY_PARAMS
                }
                
                return urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    urlencode(cleaned_params, doseq=True),
                    ''
                ))
            
            # سایر پلتفرم‌ها: حذف پارامترهای tracking
            else:
                query_params = parse_qs(parsed.query)
                cleaned_params = {
                    k: v for k, v in query_params.items()
                    if k not in self.UNNECESSARY_PARAMS
                }
                
                return urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    urlencode(cleaned_params, doseq=True),
                    parsed.fragment
                ))
                
        except Exception as e:
            logger.error(f"Error cleaning URL: {str(e)}")
            return url
    
    def _is_supported_domain(self, domain: str) -> bool:
        """بررسی پشتیبانی از دامنه"""
        # لیست دامنه‌های پشتیبانی شده
        supported_domains = [
            # ویدیو شیرینگ عمومی
            'youtube.com', 'youtu.be', 'instagram.com', 'twitter.com', 'x.com',
            'tiktok.com', 'facebook.com', 'fb.watch', 'reddit.com', 'redd.it',
            'pinterest.com', 'pin.it', 'vimeo.com', 'dailymotion.com', 'dai.ly',
            'twitch.tv', 'clips.twitch.tv',
            
            # پلتفرم‌های ایرانی
            'aparat.com', 'namasha.com', 'tamasha.com', 'telewebion.com',
            '3soot.com', 'aparatchi.com',
            
            # موزیک
            'soundcloud.com', 'mixcloud.com',
            
            # سایر
            'ted.com', 'streamable.com', 'gfycat.com', 'imgur.com',
            'vine.co', 'tumblr.com', 'kickstarter.com',
        ]
        
        domain = domain.lower().replace('www.', '').replace('m.', '')
        
        return any(supported in domain for supported in supported_domains)
    
    def extract_video_id(self, url: str, platform: str) -> Optional[str]:
        """استخراج ID ویدیو از URL"""
        if platform not in self.PLATFORM_PATTERNS:
            return None
        
        for pattern in self.PLATFORM_PATTERNS[platform]:
            match = pattern.search(url)
            if match:
                return match.group(1)
        
        return None
    
    def is_playlist(self, url: str) -> bool:
        """بررسی playlist بودن URL"""
        playlist_indicators = [
            'playlist?list=',
            '/playlist/',
            'album/',
            'collection/',
            '/sets/',
        ]
        
        return any(indicator in url.lower() for indicator in playlist_indicators)
    
    def is_live_stream(self, url: str) -> bool:
        """بررسی live بودن URL"""
        live_indicators = [
            '/live',
            'livestream',
            'live=',
            '/videos/live',
        ]
        
        return any(indicator in url.lower() for indicator in live_indicators)