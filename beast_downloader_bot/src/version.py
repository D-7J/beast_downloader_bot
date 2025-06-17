"""
Persian Downloader Bot Version Info
"""

__version__ = "1.0.0"
__release_date__ = "2024-01-01"
__author__ = "Your Name"
__email__ = "your-email@example.com"
__description__ = "A powerful Telegram bot for downloading videos from social media platforms"
__url__ = "https://github.com/yourusername/persian-downloader-bot"
__license__ = "MIT"

# Version history
VERSION_HISTORY = [
    {
        "version": "1.0.0",
        "date": "2024-01-01",
        "changes": [
            "Initial release",
            "Support for YouTube, Instagram, Twitter, TikTok",
            "Subscription system with 4 tiers",
            "Admin panel",
            "Persian language support",
            "Queue system with priority",
            "Payment integration with Zarinpal"
        ]
    }
]

def get_version_info():
    """دریافت اطلاعات کامل نسخه"""
    return {
        "version": __version__,
        "release_date": __release_date__,
        "author": __author__,
        "description": __description__,
        "latest_changes": VERSION_HISTORY[0]["changes"] if VERSION_HISTORY else []
    }