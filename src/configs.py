"""
Configuration module for Zam Telegram Bot.
Contains all configuration constants organized by module.
Loads environment variables and provides shared imports.
"""

import datetime as dt
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Working directory
working_dir = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# TELEGRAM BACKEND CONFIGURATION
# =============================================================================
class TelegramConfig:
    """Configuration for Telegram bot functionality."""

    # API timeout settings
    DEFAULT_TIMEOUT = 30  # seconds

    # Message limits
    MAX_CAPTION_LENGTH = 1024  # Telegram caption character limit

    # Message queue settings
    QUEUE_RATE_LIMIT = 0.5  # seconds between messages
    QUEUE_MAX_RETRIES = 3
    QUEUE_STOP_TIMEOUT = 5  # seconds

    # Text truncation limits
    OCR_TEXT_MAX_LENGTH = 300  # For multi-tweet messages
    QUOTED_TEXT_MAX_LENGTH = 200  # For quoted tweets in multi-tweet
    MIN_TEXT_KEEP_LENGTH = 50  # Minimum chars to keep when truncating

    # Expandable blockquote settings
    # When tweet text exceeds this length, use Telegram's expandable/collapsible blockquote
    # Set to 0 to disable expandable blockquotes entirely
    EXPANDABLE_BLOCKQUOTE_THRESHOLD = 400  # Characters (roughly 4-5 lines)

    # Auto-timing settings
    DEFAULT_TWEETS_PER_HOUR = 6
    MIN_GAP_MINUTES = 5
    TIME_OPTIONS_MAX_MINUTES = 480  # 16 * 30 = 8 hours
    TIME_OPTIONS_INTERVAL = 30  # minutes

    # Hour weights for auto-timing: Peak hours get more tweets
    # Index = hour (0-23), Value = weight multiplier
    HOUR_WEIGHTS = [
        0.3, 0.3, 0.3, 0.3, 0.3, 0.3,  # 0-5 AM (quiet hours)
        0.5, 0.7, 0.7, 0.7, 0.7, 0.8,  # 6-11 AM (morning)
        0.8, 0.8, 0.8, 0.8, 0.8, 0.8,  # 12-5 PM (afternoon)
        0.9, 0.9, 1.5, 1.5, 1.5, 1.3,  # 6-11 PM (evening/night peak)
    ]

    # Background task intervals
    TWEET_LINE_CHECK_INTERVAL = 10  # seconds
    TIME_COUNTER_UPDATE_INTERVAL = 61  # seconds

    # Mahsa Amini memorial (time counter feature)
    MAHSA_DEATH_TIME = dt.datetime(2022, 9, 16, 19, 0)
    MAHSA_FLAG_IMAGE_URL = 'https://revolution.aminalam.info/static/images/wlf_flag.png'


# =============================================================================
# TWITTER BACKEND CONFIGURATION
# =============================================================================
class TwitterConfig:
    """Configuration for Twitter/X capture functionality."""

    # TweetCapture defaults
    TWEET_CAPTURE_MODE = 3  # Show everything
    TWEET_CAPTURE_NIGHT_MODE = 2  # Dark mode (0=light, 1=dim, 2=dark)
    TWEET_CAPTURE_RADIUS = 15  # Corner radius
    TWEET_CAPTURE_OVERWRITE = True

    # Video capture settings
    VIDEO_MAX_DURATION = 120  # seconds (2 minutes)
    VIDEO_DEFAULT_DURATION = 30.0  # seconds (fallback)

    # Directory names (relative to src/)
    SCREENSHOTS_DIR_NAME = 'screenshots'
    VIDEOS_DIR_NAME = 'videos'

    # Queue priority levels
    PRIORITY_ADMIN = 10
    PRIORITY_SUGGESTIONS = 1

    # Queue worker settings
    QUEUE_WORKER_POLL_INTERVAL = 2  # seconds
    QUEUE_WORKER_ERROR_WAIT = 5  # seconds
    QUEUE_WORKER_STOP_TIMEOUT = 5  # seconds

    # Chrome WebDriver options
    CHROME_OPTIONS = [
        '--headless',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--window-size=600,1200',
        '--hide-scrollbars',
        '--disable-extensions',
        '--disable-infobars',
        '--disable-notifications',
        '--disable-popup-blocking',
        '--font-render-hinting=none',
        '--disable-font-subpixel-positioning',
    ]

    # Default binary paths
    DEFAULT_CHROME_BINARY = '/usr/bin/chromium'
    DEFAULT_CHROMEDRIVER_PATH = '/usr/bin/chromedriver'

    # WebDriver wait timeout
    WEBDRIVER_WAIT_TIMEOUT = 15  # seconds


# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
class DatabaseConfig:
    """Configuration for database connectivity."""

    # Connection pool settings
    POOL_MIN_CONNECTIONS = 1
    POOL_MAX_CONNECTIONS = 10

    # Default connection parameters (overridden by env vars)
    DEFAULT_HOST = 'localhost'
    DEFAULT_PORT = '5432'
    DEFAULT_USER = 'zam'
    DEFAULT_DATABASE = 'zam_db'

    # Stats/monitoring settings
    HOURLY_DISTRIBUTION_HOURS_AHEAD = 6
    MAX_SLOTS_PER_HOUR = 6


# =============================================================================
# OCR CONFIGURATION
# =============================================================================
class OCRConfig:
    """Configuration for OCR text extraction."""

    # Tesseract language codes
    DEFAULT_LANGUAGE = "eng+fas"  # English + Persian/Farsi


# =============================================================================
# UTILS CONFIGURATION
# =============================================================================
class UtilsConfig:
    """Configuration for utility functions."""

    # Telegraph API
    TELEGRAPH_API_URL = 'https://api.telegra.ph'


# =============================================================================
# MAIN APPLICATION CONFIGURATION
# =============================================================================
class MainConfig:
    """Configuration for main application defaults."""

    # CLI defaults
    DEFAULT_TIME_DIFF = '3:30'  # Tehran timezone offset
    DEFAULT_NUM_TWEETS_TO_PRESERVE = 1000
    DEFAULT_USER_TWEET_LIMIT = 10

    # Validation ranges
    TWEETS_TO_PRESERVE_MIN = 500
    TWEETS_TO_PRESERVE_MAX = 5000
    USER_TWEET_LIMIT_MIN = 0
    USER_TWEET_LIMIT_MAX = 120


# =============================================================================
# TWEETCAPTURE CONFIGURATION
# =============================================================================
class TweetCaptureConfig:
    """Configuration for TweetCapture library."""

    # Default capture settings
    DEFAULT_MODE = 3
    DEFAULT_NIGHT_MODE = 0
    DEFAULT_WAIT_TIME = 5  # seconds
    DEFAULT_RADIUS = 15
    DEFAULT_SCALE = 1.0

    # Video capture defaults
    DEFAULT_VIDEO_OUTPUT_DIR = "/app/videos"
    DEFAULT_X_DISPLAY = ":99"
    DEFAULT_VIDEO_MAX_DURATION = 120  # seconds
    DEFAULT_VIDEO_WITH_AUDIO = True

    # Wait time range
    WAIT_TIME_MIN = 1.0
    WAIT_TIME_MAX = 10.0

    # Scale range
    SCALE_MIN = 0.0
    SCALE_MAX = 14.0

    # Night mode colors (RGB)
    NIGHT_MODE_COLORS = {
        0: (255, 255, 255),  # Light mode (white)
        1: (21, 32, 43),     # Dim mode (dark blue)
        2: (0, 0, 0),        # Dark mode (black)
    }

    # Video playback settings
    VIDEO_START_TIMEOUT = 10  # seconds
    VIDEO_END_BUFFER = 1.5  # seconds after video ends
    VIDEO_POLL_INTERVAL = 0.5  # seconds

    # Recording settings
    RECORDING_START_DELAY = 0.3  # seconds

    # Telegram file size limit
    TELEGRAM_MAX_FILE_SIZE_MB = 50
