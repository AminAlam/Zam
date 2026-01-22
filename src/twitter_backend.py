import asyncio
import datetime as dt
import os
import random
import re
import threading
import time

from persiantools.jdatetime import JalaliDate
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# #region agent log
print("[DEBUG] twitter_backend.py module loaded")
# #endregion

# Import tweetcapture (installed via pip install -e in Dockerfile)
from tweetcapture import TweetCapture

from .configs import TwitterConfig


class TwitterClient:
    """
    Twitter client that captures tweets as screenshots and videos.
    Manages a background queue worker for processing tweet capture requests.
    """

    def __init__(self, db, telegram_callback=None, enable_video_capture=True):
        # #region agent log
        print(f"[DEBUG] TwitterClient.__init__ called, enable_video_capture={enable_video_capture}")
        # #endregion
        """
        Initialize the Twitter client.
        
        Args:
            db: Database instance for queue management
            telegram_callback: Callback function to send processed tweets to Telegram
            enable_video_capture: Whether to capture videos from tweets
        """
        self.db = db
        self.telegram_callback = telegram_callback
        self.screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', TwitterConfig.SCREENSHOTS_DIR_NAME)
        self.videos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', TwitterConfig.VIDEOS_DIR_NAME)

        # Ensure directories exist
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)
        if not os.path.exists(self.videos_dir):
            os.makedirs(self.videos_dir)

        # Video capture settings
        self.enable_video_capture = enable_video_capture
        self.x_display = os.environ.get('DISPLAY', ':99')

        # Initialize TweetCapture
        self.tweet_capture = TweetCapture(
            mode=TwitterConfig.TWEET_CAPTURE_MODE,  # Show everything
            night_mode=TwitterConfig.TWEET_CAPTURE_NIGHT_MODE,  # Dark mode (0=light, 1=dim, 2=dark)
            overwrite=TwitterConfig.TWEET_CAPTURE_OVERWRITE,
            radius=TwitterConfig.TWEET_CAPTURE_RADIUS
        )

        # Configure video capture if enabled
        if self.enable_video_capture:
            # Allow toggling audio capture via env (default on)
            video_with_audio = os.environ.get("ZAM_VIDEO_WITH_AUDIO", "1") == "1"
            self.tweet_capture.enable_video_capture(
                output_dir=self.videos_dir,
                x_display=self.x_display,
                max_duration=TwitterConfig.VIDEO_MAX_DURATION,
                with_audio=video_with_audio
            )

        # Queue worker control
        self._worker_running = False
        self._worker_thread = None

    def set_telegram_callback(self, callback):
        """Set the callback function for sending processed tweets."""
        self.telegram_callback = callback

    def _create_driver(self):
        """Create a configured Chrome WebDriver instance."""
        chrome_options = Options()
        for option in TwitterConfig.CHROME_OPTIONS:
            chrome_options.add_argument(option)

        # Use system chromium binary
        chrome_binary = os.environ.get('CHROME_BIN', TwitterConfig.DEFAULT_CHROME_BINARY)
        if os.path.exists(chrome_binary):
            chrome_options.binary_location = chrome_binary

        # Use system chromedriver
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', TwitterConfig.DEFAULT_CHROMEDRIVER_PATH)

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
            wait = WebDriverWait(driver, TwitterConfig.WEBDRIVER_WAIT_TIMEOUT)

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

    def _run_async(self, coro):
        """
        Run an async coroutine in a synchronous context.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Result of the coroutine
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    def capture_tweet(self, tweet_url):
        """
        Capture a tweet screenshot and videos, return metadata.
        
        Args:
            tweet_url: URL of the tweet to capture
            
        Returns:
            dict with screenshot_path, video_paths, username, tweet_id, capture_time, tweet_url
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

        # Capture the screenshot and videos using TweetCapture
        try:
            # #region agent log
            print(f"[DEBUG] capture_tweet called, enable_video_capture={self.enable_video_capture}, tweet_url={tweet_url}")
            # #endregion
            if self.enable_video_capture:
                # #region agent log
                print(f"[DEBUG] Calling screenshot_with_videos, url={normalized_url}")
                # #endregion
                # Use the new screenshot_with_videos method
                result = self._run_async(
                    self.tweet_capture.screenshot_with_videos(
                        url=normalized_url,
                        screenshot_path=output_path,
                        video_output_dir=self.videos_dir
                    )
                )

                screenshot_path = result.get('screenshot_path')
                video_paths = result.get('video_paths', [])
                tweet_text = result.get('tweet_text', '')
                # #region agent log
                preview_text = ''
                if isinstance(tweet_text, dict):
                    preview_text = tweet_text.get('main_text', '')
                elif isinstance(tweet_text, str):
                    preview_text = tweet_text
                print(f"[DEBUG] screenshot_with_videos returned: screenshot={screenshot_path}, videos={video_paths}, tweet_text={preview_text[:50] if preview_text else ''}...")
                # #endregion
            else:
                # Use traditional screenshot method (now returns dict)
                result = self._run_async(
                    self.tweet_capture.screenshot(
                        url=normalized_url,
                        path=output_path
                    )
                )
                screenshot_path = result.get('screenshot_path')
                tweet_text = result.get('tweet_text', {'main_text': '', 'quoted_tweet': None})
                video_paths = []

            if screenshot_path and os.path.exists(screenshot_path):
                capture_time = dt.datetime.now()
                capture_date_persian = JalaliDate(capture_time).strftime("%Y/%m/%d")

                # Use scraped tweet text (more accurate than OCR)
                # tweet_text is now a dict with 'main_text' and 'quoted_tweet'
                main_text = tweet_text.get('main_text', '') if isinstance(tweet_text, dict) else tweet_text
                quoted_tweet = tweet_text.get('quoted_tweet') if isinstance(tweet_text, dict) else None

                # #region agent log
                print(f"[DEBUG] Using scraped tweet text: {len(main_text)} chars, quoted_tweet: {quoted_tweet is not None}")
                # #endregion

                return {
                    'screenshot_path': screenshot_path,
                    'video_paths': video_paths,
                    'username': username,
                    'tweet_id': tweet_id,
                    'capture_time': capture_time,
                    'capture_date_persian': capture_date_persian,
                    'tweet_url': normalized_url,
                    'has_videos': len(video_paths) > 0,
                    'ocr_author': '',  # Not needed with scraping
                    'ocr_text': main_text,  # Main tweet text
                    'quoted_tweet': quoted_tweet  # Quoted tweet info (author, handle, text) or None
                }
        except Exception as e:
            print(f"Error in capture_tweet: {e}")
            self.db.error_log(e)

            # Fallback to direct Selenium capture if TweetCapture fails
            try:
                result = self._capture_screenshot(normalized_url, output_path)
                if result and os.path.exists(output_path):
                    capture_time = dt.datetime.now()
                    capture_date_persian = JalaliDate(capture_time).strftime("%Y/%m/%d")

                    # Run OCR on fallback screenshot
                    ocr_author, ocr_text = self._extract_ocr_data(output_path)

                    return {
                        'screenshot_path': output_path,
                        'video_paths': [],
                        'username': username,
                        'tweet_id': tweet_id,
                        'capture_time': capture_time,
                        'capture_date_persian': capture_date_persian,
                        'tweet_url': normalized_url,
                        'has_videos': False,
                        'ocr_author': ocr_author,
                        'ocr_text': ocr_text
                    }
            except Exception as fallback_error:
                print(f"Fallback capture also failed: {fallback_error}")
                self.db.error_log(fallback_error)

        return None

    def _extract_ocr_data(self, screenshot_path):
        """
        Extract OCR data from a tweet screenshot.
        
        Args:
            screenshot_path: Path to the screenshot image
            
        Returns:
            tuple (ocr_author, ocr_text) - empty strings if OCR fails
        """
        try:
            from .ocr import extract_tweet_ocr

            print(f"[DEBUG] Running OCR on {screenshot_path}")
            ocr_result = extract_tweet_ocr(screenshot_path)

            ocr_author = ocr_result.get('author', '')
            ocr_text = ocr_result.get('text', '')
            confidence = ocr_result.get('confidence', 0)

            print(f"[DEBUG] OCR result: author='{ocr_author}', text='{ocr_text[:50]}...', confidence={confidence:.2f}")

            return ocr_author, ocr_text

        except ImportError as e:
            print(f"[WARNING] OCR module not available: {e}")
            return '', ''
        except Exception as e:
            print(f"[WARNING] OCR extraction failed: {e}")
            self.db.error_log(e)
            return '', ''

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
            self._worker_thread.join(timeout=TwitterConfig.QUEUE_WORKER_STOP_TIMEOUT)
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
                    time.sleep(TwitterConfig.QUEUE_WORKER_POLL_INTERVAL)

            except Exception as e:
                print(f"Queue worker error: {e}")
                self.db.error_log(e)
                time.sleep(TwitterConfig.QUEUE_WORKER_ERROR_WAIT)  # Wait longer on error

    def _process_queue_item(self, queue_item):
        """
        Process a single item from the queue.
        
        Args:
            queue_item: Tuple from database (id, tweet_url, tweet_id, user_name, chat_id, bot_type, priority, added_time, batch_id, batch_total)
        """
        # #region agent log
        print(f"[DEBUG] _process_queue_item called, queue_item={queue_item}")
        # #endregion
        queue_id = queue_item[0]
        tweet_url = queue_item[1]
        tweet_id = queue_item[2]
        user_name = queue_item[3]
        chat_id = queue_item[4]
        bot_type = queue_item[5]
        batch_id = queue_item[8] if len(queue_item) > 8 else None
        batch_total = queue_item[9] if len(queue_item) > 9 else 1

        print(f"Processing queue item {queue_id}: {tweet_url} (batch: {batch_id}, {batch_total} items)")

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
                result['batch_id'] = batch_id
                result['batch_total'] = batch_total

                # Store OCR data in the queue item for batch processing
                ocr_author = result.get('ocr_author', '')
                ocr_text = result.get('ocr_text', '')
                quoted_tweet = result.get('quoted_tweet')
                if ocr_author or ocr_text or quoted_tweet:
                    self.db.update_queue_ocr_data(queue_id, ocr_author, ocr_text, quoted_tweet)

                # Mark as completed first
                self.db.mark_completed(queue_id)
                print(f"Queue item {queue_id} captured successfully")

                # Handle batch vs single tweet processing
                if batch_id and batch_total > 1:
                    # This is part of a batch - check if batch is complete
                    if self.db.is_batch_complete(batch_id):
                        print(f"Batch {batch_id} is complete, triggering combined post")
                        self._process_completed_batch(batch_id, user_name, chat_id, bot_type)
                    else:
                        print(f"Batch {batch_id} not yet complete, waiting for other items")
                else:
                    # Single tweet - process immediately
                    if self.telegram_callback:
                        success = self.telegram_callback(result)
                        if not success:
                            print(f"Warning: Failed to send queue item {queue_id} to Telegram")
            else:
                self.db.mark_failed(queue_id, "Failed to capture screenshot")
                print(f"Queue item {queue_id} failed: Could not capture screenshot")

                # For batches, check if we should still try to post completed items
                if batch_id and batch_total > 1:
                    if self.db.is_batch_complete(batch_id):
                        completed_items = self.db.get_batch_completed_items(batch_id)
                        if completed_items:
                            print(f"Batch {batch_id} complete (with some failures), posting {len(completed_items)} items")
                            self._process_completed_batch(batch_id, user_name, chat_id, bot_type)

        except Exception as e:
            error_msg = str(e)
            self.db.mark_failed(queue_id, error_msg)
            print(f"Queue item {queue_id} failed with error: {error_msg}")
            self.db.error_log(e)

            # For batches, check if we should still try to post completed items
            if batch_id and batch_total > 1:
                if self.db.is_batch_complete(batch_id):
                    completed_items = self.db.get_batch_completed_items(batch_id)
                    if completed_items:
                        self._process_completed_batch(batch_id, user_name, chat_id, bot_type)

    def _process_completed_batch(self, batch_id, user_name, chat_id, bot_type):
        """
        Process a completed batch of tweets, combining them into a single post.
        
        Args:
            batch_id: The batch identifier
            user_name: Username of the submitter
            chat_id: Chat ID for notifications
            bot_type: 'admin' or 'suggestions'
        """
        try:
            # Get all completed items in the batch
            batch_items = self.db.get_batch_completed_items(batch_id)

            if not batch_items:
                print(f"No completed items found for batch {batch_id}")
                return

            print(f"Processing completed batch {batch_id} with {len(batch_items)} items")

            # Build combined result for the callback
            # Format: (id, tweet_url, tweet_id, user_name, chat_id, bot_type, priority, added_time, batch_id, batch_total, status, ocr_author, ocr_text)
            combined_result = {
                'is_batch': True,
                'batch_id': batch_id,
                'user_name': user_name,
                'chat_id': chat_id,
                'bot_type': bot_type,
                'items': []
            }

            # Collect unique authors (from Twitter usernames in URLs)
            unique_authors = set()

            for item in batch_items:
                item_tweet_url = item[1]
                item_tweet_id = item[2]
                item_ocr_author = item[11] if len(item) > 11 else None
                item_ocr_text = item[12] if len(item) > 12 else None

                # Parse username from URL
                parsed = self.parse_tweet_url(item_tweet_url)
                if parsed:
                    unique_authors.add(parsed['username'])

                # Find the screenshot path for this tweet
                screenshot_path = self._find_screenshot_for_tweet(item_tweet_id)
                video_paths = self._find_videos_for_tweet(item_tweet_id)

                # Get quoted_tweet from database if available
                # Index 13 is quoted_tweet (stored as JSONB, returned as dict by psycopg2)
                item_quoted_tweet = item[13] if len(item) > 13 else None
                # If it's a string (shouldn't be with JSONB, but just in case), parse it
                if isinstance(item_quoted_tweet, str):
                    import json
                    try:
                        item_quoted_tweet = json.loads(item_quoted_tweet)
                    except:
                        item_quoted_tweet = None

                combined_result['items'].append({
                    'tweet_id': item_tweet_id,
                    'tweet_url': item_tweet_url,
                    'username': parsed['username'] if parsed else 'unknown',
                    'screenshot_path': screenshot_path,
                    'video_paths': video_paths,
                    'ocr_author': item_ocr_author,
                    'ocr_text': item_ocr_text,
                    'quoted_tweet': item_quoted_tweet
                })

            combined_result['unique_authors'] = list(unique_authors)
            combined_result['capture_time'] = dt.datetime.now()
            combined_result['capture_date_persian'] = JalaliDate(combined_result['capture_time']).strftime("%Y/%m/%d")

            # Call the Telegram callback with the combined result
            if self.telegram_callback:
                success = self.telegram_callback(combined_result)
                if success:
                    print(f"Batch {batch_id} posted successfully")
                else:
                    print(f"Warning: Failed to post batch {batch_id} to Telegram")

        except Exception as e:
            print(f"Error processing batch {batch_id}: {e}")
            self.db.error_log(e)

    def _find_screenshot_for_tweet(self, tweet_id):
        """
        Find the screenshot file for a given tweet ID.
        
        Args:
            tweet_id: The tweet ID
            
        Returns:
            Path to the screenshot file, or None if not found
        """
        import glob
        pattern = os.path.join(self.screenshots_dir, f"{tweet_id}_*.png")
        matches = glob.glob(pattern)
        if matches:
            # Return the most recent one
            return max(matches, key=os.path.getctime)
        return None

    def _find_videos_for_tweet(self, tweet_id):
        """
        Find video files for a given tweet ID.
        
        Args:
            tweet_id: The tweet ID
            
        Returns:
            List of paths to video files
        """
        import glob
        pattern = os.path.join(self.videos_dir, f"{tweet_id}_video_*.mp4")
        matches = glob.glob(pattern)
        return sorted(matches, key=os.path.getctime)

    def add_to_queue(self, tweet_url, user_name, chat_id, bot_type='suggestions', batch_id=None, batch_total=1):
        """
        Add a tweet to the processing queue.
        
        Args:
            tweet_url: URL of the tweet to capture
            user_name: Telegram username of the requester
            chat_id: Telegram chat ID to notify
            bot_type: 'admin' or 'suggestions' (determines priority)
            batch_id: Optional batch identifier for grouping multiple tweets
            batch_total: Total number of tweets in this batch
            
        Returns:
            tuple (queue_id, position) or (None, error_message)
        """
        # Parse the tweet URL
        parsed = self.parse_tweet_url(tweet_url)
        if not parsed:
            return None, "Invalid tweet URL"

        tweet_id = parsed['tweet_id']

        disable_duplicate_checks = os.environ.get("ZAM_DISABLE_DUPLICATE_TWEETS", "0") == "1"

        # Check if tweet already exists
        if not disable_duplicate_checks and self.db.check_tweet_existence(tweet_id):
            return None, "Tweet already posted"

        # Check if tweet is already in queue
        if not disable_duplicate_checks:
            existing = self.db.check_tweet_in_queue(tweet_id)
            if existing:
                return None, "Tweet is already in the queue"

        # Determine priority based on bot type
        priority = TwitterConfig.PRIORITY_ADMIN if bot_type == 'admin' else TwitterConfig.PRIORITY_SUGGESTIONS

        # Add to queue with batch info
        queue_id = self.db.add_to_queue(
            tweet_url=tweet_url,
            tweet_id=tweet_id,
            user_name=user_name,
            chat_id=chat_id,
            bot_type=bot_type,
            priority=priority,
            batch_id=batch_id,
            batch_total=batch_total
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
