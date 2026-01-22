"""
Pytest configuration and fixtures for Zam tests.
"""
import os
import sys

import pytest

# Add project root and local tweetcapture to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'tweetcapture'))

# Ensure we don't accidentally import from src/ directly
if os.path.join(project_root, 'src') in sys.path:
    sys.path.remove(os.path.join(project_root, 'src'))

# Test tweet URL - Jack Dorsey's first tweet
TEST_TWEET_URL = "https://x.com/jack/status/20"
TEST_TWEET_URL_TWITTER = "https://twitter.com/jack/status/20"
TEST_TWEET_ID = "20"
TEST_USERNAME = "jack"


@pytest.fixture
def test_tweet_url():
    """Fixture providing the test tweet URL."""
    return TEST_TWEET_URL


@pytest.fixture
def test_tweet_data():
    """Fixture providing test tweet data."""
    return {
        'url': TEST_TWEET_URL,
        'twitter_url': TEST_TWEET_URL_TWITTER,
        'tweet_id': TEST_TWEET_ID,
        'username': TEST_USERNAME
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to set up mock environment variables."""
    monkeypatch.setenv('DB_HOST', 'localhost')
    monkeypatch.setenv('DB_PORT', '5432')
    monkeypatch.setenv('DB_USER', 'test_user')
    monkeypatch.setenv('DB_PASSWORD', 'test_password')
    monkeypatch.setenv('DB_NAME', 'test_db')
    monkeypatch.setenv('ADMIN_TELEGRAM_BOT', 'test_admin_token')
    monkeypatch.setenv('SUGGESTIONS_TELEGRAM_BOT', 'test_suggestions_token')
    monkeypatch.setenv('MAIN_CHANNEL_CHAT_ID', '-1001234567890')
    monkeypatch.setenv('ADMIN_CHAT_ID', '-1009876543210')
    monkeypatch.setenv('SUGGESTIONS_CHAT_ID', '-1001111111111')
    monkeypatch.setenv('CHANNEL_NAME', '@TestChannel')
    monkeypatch.setenv('ADMIN_IDS', 'admin1,admin2,admin3')

