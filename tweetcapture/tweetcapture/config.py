"""
Configuration module for TweetCapture library.
Contains all configuration constants for tweet screenshot capture.
"""


class TweetCaptureConfig:
    """Configuration for TweetCapture functionality."""

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
    DEFAULT_VIDEO_DURATION = 30.0  # seconds (fallback when duration unknown)

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

    # Page load wait times
    PAGE_LOAD_WAIT = 2.0  # seconds
    SCREENSHOT_WAIT = 0.1  # seconds
    SHOW_MORE_CLICK_WAIT = 1.0  # seconds
    SHOW_MORE_SCROLL_WAIT = 0.2  # seconds
    COOKIE_DISMISS_WAIT = 0.5  # seconds
