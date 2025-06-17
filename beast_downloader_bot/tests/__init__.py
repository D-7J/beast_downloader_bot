"""
Test suite for Persian Downloader Bot

This package contains all unit and integration tests.
"""

import os
import sys

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Test configuration
TEST_BOT_TOKEN = "test_bot_token"
TEST_MONGO_URI = "mongodb://localhost:27017/test_db"
TEST_REDIS_HOST = "localhost"
TEST_REDIS_PORT = 6379

# Mock data for tests
MOCK_USER = {
    'user_id': 123456789,
    'username': 'test_user',
    'first_name': 'Test',
    'last_name': 'User'
}

MOCK_VIDEO_INFO = {
    'title': 'Test Video',
    'duration': 120,
    'thumbnail': 'https://example.com/thumb.jpg',
    'formats': [
        {'format_id': '18', 'ext': 'mp4', 'height': 360},
        {'format_id': '22', 'ext': 'mp4', 'height': 720}
    ]
}