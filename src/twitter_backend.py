import os
import re
import random
import threading
import time
import datetime as dt
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from persiantools.jdatetime import JalaliDate


class TwitterClient:
    """
    Twitter client that captures tweets as screenshots.
    Manages a background queue worker for processing tweet capture requests.
    """

    def __init__(self, db, telegram_callback=None):
        """
        Initialize the Twitter client.
        
        Args:
            db: Database instance for queue management
            telegram_callback: Callback function to send processed tweets to Telegram
        """
        self.db = db
        self.telegram_callback = telegram_callback
        self.screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'screenshots')
        
        # Ensure screenshots directory exists
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)

        # Queue worker control
        self._worker_running = False
        self._worker_thread = None

    def set_telegram_callback(self, callback):
        """Set the callback function for sending processed tweets."""
        self.telegram_callback = callback

    def _create_driver(self):
        """Create a configured Chrome WebDriver instance."""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=600,1200')
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        # Enable proper font rendering for Persian/Arabic text
        chrome_options.add_argument('--font-render-hinting=none')
        chrome_options.add_argument('--disable-font-subpixel-positioning')
        
        # Use system chromium binary
        chrome_binary = os.environ.get('CHROME_BIN', '/usr/bin/chromium')
        if os.path.exists(chrome_binary):
            chrome_options.binary_location = chrome_binary
        
        # Use system chromedriver
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
        
        if os.path.exists(chromedriver_path):
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Fallback to default
            driver = webdriver.Chrome(options=chrome_options)
        
        return driver

    def parse_tweet_url(self, tweet_url):
        """
        Parse a tweet URL to extract username and tweet ID.
        Supports both twitter.com and x.com URLs.
        
        Args:
            tweet_url: The tweet URL to parse
            
        Returns:
            dict with 'username' and 'tweet_id', or None if parsing fails
        """
        # Remove query parameters
        if '?' in tweet_url:
            tweet_url = tweet_url.split('?')[0]

        # Pattern for twitter.com and x.com URLs
        pattern = r'(?:https?://)?(?:mobile\.)?(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)'
        match = re.match(pattern, tweet_url)

        if match:
            return {
                'username': match.group(1),
                'tweet_id': match.group(2)
            }
        return None

    def normalize_tweet_url(self, tweet_url):
        """
        Normalize a tweet URL to a consistent format.
        
        Args:
            tweet_url: The tweet URL to normalize
            
        Returns:
            Normalized URL string
        """
        parsed = self.parse_tweet_url(tweet_url)
        if parsed:
            return f"https://twitter.com/{parsed['username']}/status/{parsed['tweet_id']}"
        return tweet_url

    def _dismiss_cookie_banner(self, driver):
        """
        Dismiss or hide cookie consent banners on Twitter/X.
        """
        try:
            # JavaScript to hide cookie banners and other popups
            hide_elements_js = """
            // Hide cookie banner by various selectors
            const selectorsToHide = [
                '[data-testid="BottomBar"]',
                '[role="dialog"]',
                '[data-testid="sheetDialog"]',
                '[aria-label="Cookie banner"]',
                'div[class*="cookie"]',
                'div[class*="Cookie"]',
                'div[class*="consent"]',
                'div[class*="Consent"]',
                '#layers > div:last-child',
                'div[data-testid="toast"]'
            ];
            
            selectorsToHide.forEach(selector => {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                });
            });
            
            // Try to click refuse/close buttons
            const buttonTexts = ['Refuse', 'Decline', 'Close', 'Not now', 'Maybe later'];
            const buttons = document.querySelectorAll('button, [role="button"]');
            buttons.forEach(btn => {
                const text = btn.textContent.toLowerCase();
                if (buttonTexts.some(t => text.includes(t.toLowerCase()))) {
                    try { btn.click(); } catch(e) {}
                }
            });
            
            // Hide the bottom bar that often contains cookie notice
            const bottomBars = document.querySelectorAll('div[style*="bottom: 0"]');
            bottomBars.forEach(el => {
                if (el.textContent.toLowerCase().includes('cookie')) {
                    el.style.display = 'none';
                }
            });
            """
            driver.execute_script(hide_elements_js)
        except Exception as e:
            print(f"Could not dismiss cookie banner: {e}")

    def _capture_screenshot(self, tweet_url, output_path):
        """
        Capture a screenshot of a tweet.
        
        Args:
            tweet_url: URL of the tweet to capture
            output_path: Path to save the screenshot
            
        Returns:
            The output path if successful, None otherwise
        """
        driver = None
        try:
            driver = self._create_driver()
            driver.get(tweet_url)
            
            # Wait for the tweet to load
            wait = WebDriverWait(driver, 15)
            
            # Try to find the tweet article element
            try:
                # Wait for tweet content to be present
                tweet_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
                )
                
                # Give it a moment to fully render
                time.sleep(2)
                
                # Dismiss cookie banners and popups
                self._dismiss_cookie_banner(driver)
                time.sleep(0.5)
                
                # Try to take screenshot of just the tweet
                tweet_element.screenshot(output_path)
                
            except Exception as e:
                print(f"Could not capture tweet element, taking full page screenshot: {e}")
                # Fallback to full page screenshot
                time.sleep(3)
                self._dismiss_cookie_banner(driver)
                time.sleep(0.5)
                driver.save_screenshot(output_path)
            
            return output_path
            
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            self.db.error_log(e)
            return None
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def capture_tweet(self, tweet_url):
        """
        Capture a tweet screenshot and return metadata.
        
        Args:
            tweet_url: URL of the tweet to capture
            
        Returns:
            dict with screenshot_path, username, tweet_id, capture_time, tweet_url
            or None if capture fails
        """
        parsed = self.parse_tweet_url(tweet_url)
        if not parsed:
            return None

        username = parsed['username']
        tweet_id = parsed['tweet_id']

        # Generate unique filename
        random_suffix = random.randint(1, 1000000000)
        filename = f"{tweet_id}_{random_suffix}.png"
        output_path = os.path.join(self.screenshots_dir, filename)

        # Normalize the URL for capture
        normalized_url = self.normalize_tweet_url(tweet_url)

        # Capture the screenshot
        try:
            result = self._capture_screenshot(normalized_url, output_path)

            if result and os.path.exists(output_path):
                capture_time = dt.datetime.now()
                capture_date_persian = JalaliDate(capture_time).strftime("%Y/%m/%d")

                return {
                    'screenshot_path': output_path,
                    'username': username,
                    'tweet_id': tweet_id,
                    'capture_time': capture_time,
                    'capture_date_persian': capture_date_persian,
                    'tweet_url': normalized_url
                }
        except Exception as e:
            print(f"Error in capture_tweet: {e}")
            self.db.error_log(e)

        return None

    def start_queue_worker(self):
        """Start the background queue worker thread."""
        if self._worker_running:
            print("Queue worker is already running")
            return

        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._queue_worker_loop, daemon=True)
        self._worker_thread.start()
        print("Queue worker started")

    def stop_queue_worker(self):
        """Stop the background queue worker thread."""
        self._worker_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        print("Queue worker stopped")

    def _queue_worker_loop(self):
        """
        Main loop for the queue worker.
        Continuously processes pending items from the queue.
        """
        while self._worker_running:
            try:
                # Get next pending item
                queue_item = self.db.get_next_pending()

                if queue_item:
                    self._process_queue_item(queue_item)
                else:
                    # No pending items, wait before checking again
                    time.sleep(2)

            except Exception as e:
                print(f"Queue worker error: {e}")
                self.db.error_log(e)
                time.sleep(5)  # Wait longer on error

    def _process_queue_item(self, queue_item):
        """
        Process a single item from the queue.
        
        Args:
            queue_item: Tuple from database (id, tweet_url, tweet_id, user_name, chat_id, bot_type, priority, added_time)
        """
        queue_id = queue_item[0]
        tweet_url = queue_item[1]
        tweet_id = queue_item[2]
        user_name = queue_item[3]
        chat_id = queue_item[4]
        bot_type = queue_item[5]

        print(f"Processing queue item {queue_id}: {tweet_url}")

        # Mark as processing
        self.db.mark_processing(queue_id)

        try:
            # Capture the tweet
            result = self.capture_tweet(tweet_url)

            if result:
                # Add queue metadata to result
                result['queue_id'] = queue_id
                result['user_name'] = user_name
                result['chat_id'] = chat_id
                result['bot_type'] = bot_type

                # Call the Telegram callback to send the tweet
                if self.telegram_callback:
                    success = self.telegram_callback(result)
                    if success:
                        self.db.mark_completed(queue_id)
                        print(f"Queue item {queue_id} completed successfully")
                    else:
                        self.db.mark_failed(queue_id, "Failed to send to Telegram")
                else:
                    # No callback set, just mark as completed
                    self.db.mark_completed(queue_id)
                    print(f"Queue item {queue_id} captured (no callback)")
            else:
                self.db.mark_failed(queue_id, "Failed to capture screenshot")
                print(f"Queue item {queue_id} failed: Could not capture screenshot")

        except Exception as e:
            error_msg = str(e)
            self.db.mark_failed(queue_id, error_msg)
            print(f"Queue item {queue_id} failed with error: {error_msg}")
            self.db.error_log(e)

    def add_to_queue(self, tweet_url, user_name, chat_id, bot_type='suggestions'):
        """
        Add a tweet to the processing queue.
        
        Args:
            tweet_url: URL of the tweet to capture
            user_name: Telegram username of the requester
            chat_id: Telegram chat ID to notify
            bot_type: 'admin' or 'suggestions' (determines priority)
            
        Returns:
            tuple (queue_id, position) or (None, error_message)
        """
        # Parse the tweet URL
        parsed = self.parse_tweet_url(tweet_url)
        if not parsed:
            return None, "Invalid tweet URL"

        tweet_id = parsed['tweet_id']

        # Check if tweet already exists
        if self.db.check_tweet_existence(tweet_id):
            return None, "Tweet already posted"

        # Check if tweet is already in queue
        existing = self.db.check_tweet_in_queue(tweet_id)
        if existing:
            return None, "Tweet is already in the queue"

        # Determine priority based on bot type
        priority = 10 if bot_type == 'admin' else 1

        # Add to queue
        queue_id = self.db.add_to_queue(
            tweet_url=tweet_url,
            tweet_id=tweet_id,
            user_name=user_name,
            chat_id=chat_id,
            bot_type=bot_type,
            priority=priority
        )

        if queue_id:
            position = self.db.get_queue_position(queue_id)
            return queue_id, position

        return None, "Failed to add to queue"

    def get_reference_tweet_snapshot_as_media(self, tweet_url, tweet_id):
        """
        Capture a reference tweet (quoted or replied-to) as media.
        This is a synchronous method for capturing additional context tweets.
        
        Args:
            tweet_url: URL of the reference tweet
            tweet_id: ID of the reference tweet
            
        Returns:
            list [file_path, 'photo'] or None if capture fails
        """
        result = self.capture_tweet(tweet_url)
        if result:
            return [result['screenshot_path'], 'photo']
        return None
