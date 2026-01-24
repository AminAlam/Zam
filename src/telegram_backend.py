import datetime as dt
import json
import os
import queue
import random
import threading
import time

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, MessageEntity
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import CallbackQueryHandler, CommandHandler, Filters, MessageHandler, Updater

from .configs import TelegramConfig
from .utils import covert_tweet_time_to_desired_time, deleted_snapshots, form_time_counter_message, telegraph


class TelegramMessageQueue:
    """
    Thread-safe queue for outgoing Telegram messages.
    
    Features:
    - Single sender thread with rate limiting
    - Retry with exponential backoff
    - Proper error handling and logging
    - Graceful shutdown support
    """

    def __init__(self, bot, db=None, rate_limit=None, max_retries=None):
        """
        Initialize the message queue.
        
        Args:
            bot: Telegram Bot instance
            db: Database instance for error logging (optional)
            rate_limit: Minimum seconds between messages
            max_retries: Maximum retry attempts for failed messages
        """
        self.bot = bot
        self.db = db
        self.rate_limit = rate_limit if rate_limit is not None else TelegramConfig.QUEUE_RATE_LIMIT
        self.max_retries = max_retries if max_retries is not None else TelegramConfig.QUEUE_MAX_RETRIES
        self._queue = queue.Queue()
        self._running = False
        self._sender_thread = None

    def start(self):
        """Start the sender thread."""
        if self._running:
            return
        self._running = True
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()
        print("Message queue sender started")

    def stop(self):
        """Stop the sender thread."""
        self._running = False
        # Put a None to unblock the queue
        self._queue.put(None)
        if self._sender_thread:
            self._sender_thread.join(timeout=TelegramConfig.QUEUE_STOP_TIMEOUT)
        print("Message queue sender stopped")

    def send_message(self, chat_id, text, **kwargs):
        """Queue a text message for sending."""
        self._queue.put(('message', chat_id, text, kwargs))

    def send_media_group(self, chat_id, media, **kwargs):
        """Queue a media group for sending."""
        self._queue.put(('media_group', chat_id, media, kwargs))

    def edit_message_text(self, chat_id, message_id, text, **kwargs):
        """Queue an edit message request."""
        self._queue.put(('edit_message', chat_id, message_id, text, kwargs))

    def edit_message_media(self, chat_id, message_id, media, **kwargs):
        """Queue an edit media request."""
        self._queue.put(('edit_media', chat_id, message_id, media, kwargs))

    def send_message_sync(self, chat_id, text, **kwargs):
        """
        Send a message synchronously (bypasses queue).
        Use only when you need the return value immediately.
        """
        return self._send_with_retry(
            lambda: self.bot.sendMessage(chat_id=chat_id, text=text, timeout=TelegramConfig.DEFAULT_TIMEOUT, **kwargs)
        )

    def send_media_group_sync(self, chat_id, media, **kwargs):
        """
        Send a media group synchronously (bypasses queue).
        Use only when you need the return value immediately.
        """
        return self._send_with_retry(
            lambda: self.bot.sendMediaGroup(chat_id=chat_id, media=media, timeout=TelegramConfig.DEFAULT_TIMEOUT, **kwargs)
        )

    def _sender_loop(self):
        """Main sender loop - processes queued messages."""
        while self._running:
            try:
                item = self._queue.get(timeout=1)

                if item is None:
                    continue

                msg_type = item[0]

                try:
                    if msg_type == 'message':
                        _, chat_id, text, kwargs = item
                        self._send_with_retry(
                            lambda: self.bot.sendMessage(chat_id=chat_id, text=text, timeout=TelegramConfig.DEFAULT_TIMEOUT, **kwargs)
                        )

                    elif msg_type == 'media_group':
                        _, chat_id, media, kwargs = item
                        self._send_with_retry(
                            lambda: self.bot.sendMediaGroup(chat_id=chat_id, media=media, timeout=TelegramConfig.DEFAULT_TIMEOUT, **kwargs)
                        )

                    elif msg_type == 'edit_message':
                        _, chat_id, message_id, text, kwargs = item
                        self._send_with_retry(
                            lambda: self.bot.editMessageText(chat_id=chat_id, message_id=message_id, text=text, timeout=TelegramConfig.DEFAULT_TIMEOUT, **kwargs)
                        )

                    elif msg_type == 'edit_media':
                        _, chat_id, message_id, media, kwargs = item
                        self._send_with_retry(
                            lambda: self.bot.editMessageMedia(chat_id=chat_id, message_id=message_id, media=media, timeout=TelegramConfig.DEFAULT_TIMEOUT, **kwargs)
                        )

                except Exception as e:
                    print(f"Failed to send message after retries: {e}")
                    if self.db:
                        self.db.error_log(e)

                # Rate limiting
                time.sleep(self.rate_limit)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Message queue error: {e}")
                if self.db:
                    self.db.error_log(e)

    def _send_with_retry(self, send_func):
        """
        Execute a send function with exponential backoff retry.
        
        Args:
            send_func: Callable that performs the actual send
            
        Returns:
            The result of send_func if successful
            
        Raises:
            The last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return send_func()
            except RetryAfter as e:
                # Telegram asked us to wait
                wait_time = e.retry_after + 1
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            except (NetworkError, TimedOut) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(e)
                    print(f"Network error, retry {attempt + 1}/{self.max_retries} in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    raise
            except Exception:
                # Non-retryable error
                raise

        if last_exception:
            raise last_exception


class TelegramBot:
    """Base class for Telegram bots."""

    def __init__(self, creds, db, twitter_api, time_diff, reference_snapshot):
        self.creds = creds
        self.db = db
        self.twitter_api = twitter_api
        self.time_diff = time_diff
        self.reference_snapshot = reference_snapshot
        # Message queue will be initialized by subclasses after bot is created
        self.message_queue = None

    def start(self, update, context=None):
        """Handle /start command."""
        update.message.reply_text('Hello {}'.format(update.message.from_user.first_name))

    def make_media_array(self, tg_text, media_list, entities=None):
        """Create an array of media for sending to Telegram."""
        media_array = []
        for indx, media in enumerate(media_list):
            if indx == 0:
                caption = tg_text
                caption_entities = entities
            else:
                caption = ""
                caption_entities = None

            if media[1] == "photo":
                if not media[0].startswith("http"):
                    media_url = open(media[0], 'rb')
                else:
                    media_url = media[0]
                if entities:
                    media_tmp = InputMediaPhoto(media_url, caption=caption, caption_entities=caption_entities)
                else:
                    media_tmp = InputMediaPhoto(media_url, caption=caption, parse_mode="HTML")
            elif media[1] == "video" or media[1] == "animated_gif":
                if not media[0].startswith("http"):
                    media_url = open(media[0], 'rb')
                else:
                    media_url = media[0]
                if entities:
                    media_tmp = InputMediaVideo(media_url, caption=caption, caption_entities=caption_entities)
                else:
                    media_tmp = InputMediaVideo(media_url, caption=caption, parse_mode="HTML")
            media_array.append(media_tmp)
        return media_array

    def _utf16_len(self, text: str) -> int:
        return len((text or "").encode("utf-16-le")) // 2

    def _append_text(self, parts: list, current_len: int, segment: str) -> int:
        parts.append(segment)
        return current_len + self._utf16_len(segment)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters in text."""
        if not text:
            return ""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

    def format_tweet_message(self, tweet_data):
        """
        Format a captured tweet for display in Telegram using HTML.
        
        Dynamically truncates text if the message exceeds Telegram's 1024 char caption limit.
        
        Args:
            tweet_data: Dict with screenshot_path, username, tweet_id, capture_date_persian, tweet_url,
                       ocr_text (main tweet text), quoted_tweet (optional dict with author, handle, text)
            
        Returns:
            Tuple of (formatted_message_string, None)
            - None entities means use parse_mode="HTML"
        """
        username = tweet_data['username']
        tweet_url = tweet_data['tweet_url']
        capture_date_persian = tweet_data['capture_date_persian']
        ocr_text = tweet_data.get('ocr_text', '').strip()
        quoted_tweet = tweet_data.get('quoted_tweet')
        quote_text = quoted_tweet.get('text', '').strip() if quoted_tweet else ''

        # First attempt: generate HTML with full text
        message = self._build_html_message(username, tweet_url, capture_date_persian, ocr_text, quoted_tweet)

        print(f"[DEBUG] format_tweet_message: message_len={len(message)}, ocr_len={len(ocr_text)}, quote_len={len(quote_text)}")

        # If within limit, return as-is
        if len(message) <= TelegramConfig.MAX_CAPTION_LENGTH:
            return message, None

        # Calculate how much we need to trim
        excess = len(message) - TelegramConfig.MAX_CAPTION_LENGTH + 3  # +3 for "..."

        # Truncate text and regenerate
        if quote_text and ocr_text:
            # Both present: trim from the longer one first, prioritize main text
            if len(quote_text) > len(ocr_text) // 2:
                # Trim quote first
                trim_from_quote = min(excess, max(0, len(quote_text) - TelegramConfig.MIN_TEXT_KEEP_LENGTH))  # Keep at least MIN_TEXT_KEEP_LENGTH chars
                if trim_from_quote > 0:
                    quote_text = quote_text[:len(quote_text) - trim_from_quote] + '...'
                    excess -= trim_from_quote
                    quoted_tweet = {**quoted_tweet, 'text': quote_text}
            if excess > 0:
                # Still need to trim, take from main text
                ocr_text = ocr_text[:len(ocr_text) - excess] + '...'
        elif ocr_text:
            # Only main text, trim it
            ocr_text = ocr_text[:len(ocr_text) - excess] + '...'
        elif quote_text:
            # Only quote text, trim it
            quote_text = quote_text[:len(quote_text) - excess] + '...'
            quoted_tweet = {**quoted_tweet, 'text': quote_text}

        # Regenerate with truncated text
        message = self._build_html_message(username, tweet_url, capture_date_persian, ocr_text, quoted_tweet)

        print(f"[DEBUG] format_tweet_message after truncation: message_len={len(message)}")

        return message, None

    def _build_html_message(self, username, tweet_url, capture_date_persian, ocr_text, quoted_tweet):
        """Build the HTML formatted message."""
        parts = []

        # Header with linked username
        parts.append(f'🌐 <a href="{tweet_url}">{self._escape_html(username)}</a>\n')

        # Main tweet text - use expandable blockquote if text exceeds threshold
        if ocr_text:
            threshold = TelegramConfig.EXPANDABLE_BLOCKQUOTE_THRESHOLD
            if threshold > 0 and len(ocr_text) > threshold:
                # Use expandable blockquote for long text
                parts.append(f'\n\n<blockquote expandable>{self._escape_html(ocr_text)}</blockquote>\n')
            else:
                parts.append(f'\n {self._escape_html(ocr_text)}\n')

        # Quoted tweet as blockquote if available
        if quoted_tweet and quoted_tweet.get('text'):
            quote_text = quoted_tweet.get('text', '').strip()
            quote_handle = quoted_tweet.get('handle', '').lstrip('@')
            quote_url = quoted_tweet.get('url', '')

            if quote_text:
                # Format the quote attribution as a linked handle inside the blockquote
                if quote_handle and quote_url:
                    quote_attribution = f'<a href="{quote_url}">{self._escape_html(quote_handle)}</a>'
                elif quote_handle:
                    quote_attribution = f'{self._escape_html(quote_handle)}'
                else:
                    quote_attribution = ''

                # Also use expandable blockquote for long quotes
                threshold = TelegramConfig.EXPANDABLE_BLOCKQUOTE_THRESHOLD
                if threshold > 0 and len(quote_text) > threshold:
                    parts.append(f'\n<blockquote expandable>💬 {quote_attribution}\n\n{self._escape_html(quote_text)}</blockquote>\n')
                else:
                    parts.append(f'\n<blockquote>💬 {quote_attribution}\n\n{self._escape_html(quote_text)}</blockquote>\n')

        # Date at the end
        parts.append(f'\n📅 {self._escape_html(capture_date_persian)}')
        parts.append(f'\n{self._escape_html(self.CHANNEL_NAME)}')

        return "".join(parts)

    def format_multi_tweet_message(self, batch_data):
        """
        Format a batch of captured tweets for display in Telegram.
        
        Creates a caption with all unique authors mentioned.
        
        Args:
            batch_data: Dict with items (list of tweet data), unique_authors, capture_date_persian
            
        Returns:
            Formatted message string
        """
        unique_authors = batch_data.get('unique_authors', [])
        capture_date_persian = batch_data.get('capture_date_persian', '')
        items = batch_data.get('items', [])

        # Build author links - each author linked to their tweet
        author_links = []
        author_urls = {}

        # Map authors to their tweet URLs
        for item in items:
            username = item.get('username', '')
            tweet_url = item.get('tweet_url', '')
            if username and username not in author_urls:
                author_urls[username] = tweet_url

        # Create linked author names
        for author in unique_authors:
            url = author_urls.get(author, f"https://twitter.com/{author}")
            author_links.append(f"<a href='{url}'>{author}</a>")

        # Format the author line
        if len(author_links) == 1:
            authors_text = author_links[0]
        elif len(author_links) == 2:
            authors_text = f"{author_links[0]} و {author_links[1]}"  # Persian "and"
        else:
            # Join all but last with comma, then add last with "and"
            authors_text = "، ".join(author_links[:-1]) + f" و {author_links[-1]}"

        parts = []
        entities = []
        current_len = 0

        current_len = self._append_text(parts, current_len, "🌐 ")
        current_len = self._append_text(parts, current_len, authors_text)
        current_len = self._append_text(parts, current_len, "\n")

        # Add text from all tweets in the batch
        has_added_text = False
        for item in items:
            ocr_text = item.get('ocr_text', '').strip()
            quoted_tweet = item.get('quoted_tweet')

            if not ocr_text and not (quoted_tweet and quoted_tweet.get('text')):
                continue

            # Add separator if this isn't the first text block
            if has_added_text:
                current_len = self._append_text(parts, current_len, "\n---\n")
            
            has_added_text = True

            # Add main OCR text
            if ocr_text:
                # Per-tweet limit to prevent overfilling caption
                per_tweet_limit = TelegramConfig.OCR_TEXT_MAX_LENGTH
                if len(items) > 1:
                    per_tweet_limit = max(100, 600 // len(items))
                
                if len(ocr_text) > per_tweet_limit:
                    ocr_text = ocr_text[:per_tweet_limit] + '...'
                
                current_len = self._append_text(parts, current_len, f"\n {ocr_text}\n")

            # Add quoted tweet if available for this item
            if quoted_tweet and quoted_tweet.get('text'):
                quote_text = quoted_tweet.get('text', '').strip()
                quote_handle = quoted_tweet.get('handle', '').lstrip('@')
                quote_url = quoted_tweet.get('url', '')

                if quote_text:
                    # Truncate quoted text if too long
                    per_quote_limit = TelegramConfig.QUOTED_TEXT_MAX_LENGTH
                    if len(items) > 1:
                        per_quote_limit = max(50, 200 // len(items))
                    
                    if len(quote_text) > per_quote_limit:
                        quote_text = quote_text[:per_quote_limit] + '...'

                    # Add handle link
                    current_len = self._append_text(parts, current_len, "\n💬 ")
                    if quote_handle:
                        handle_offset = current_len
                        current_len = self._append_text(parts, current_len, quote_handle)
                        if quote_url:
                            entities.append(
                                MessageEntity(
                                    type="text_link",
                                    offset=handle_offset,
                                    length=self._utf16_len(quote_handle),
                                    url=quote_url
                                )
                            )
                    current_len = self._append_text(parts, current_len, "\n")

                    # Quote text in blockquote
                    quote_offset = current_len
                    current_len = self._append_text(parts, current_len, quote_text)
                    
                    threshold = TelegramConfig.EXPANDABLE_BLOCKQUOTE_THRESHOLD
                    blockquote_type = "expandable_blockquote" if threshold > 0 and len(quote_text) > threshold else "blockquote"
                    entities.append(
                        MessageEntity(
                            type=blockquote_type,
                            offset=quote_offset,
                            length=self._utf16_len(quote_text)
                        )
                    )
                    current_len = self._append_text(parts, current_len, "\n")

        # Date at the end
        current_len = self._append_text(parts, current_len, f"\n📅 {capture_date_persian}")
        current_len = self._append_text(parts, current_len, f"\n{self.CHANNEL_NAME}")

        return "".join(parts), entities

    def on_captured_tweet(self, tweet_data):
        """
        Handle a captured tweet from the queue worker.
        
        Supports both single tweets and batch results.
        
        Args:
            tweet_data: Dict with screenshot_path, video_paths, username, tweet_id, etc.
                       Or batch result with is_batch=True, items list, unique_authors
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if this is a batch result
            if tweet_data.get('is_batch', False):
                return self._handle_batch_result(tweet_data)

            # Single tweet processing
            tweet_id = tweet_data['tweet_id']
            screenshot_path = tweet_data['screenshot_path']
            video_paths = tweet_data.get('video_paths', [])
            chat_id = tweet_data.get('chat_id')
            user_name = tweet_data.get('user_name', '')
            bot_type = tweet_data.get('bot_type', 'suggestions')
            ocr_author = tweet_data.get('ocr_author', '')
            ocr_text = tweet_data.get('ocr_text', '')

            disable_duplicate_checks = os.environ.get("ZAM_DISABLE_DUPLICATE_TWEETS", "0") == "1"

            # Check if already posted
            if not disable_duplicate_checks and self.db.check_tweet_existence(tweet_id):
                return False

            # Format the message
            tg_text, entities = self.format_tweet_message(tweet_data)

            # Create media array with the screenshot and any videos
            media_list = [[screenshot_path, 'photo']]

            # Add videos to media list (they will be sent as a media group)
            for video_path in video_paths:
                if video_path and os.path.exists(video_path):
                    media_list.append([video_path, 'video'])

            media_array = self.make_media_array(tg_text, media_list, entities=entities)
            print(f"[DEBUG] on_captured_tweet: entities={entities}")

            # Send to the appropriate channel (sync because we need the message_id)
            sent_messages = self.message_queue.send_media_group_sync(
                chat_id=self.CHAT_ID,
                media=media_array
            )
            sent_message = sent_messages[0]

            # Add time selection buttons
            reply_markup, markup_text = self.make_time_options(tweet_id)
            self.message_queue.send_message_sync(
                chat_id=self.CHAT_ID,
                text=markup_text,
                reply_markup=reply_markup,
                reply_to_message_id=sent_message.message_id
            )

            # Log the tweet
            tweet_line_args = {
                'tweet_id': tweet_id,
                'tweet_text': tg_text,
                'media_list': media_list
            }
            self.db.add_tweet_to_line(tweet_line_args)

            log_args = {
                'tweet_id': tweet_id,
                'tweet_text': tg_text,
                'user_name': user_name,
                'status': 'Success',
                'admin': bot_type == 'admin',
                'ocr_author': ocr_author,
                'ocr_text': ocr_text
            }
            self.db.tweet_log(log_args)

            # Notify the user that their tweet was processed (async, don't need result)
            if chat_id:
                video_count = len(video_paths)
                if video_count > 0:
                    notification_text = f"✅ Your tweet has been processed!\n📸 Screenshot captured\n🎬 {video_count} video(s) captured"
                else:
                    notification_text = "✅ Your tweet has been processed and sent to the admin channel!"

                self.message_queue.send_message(
                    chat_id=chat_id,
                    text=notification_text
                )

            return True

        except Exception as e:
            self.db.error_log(e)
            return False

    def _handle_batch_result(self, batch_data):
        """
        Handle a batch of captured tweets, sending them as a single media group.
        
        Args:
            batch_data: Dict with is_batch=True, items, unique_authors, etc.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            disable_duplicate_checks = os.environ.get("ZAM_DISABLE_DUPLICATE_TWEETS", "0") == "1"
            items = batch_data.get('items', [])
            chat_id = batch_data.get('chat_id')
            user_name = batch_data.get('user_name', '')
            bot_type = batch_data.get('bot_type', 'suggestions')
            batch_id = batch_data.get('batch_id', '')

            if not items:
                print(f"Batch {batch_id}: No items to process")
                return False

            # Filter to items that have valid screenshots
            valid_items = [
                item for item in items
                if item.get('screenshot_path') and os.path.exists(item.get('screenshot_path', ''))
            ]

            if not valid_items:
                print(f"Batch {batch_id}: No valid screenshots found")
                return False

            print(f"Processing batch {batch_id} with {len(valid_items)} valid items")

            # Format the multi-tweet message
            tg_text, entities = self.format_multi_tweet_message(batch_data)

            # Build media list - Telegram allows max 10 items per media group
            media_list = []
            for item in valid_items[:10]:  # Limit to 10 items (Telegram limit)
                screenshot_path = item.get('screenshot_path')
                if screenshot_path and os.path.exists(screenshot_path):
                    media_list.append([screenshot_path, 'photo'])

                # Add videos for this tweet
                for video_path in item.get('video_paths', []):
                    if video_path and os.path.exists(video_path):
                        media_list.append([video_path, 'video'])
                        if len(media_list) >= 10:  # Respect Telegram limit
                            break

                if len(media_list) >= 10:
                    break

            if not media_list:
                print(f"Batch {batch_id}: No media to send")
                return False

            # Create media array
            media_array = self.make_media_array(tg_text, media_list, entities=entities)

            # Send to the appropriate channel
            sent_messages = self.message_queue.send_media_group_sync(
                chat_id=self.CHAT_ID,
                media=media_array
            )
            sent_message = sent_messages[0]

            # Use the first tweet_id for time options (or create a combined ID)
            first_tweet_id = valid_items[0].get('tweet_id', batch_id)

            # Add time selection buttons
            reply_markup, markup_text = self.make_time_options(first_tweet_id)
            self.message_queue.send_message_sync(
                chat_id=self.CHAT_ID,
                text=markup_text,
                reply_markup=reply_markup,
                reply_to_message_id=sent_message.message_id
            )

            # Log each tweet in the batch
            for item in valid_items:
                tweet_id = item.get('tweet_id', '')

                # Skip if already posted
                if not disable_duplicate_checks and self.db.check_tweet_existence(tweet_id):
                    continue

                # Add to tweets line (for scheduling)
                tweet_line_args = {
                    'tweet_id': tweet_id,
                    'tweet_text': tg_text,
                    'media_list': media_list
                }
                self.db.add_tweet_to_line(tweet_line_args)

                # Log the tweet
                log_args = {
                    'tweet_id': tweet_id,
                    'tweet_text': tg_text,
                    'user_name': user_name,
                    'status': 'Success',
                    'admin': bot_type == 'admin',
                    'ocr_author': item.get('ocr_author', ''),
                    'ocr_text': item.get('ocr_text', '')
                }
                self.db.tweet_log(log_args)

            # Notify the user
            if chat_id:
                notification_text = (
                    f"✅ Your batch of {len(valid_items)} tweets has been processed!\n"
                    f"📦 Batch ID: {batch_id}\n"
                    f"📸 All screenshots combined into a single post."
                )
                self.message_queue.send_message(
                    chat_id=chat_id,
                    text=notification_text
                )

            return True

        except Exception as e:
            print(f"Error handling batch result: {e}")
            self.db.error_log(e)
            return False

    def callback_query_handler(self, update, context=None):
        """Handle callback queries from inline keyboards."""
        user_name = self.get_user_name(update)
        query = update.callback_query
        query_text = query.data.split('|')
        query_type = query_text[0]
        query_dict = query.to_dict()
        chat_id = query_dict['message']['chat']['id']

        try:
            tg_text = query.message.reply_to_message.text
            entities = query.to_dict()['message']['reply_to_message']['entities']

            if tg_text is None:
                tg_text = query.message.reply_to_message.caption
                entities = query.to_dict()['message']['reply_to_message']['caption_entities']
        except:
            tg_text = None
            entities = None

        if query_type == 'TIME':
            tweet_id = query_text[2]
            time_now = dt.datetime.now()
            time_now = time_now.replace(second=0, microsecond=0)
            if query_text[1] == 'AUTO':
                desired_time = self._get_next_sending_time()
            else:
                desired_time = time_now + dt.timedelta(minutes=int(query_text[1]))
            desired_time_str = desired_time.strftime("%Y-%m-%d %H:%M:%S")
            desired_time_persian = covert_tweet_time_to_desired_time(desired_time_str, self.time_diff)
            self.db.set_sending_time_for_tweet_in_line(tweet_id, sending_time=desired_time_str, tweet_text=tg_text, entities=entities, query=query_dict)

            button_list = [InlineKeyboardButton("Cancel ❌", callback_data=f"CANCEL|{tweet_id}")]
            reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
            success_message = f"Tweet has been scheduled for {desired_time_persian} (Iran time-zone).\nYou can edit the text or caption of the message till the sending time.\nAlso, you can cancel it via Cancel button."
            query.edit_message_text(text=success_message, reply_markup=reply_markup)

        elif query_type == 'CANCEL':
            tweet_id = query_text[1]
            reply_markup, markup_text = self.make_time_options(tweet_id)
            self.db.set_sending_time_for_tweet_in_line(tweet_id, sending_time=None, tweet_text=tg_text, entities=None, query=None)
            query.edit_message_text(text=markup_text, reply_markup=reply_markup)

        elif query_type == 'SENT':
            tweet_id = query_text[2]
            sent_time = query_text[1]
            tweet = self.db.get_tweet_by_tweet_id(tweet_id)
            admin_user_name = tweet[2] if tweet else 'Unknown'
            query.answer(text=f"Sent by {admin_user_name} at {sent_time} Iran time-zone")

    def make_time_options(self, tweet_id):
        """Create time selection inline keyboard."""
        button_list = []
        for time_option in range(0, TelegramConfig.TIME_OPTIONS_MAX_MINUTES, TelegramConfig.TIME_OPTIONS_INTERVAL):
            inline_key = InlineKeyboardButton(f"{time_option} min later", callback_data=f"TIME|{time_option}|{tweet_id}")
            button_list.append(inline_key)
        # Automatic option
        inline_key = InlineKeyboardButton("Auto timing", callback_data=f"TIME|AUTO|{tweet_id}")
        button_list.append(inline_key)
        reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=3))
        markup_text = "Please select a time for sending this tweet."
        return reply_markup, markup_text

    def _get_next_sending_time(self, desired_num_tweets_per_hour=None, min_gap_minutes=None):
        """
        Calculate the next available sending time using weighted slot selection.
        
        Features:
        - Peak hour weighting (evening/night get more tweets)
        - Minimum gap enforcement between tweets
        - Quiet hours with reduced frequency
        - Next-day rollover support
        
        Args:
            desired_num_tweets_per_hour: Target tweets per hour (used for slot calculation)
            min_gap_minutes: Minimum minutes between consecutive tweets
            
        Returns:
            datetime: The next available sending time
        """

        if desired_num_tweets_per_hour is None:
            desired_num_tweets_per_hour = TelegramConfig.DEFAULT_TWEETS_PER_HOUR
        if min_gap_minutes is None:
            min_gap_minutes = TelegramConfig.MIN_GAP_MINUTES

        time_now = dt.datetime.now().replace(second=0, microsecond=0)

        # Get all scheduled tweet times
        scheduled_times = self._get_scheduled_times()

        # Try to find a slot for today and tomorrow
        for day_offset in range(2):
            base_date = time_now + dt.timedelta(days=day_offset)

            # Generate candidate slots (every 5 minutes)
            candidate_slots = self._generate_candidate_slots(base_date, time_now, day_offset)

            # Filter slots that respect minimum gap
            valid_slots = self._filter_by_gap(candidate_slots, scheduled_times, min_gap_minutes)

            if valid_slots:
                # Apply hour weights and select
                selected_slot = self._weighted_random_select(valid_slots)
                return selected_slot

        # Fallback: return next available 5-minute mark
        fallback_time = time_now + dt.timedelta(minutes=min_gap_minutes)
        # Round up to next 5-minute mark
        minutes_to_add = (5 - fallback_time.minute % 5) % 5
        return fallback_time + dt.timedelta(minutes=minutes_to_add)

    def _get_scheduled_times(self):
        """Get all currently scheduled tweet times."""
        tweets_line = self.db.get_tweets_line()
        scheduled_times = []
        for tweet in tweets_line:
            sending_time = tweet[4]  # sending_time is at index 4
            if sending_time is not None:
                if isinstance(sending_time, str):
                    scheduled_times.append(dt.datetime.strptime(sending_time, '%Y-%m-%d %H:%M:%S'))
                else:
                    scheduled_times.append(sending_time)
        return scheduled_times

    def _generate_candidate_slots(self, base_date, time_now, day_offset):
        """Generate candidate time slots for a given day."""
        slots = []

        if day_offset == 0:
            # Today: start from current time + 2 minutes, rounded to next 5-min mark
            start_time = time_now + dt.timedelta(minutes=2)
            start_minute = ((start_time.minute // 5) + 1) * 5
            if start_minute >= 60:
                start_hour = start_time.hour + 1
                start_minute = 0
            else:
                start_hour = start_time.hour
        else:
            # Tomorrow: start from 6 AM
            start_hour = 6
            start_minute = 0

        # Generate slots from start time until end of day
        for hour in range(start_hour, 24):
            minute_start = start_minute if hour == start_hour else 0
            for minute in range(minute_start, 60, 5):
                slot_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if day_offset > 0:
                    slot_time = slot_time.replace(day=base_date.day)
                slots.append(slot_time)

        return slots

    def _filter_by_gap(self, candidate_slots, scheduled_times, min_gap_minutes):
        """Filter slots that maintain minimum gap from scheduled tweets."""
        valid_slots = []
        min_gap = dt.timedelta(minutes=min_gap_minutes)

        for slot in candidate_slots:
            is_valid = True
            for scheduled in scheduled_times:
                if abs(slot - scheduled) < min_gap:
                    is_valid = False
                    break
            if is_valid:
                valid_slots.append(slot)

        return valid_slots

    def _weighted_random_select(self, valid_slots):
        """Select a slot using hour-based weights."""
        import random

        if not valid_slots:
            return None

        # Calculate weights for each slot based on hour
        weights = []
        for slot in valid_slots:
            hour_weight = TelegramConfig.HOUR_WEIGHTS[slot.hour]
            weights.append(hour_weight)

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(valid_slots)

        # Weighted random selection
        r = random.uniform(0, total_weight)
        cumulative = 0
        for slot, weight in zip(valid_slots, weights):
            cumulative += weight
            if r <= cumulative:
                return slot

        return valid_slots[-1]  # Fallback

    def get_user_name(self, update):
        """Extract username from update object."""
        user_name = None
        try:
            user_name = update.message.chat['username']
        except:
            try:
                user_name = update.message['from']['username']
            except:
                try:
                    user_name = update.message.from_user.username
                except:
                    try:
                        user_name = update.callback_query.from_user.username
                    except:
                        pass
        return user_name

    def check_admin(self, update):
        """Check if the user is an admin."""
        user_name = self.get_user_name(update)
        admin_ids = self.creds.get("ADMIN_IDS", [])
        if user_name in admin_ids:
            return True, user_name
        else:
            return False, user_name

    def build_menu(self, buttons, n_cols, header_buttons=None, footer_buttons=None):
        """Build a menu from buttons."""
        menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        if header_buttons:
            menu.insert(0, [header_buttons])
        if footer_buttons:
            menu.append([footer_buttons])
        return menu


class TelegramAdminBot(TelegramBot):
    """Admin bot for managing tweets."""

    def __init__(self, creds, twitter_api, db, suggestions_bot, time_diff, mahsa_message, num_tweets_to_preserve, reference_snapshot):
        super().__init__(creds, db, twitter_api, time_diff, reference_snapshot)
        self.CHAT_ID = creds["ADMIN_CHAT_ID"]
        self.TOKEN = creds["ADMIN_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.MAIN_CHANNEL_CHAT_ID = creds["MAIN_CHANNEL_CHAT_ID"]
        self.bot = Bot(token=self.TOKEN)
        self.suggestions_bot = suggestions_bot
        self.mahsa_message = mahsa_message
        self.num_tweets_to_preserve = num_tweets_to_preserve
        self.telegraph_client = telegraph(account_name=self.CHANNEL_NAME.split('@')[1])

        # Initialize message queue for rate-limited sending
        self.message_queue = TelegramMessageQueue(self.bot, db=self.db)
        self.message_queue.start()

        # Set up the Twitter API callback for admin bot
        self.twitter_api.set_telegram_callback(self._handle_captured_tweet)

        # Set up handlers - handle messages directly (no thread spawning)
        updater = Updater(self.TOKEN, use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("queue", self.queue_status))
        dp.add_handler(CommandHandler("stats", self.stats_command))
        dp.add_handler(MessageHandler(Filters.text, self.text_handler))
        dp.add_handler(CallbackQueryHandler(self.callback_query_handler))
        updater.start_polling()

        # Start background threads
        self.check_for_tweet_in_line_thread = threading.Thread(target=self.check_for_tweet_in_line, daemon=True)
        self.check_for_tweet_in_line_thread.start()

        if self.mahsa_message:
            self.time_counter_thread = threading.Thread(target=self.time_counter, daemon=True)
            self.time_counter_thread.start()

        # Start the queue worker
        self.twitter_api.start_queue_worker()

    def _handle_captured_tweet(self, tweet_data):
        """
        Callback for handling captured tweets from the queue worker.
        Routes to the appropriate bot based on bot_type.
        """
        bot_type = tweet_data.get('bot_type', 'suggestions')

        if bot_type == 'admin':
            return self.on_captured_tweet(tweet_data)
        else:
            # Route to suggestions bot
            if self.suggestions_bot:
                return self.suggestions_bot.on_captured_tweet(tweet_data)
            return False

    def queue_status(self, update, context=None):
        """Handle /queue command - show queue status."""
        admin_bool, _ = self.check_admin(update)
        if not admin_bool:
            return

        pending_count = self.db.get_pending_count()
        update.message.reply_text(f"📊 Queue Status:\n\n📝 Pending tweets: {pending_count}")

    def stats_command(self, update, context=None):
        """Handle /stats command - show comprehensive channel statistics."""
        admin_bool, _ = self.check_admin(update)
        if not admin_bool:
            return

        try:
            # Gather stats
            pending_count = self.db.get_pending_count()
            processing_count = self.db.get_processing_count()
            scheduled_count = self.db.get_scheduled_count()
            posts_today = self.db.get_posts_sent_today()
            next_scheduled = self.db.get_next_scheduled_tweet()
            hourly_dist = self.db.get_hourly_distribution(hours_ahead=6)

            # Format next scheduled time
            if next_scheduled:
                if isinstance(next_scheduled, str):
                    next_scheduled = dt.datetime.strptime(next_scheduled, '%Y-%m-%d %H:%M:%S')
                time_until = next_scheduled - dt.datetime.now()
                minutes_until = int(time_until.total_seconds() / 60)
                next_str = f"{next_scheduled.strftime('%H:%M')} (in {minutes_until} min)"
            else:
                next_str = "None scheduled"

            # Build the stats message
            stats_msg = "📊 *Channel Statistics*\n\n"

            # Queue status
            stats_msg += "📝 *Queue Status:*\n"
            stats_msg += f"   • Pending captures: {pending_count}\n"
            stats_msg += f"   • Currently processing: {processing_count}\n\n"

            # Scheduled posts
            stats_msg += "📅 *Scheduled Posts:*\n"
            stats_msg += f"   • Awaiting posting: {scheduled_count}\n"
            stats_msg += f"   • Next post: {next_str}\n\n"

            # Today's activity
            stats_msg += "📈 *Today's Activity:*\n"
            stats_msg += f"   • Posts sent: {posts_today}\n\n"

            # Peak hours availability
            stats_msg += "⏰ *Next 6 Hours Availability:*\n"
            for hour, count, max_slots in hourly_dist:
                # Create visual progress bar
                filled = min(count, max_slots)
                empty = max_slots - filled
                bar = "█" * filled + "░" * empty
                hour_str = f"{hour:02d}:00"
                status = "FULL" if count >= max_slots else f"{count}/{max_slots}"
                stats_msg += f"`{hour_str}` {bar} {status}\n"

            # Use message queue for response
            self.message_queue.send_message(
                chat_id=update.message.chat_id,
                text=stats_msg,
                parse_mode='Markdown'
            )

        except Exception as e:
            self.db.error_log(e)
            self.message_queue.send_message(
                chat_id=update.message.chat_id,
                text="❌ Error fetching statistics. Please try again."
            )

    def text_handler(self, update, context=None):
        """Handle incoming text messages (no thread spawning)."""
        try:
            admin_bool, user_name = self.check_admin(update)
            chat_id = update.message.chat_id
            self.db.set_state(str(chat_id), None)
        except:
            return

        if admin_bool:
            message_text = update.message.text.strip()

            # Check if it contains any valid tweet URLs
            if "twitter.com" in message_text or "x.com" in message_text:
                self.receive_tweet(update, user_name)
            else:
                self.message_queue.send_message(
                    chat_id=chat_id,
                    text='Please send a valid tweet URL (twitter.com or x.com)'
                )

    def receive_tweet(self, update, user_name):
        """
        Process received tweet URLs (supports multiple URLs, one per line).
        
        Multiple URLs will be grouped as a batch and sent as a single media group.
        """
        message_text = update.message.text.strip()
        chat_id = str(update.message.chat_id)

        # Extract all tweet URLs from the message (one per line or space-separated)
        tweet_urls = self._extract_tweet_urls(message_text)

        if not tweet_urls:
            self.message_queue.send_message(
                chat_id=chat_id,
                text='❌ No valid tweet URLs found in your message.'
            )
            return

        # Generate batch ID if multiple URLs
        batch_id = None
        batch_total = len(tweet_urls)
        if batch_total > 1:
            import uuid
            batch_id = str(uuid.uuid4())[:8]  # Short unique ID

        # Add each URL to queue
        added_count = 0
        failed_urls = []
        first_position = None

        for tweet_url in tweet_urls:
            queue_id, result = self.twitter_api.add_to_queue(
                tweet_url=tweet_url,
                user_name=user_name,
                chat_id=chat_id,
                bot_type='admin',
                batch_id=batch_id,
                batch_total=batch_total
            )

            if queue_id:
                added_count += 1
                if first_position is None:
                    first_position = result
            else:
                failed_urls.append((tweet_url, result))

        # Send feedback
        if added_count > 0:
            if batch_total == 1:
                self.message_queue.send_message(
                    chat_id=chat_id,
                    text=f"✅ Tweet added to queue!\n\n"
                    f"📍 Position: {first_position}\n"
                    f"⏳ You'll be notified when it's processed."
                )
            else:
                msg = f"✅ {added_count}/{batch_total} tweets added to queue!\n\n"
                msg += f"📍 Starting position: {first_position}\n"
                msg += f"📦 Batch ID: {batch_id}\n"
                msg += "⏳ All tweets will be combined into a single post."

                if failed_urls:
                    msg += f"\n\n⚠️ Failed to add {len(failed_urls)} tweet(s):"
                    for url, reason in failed_urls[:3]:  # Show first 3
                        short_url = url[:50] + '...' if len(url) > 50 else url
                        msg += f"\n• {short_url}: {reason}"

                self.message_queue.send_message(chat_id=chat_id, text=msg)
        else:
            error_msg = "❌ Could not add any tweets:\n"
            for url, reason in failed_urls[:5]:
                short_url = url[:50] + '...' if len(url) > 50 else url
                error_msg += f"\n• {short_url}: {reason}"
            self.message_queue.send_message(chat_id=chat_id, text=error_msg)

    def _extract_tweet_urls(self, text):
        """
        Extract all valid tweet URLs from text.
        
        Args:
            text: Message text potentially containing multiple URLs
            
        Returns:
            List of valid tweet URLs
        """
        import re

        # Pattern for twitter.com and x.com URLs
        pattern = r'https?://(?:mobile\.)?(?:twitter\.com|x\.com)/\w+/status/\d+'

        # Find all matches
        urls = re.findall(pattern, text)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            # Normalize URL
            normalized = self.twitter_api.normalize_tweet_url(url)
            if normalized not in seen:
                seen.add(normalized)
                unique_urls.append(normalized)

        return unique_urls

    def time_counter(self):
        """Background thread for the Mahsa Amini time counter."""
        message_txt = "minutes have passed since when the brutal Islamic Regime took the life of our brave Mahsa, but our resolve remains unbroken. We will never forget, nor forgive the injustice that has been done 💔\n\nBut we do not mourn alone, for we stand united as a force to be reckoned with, a force that will fight with every breath and every beat of our hearts until justice is served ⚖️\n\nWe will not rest until we have reclaimed our rights and taken back what is rightfully ours. This is not just a cry for justice, but a call to arms - the sound of our REVOLUTION 🔥\n\n#MahsaAmini\n#WomanLifeFreedom\n\n@Tweets_SUT"
        mahsa_death_time = TelegramConfig.MAHSA_DEATH_TIME
        message_id = self.db.get_time_counter_message_id()

        if message_id is None:
            time_now = dt.datetime.now()
            diff_time = time_now - mahsa_death_time
            message_caption = form_time_counter_message(diff_time, message_txt)
            media_array = self.make_media_array(message_caption, [[TelegramConfig.MAHSA_FLAG_IMAGE_URL, 'photo']])
            try:
                result = self.message_queue.send_media_group_sync(
                    chat_id=self.MAIN_CHANNEL_CHAT_ID,
                    media=media_array
                )
                message_id = result[0]['message_id']
                self.db.set_time_counter_message_id(str(message_id))
            except Exception as e:
                print(f"Failed to create time counter message: {e}")
                return

        while True:
            try:
                time_now = dt.datetime.now()
                diff_time = time_now - mahsa_death_time
                message_caption = form_time_counter_message(diff_time, message_txt)
                # Queue the edit (async)
                self.message_queue.edit_message_media(
                    chat_id=self.MAIN_CHANNEL_CHAT_ID,
                    message_id=message_id,
                    media=InputMediaPhoto(TelegramConfig.MAHSA_FLAG_IMAGE_URL, message_caption)
                )
            except Exception as e:
                print(f"Time counter error: {e}")
            time.sleep(TelegramConfig.TIME_COUNTER_UPDATE_INTERVAL)

    def check_for_tweet_in_line(self):
        """Background thread to check for scheduled tweets."""
        while True:
            try:
                tweets_line = self.db.get_tweets_line()
                if tweets_line:
                    for tweet in tweets_line:
                        tweet_id = tweet[1]  # tweet_id is at index 1 in PostgreSQL
                        tweet_text = tweet[2]
                        media_list = tweet[3]
                        tweet_sent_time = tweet[4]
                        entities = tweet[5]
                        query = tweet[6]

                        if tweet_sent_time:
                            # Handle both string and datetime objects
                            if isinstance(tweet_sent_time, str):
                                tweet_sent_time_dt = dt.datetime.strptime(tweet_sent_time, '%Y-%m-%d %H:%M:%S')
                            else:
                                tweet_sent_time_dt = tweet_sent_time

                            desired_time_persian = covert_tweet_time_to_desired_time(
                                tweet_sent_time_dt.strftime('%Y-%m-%d %H:%M:%S'),
                                self.time_diff
                            )

                            if tweet_sent_time_dt <= dt.datetime.now():
                                try:
                                    query = json.loads(query) if query else {}
                                    entities = json.loads(entities) if entities else []
                                    media_list = json.loads(media_list) if media_list else []

                                    entities_list_converted = []
                                    for entity in entities:
                                        if 'url' in entity:
                                            converted_format = MessageEntity(
                                                type=entity['type'],
                                                offset=entity['offset'],
                                                length=entity['length'],
                                                url=entity['url']
                                            )
                                        else:
                                            converted_format = MessageEntity(
                                                type=entity['type'],
                                                offset=entity['offset'],
                                                length=entity['length']
                                            )
                                        entities_list_converted.append(converted_format)

                                    # Send via message queue (sync to ensure delivery before cleanup)
                                    if media_list:
                                        media_array = self.make_media_array(tweet_text, media_list, entities=entities_list_converted if entities_list_converted else None)
                                        self.message_queue.send_media_group_sync(
                                            chat_id=self.MAIN_CHANNEL_CHAT_ID,
                                            media=media_array
                                        )
                                    else:
                                        # For voice messages, add an inline button linked to the suggestions bot
                                        reply_markup_main = None
                                        if tweet_id.startswith("VOICE_"):
                                            bot_username = self.creds.get("SUGGESTIONS_BOT_ID", "").lstrip("@")
                                            if bot_username:
                                                keyboard = [[InlineKeyboardButton("🎤 Send your voice", url=f"https://t.me/{bot_username}")]]
                                                reply_markup_main = InlineKeyboardMarkup(keyboard)

                                        self.message_queue.send_message_sync(
                                            chat_id=self.MAIN_CHANNEL_CHAT_ID,
                                            text=tweet_text,
                                            disable_web_page_preview=True,
                                            entities=entities_list_converted if entities_list_converted else None,
                                            reply_markup=reply_markup_main
                                        )

                                    self.db.remove_tweet_from_line(tweet_id)
                                    self.db.remove_old_tweets_in_line(num_tweets_to_preserve=self.num_tweets_to_preserve)
                                    deleted_snapshots(media_list)

                                    button_list = [InlineKeyboardButton("Sent ✅", callback_data=f"SENT|{desired_time_persian}|{tweet_id}")]
                                    reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
                                    success_message = "Sent successfully."

                                    # Queue the edit (async is fine here)
                                    if query and 'message' in query:
                                        self.message_queue.edit_message_text(
                                            chat_id=query['message']['chat']['id'],
                                            message_id=query['message']['message_id'],
                                            text=success_message,
                                            reply_markup=reply_markup
                                        )

                                except Exception as e:
                                    self.db.error_log(e)

            except Exception as e:
                self.db.error_log(e)

            time.sleep(TelegramConfig.TWEET_LINE_CHECK_INTERVAL)


class TelegramSuggestedTweetsBot(TelegramBot):
    """Bot for handling suggested tweets from users with interactive menu."""

    # User states for conversation flow
    STATE_IDLE = 'idle'
    STATE_AWAITING_TWEET = 'awaiting_tweet'
    STATE_AWAITING_FEEDBACK = 'awaiting_feedback'
    STATE_AWAITING_VOICE_MESSAGE = 'awaiting_voice_message'
    STATE_AWAITING_VOICE_NAME = 'awaiting_voice_name'

    def __init__(self, creds, twitter_api, db, time_diff, reference_snapshot, user_tweet_limit):
        super().__init__(creds, db, twitter_api, time_diff, reference_snapshot)
        self.CHAT_ID = creds["SUGGESTIONS_CHAT_ID"]
        self.TOKEN = creds["SUGGESTIONS_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.bot = Bot(token=self.TOKEN)
        self.user_tweet_limit = user_tweet_limit

        # Store user feedback category temporarily
        self.user_feedback_category = {}
        # Store user voice message temporarily
        self.user_voice_message = {}

        # Initialize message queue for rate-limited sending
        self.message_queue = TelegramMessageQueue(self.bot, db=self.db)
        self.message_queue.start()

        # Set up handlers - handle messages directly (no thread spawning)
        updater = Updater(self.TOKEN, use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start_menu))
        dp.add_handler(MessageHandler(Filters.text, self.handle_text_message))
        dp.add_handler(CallbackQueryHandler(self.menu_callback_handler))
        updater.start_polling()

    def start_menu(self, update, context=None):
        """Show the main interactive menu."""
        user_name = self.get_user_name(update)
        chat_id = str(update.message.chat_id)

        # Reset user state
        self.db.set_state(chat_id, self.STATE_IDLE)

        # Get remaining submissions
        if self.user_tweet_limit > 0:
            remaining, total = self.db.get_user_remaining_submissions(user_name, self.user_tweet_limit)
            limit_text = f"\n\n📊 Submissions remaining: {remaining}/{total} this hour"
        else:
            limit_text = ""

        welcome_text = (
            f"🎯 *Welcome to {self.CHANNEL_NAME} Suggestions Bot!*\n\n"
            f"What would you like to do?"
            f"{limit_text}"
        )

        # Create menu buttons
        keyboard = [
            [
                InlineKeyboardButton("📤 Submit Tweet", callback_data="MENU|submit_tweet"),
                InlineKeyboardButton("💬 Send Feedback", callback_data="MENU|feedback")
            ],
            [
                InlineKeyboardButton("🎤 Send your voice", callback_data="MENU|send_voice")
            ],
            [
                InlineKeyboardButton("📊 My Remaining Submissions", callback_data="MENU|remaining")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        self.message_queue.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def menu_callback_handler(self, update, context=None):
        """Handle menu button callbacks."""
        query = update.callback_query
        query_data = query.data.split('|')
        query_type = query_data[0]

        user_name = query.from_user.username or str(query.from_user.id)
        chat_id = str(query.message.chat_id)

        if query_type == 'MENU':
            action = query_data[1]

            if action == 'submit_tweet':
                self._handle_submit_tweet_menu(query, chat_id)

            elif action == 'feedback':
                self._show_feedback_categories(query)

            elif action == 'send_voice':
                self._handle_voice_submission_start(query, chat_id)

            elif action == 'remaining':
                self._show_remaining_submissions(query, user_name)

            elif action == 'back':
                self._show_main_menu(query, user_name)

        elif query_type == 'FEEDBACK':
            category = query_data[1]
            self._handle_feedback_category(query, chat_id, category)

        # Also handle parent class callbacks (TIME, CANCEL, SENT)
        elif query_type in ('TIME', 'CANCEL', 'SENT'):
            self.callback_query_handler(update, context)

    def _handle_submit_tweet_menu(self, query, chat_id):
        """Set state to await tweet URL."""
        self.db.set_state(chat_id, self.STATE_AWAITING_TWEET)

        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "📤 *Submit a Tweet*\n\n"
            "Please send me the tweet URL (twitter.com or x.com link).\n\n"
            "Example: `https://x.com/user/status/123456789`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def _handle_voice_submission_start(self, query, chat_id):
        """Set state to await voice message."""
        self.db.set_state(chat_id, self.STATE_AWAITING_VOICE_MESSAGE)

        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "🎤 *Send your voice*\n\n"
            "Please type the message you'd like to share with the channel.\n\n"
            "This will be posted to the channel with your chosen name after admin approval.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def _show_feedback_categories(self, query):
        """Show feedback category selection."""
        keyboard = [
            [
                InlineKeyboardButton("💡 Suggestion", callback_data="FEEDBACK|suggestion"),
                InlineKeyboardButton("🐛 Bug Report", callback_data="FEEDBACK|bug")
            ],
            [
                InlineKeyboardButton("❓ Question", callback_data="FEEDBACK|question")
            ],
            [
                InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "💬 *Send Feedback*\n\n"
            "What type of message would you like to send?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def _handle_feedback_category(self, query, chat_id, category):
        """Set state to await feedback message."""
        self.db.set_state(chat_id, self.STATE_AWAITING_FEEDBACK)
        self.user_feedback_category[chat_id] = category

        category_emojis = {
            'suggestion': '💡',
            'bug': '🐛',
            'question': '❓'
        }
        category_names = {
            'suggestion': 'Suggestion',
            'bug': 'Bug Report',
            'question': 'Question'
        }

        emoji = category_emojis.get(category, '💬')
        name = category_names.get(category, 'Feedback')

        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            f"{emoji} *{name}*\n\n"
            f"Please type your message and send it.\n\n"
            f"Your message will be forwarded to the channel admins.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def _show_remaining_submissions(self, query, user_name):
        """Show remaining submissions for the user."""
        if self.user_tweet_limit > 0:
            remaining, total = self.db.get_user_remaining_submissions(user_name, self.user_tweet_limit)

            # Create a visual progress bar
            used = total - remaining
            bar_filled = "█" * used
            bar_empty = "░" * remaining

            text = (
                f"📊 *Your Submission Status*\n\n"
                f"Used: {used}/{total} this hour\n"
                f"`[{bar_filled}{bar_empty}]`\n\n"
                f"✅ Remaining: *{remaining}* submissions\n\n"
                f"_Limit resets every hour._"
            )
        else:
            text = (
                "📊 *Your Submission Status*\n\n"
                "✅ *Unlimited* submissions allowed!\n\n"
                "_There is no hourly limit set for this bot._"
            )

        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    def _show_main_menu(self, query, user_name):
        """Return to main menu."""
        chat_id = str(query.message.chat_id)
        self.db.set_state(chat_id, self.STATE_IDLE)

        # Clear any pending feedback category
        if chat_id in self.user_feedback_category:
            del self.user_feedback_category[chat_id]

        # Get remaining submissions
        if self.user_tweet_limit > 0:
            remaining, total = self.db.get_user_remaining_submissions(user_name, self.user_tweet_limit)
            limit_text = f"\n\n📊 Submissions remaining: {remaining}/{total} this hour"
        else:
            limit_text = ""

        welcome_text = (
            f"🎯 *Welcome to {self.CHANNEL_NAME} Suggestions Bot!*\n\n"
            f"What would you like to do?"
            f"{limit_text}"
        )

        keyboard = [
            [
                InlineKeyboardButton("📤 Submit Tweet", callback_data="MENU|submit_tweet"),
                InlineKeyboardButton("💬 Send Feedback", callback_data="MENU|feedback")
            ],
            [
                InlineKeyboardButton("🎤 Send your voice", callback_data="MENU|send_voice")
            ],
            [
                InlineKeyboardButton("📊 My Remaining Submissions", callback_data="MENU|remaining")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

    def handle_text_message(self, update, context=None):
        """Route text messages based on user state (no thread spawning)."""
        chat_id = str(update.message.chat_id)
        state = self.db.get_state(chat_id)

        if state == self.STATE_AWAITING_TWEET:
            self.receive_tweet(update, context)
        elif state == self.STATE_AWAITING_FEEDBACK:
            self.receive_feedback(update, context)
        elif state == self.STATE_AWAITING_VOICE_MESSAGE:
            self.receive_voice_message(update, context)
        elif state == self.STATE_AWAITING_VOICE_NAME:
            self.receive_voice_name(update, context)
        else:
            # Check if it's a tweet URL - handle it directly
            text = update.message.text.strip()
            if "twitter.com" in text or "x.com" in text:
                self.receive_tweet(update, context)
            else:
                # Prompt user to use menu
                keyboard = [[InlineKeyboardButton("📋 Open Menu", callback_data="MENU|back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                self.message_queue.send_message(
                    chat_id=chat_id,
                    text="👋 Please use the menu to interact with this bot.\n\n"
                         "Send /start or click the button below to open the menu.",
                    reply_markup=reply_markup
                )

    def receive_tweet(self, update, context=None):
        """
        Process suggested tweet URLs (supports multiple URLs, one per line).
        
        Multiple URLs will be grouped as a batch and sent as a single media group.
        """
        _, user_name = self.check_admin(update)
        chat_id = str(update.message.chat_id)
        message_text = update.message.text.strip()

        # Reset state
        self.db.set_state(chat_id, self.STATE_IDLE)

        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Extract all tweet URLs from the message
        tweet_urls = self._extract_tweet_urls(message_text)

        if not tweet_urls:
            self.message_queue.send_message(
                chat_id=chat_id,
                text='❌ No valid tweet URLs found. Please send valid twitter.com or x.com links.',
                reply_markup=reply_markup
            )
            return

        # Check rate limit (if enabled)
        if self.user_tweet_limit > 0:
            user_count = self.db.get_user_tweet_count_last_hour(user_name)
            # Check if adding these tweets would exceed the limit
            if user_count + len(tweet_urls) > self.user_tweet_limit:
                remaining = self.user_tweet_limit - user_count
                if remaining <= 0:
                    self.message_queue.send_message(
                        chat_id=chat_id,
                        text=f'⚠️ You have exceeded your hourly limit ({self.user_tweet_limit} tweets per hour).\n'
                             f'Please try again later.',
                        reply_markup=reply_markup
                    )
                    return
                else:
                    # Truncate to remaining limit
                    tweet_urls = tweet_urls[:remaining]
                    self.message_queue.send_message(
                        chat_id=chat_id,
                        text=f'⚠️ Only processing {remaining} tweet(s) due to your hourly limit.',
                        reply_markup=reply_markup
                    )

        # Generate batch ID if multiple URLs
        batch_id = None
        batch_total = len(tweet_urls)
        if batch_total > 1:
            import uuid
            batch_id = str(uuid.uuid4())[:8]

        # Add each URL to queue
        added_count = 0
        failed_urls = []
        first_position = None

        for tweet_url in tweet_urls:
            queue_id, result = self.twitter_api.add_to_queue(
                tweet_url=tweet_url,
                user_name=user_name,
                chat_id=chat_id,
                bot_type='suggestions',
                batch_id=batch_id,
                batch_total=batch_total
            )

            if queue_id:
                added_count += 1
                if first_position is None:
                    first_position = result
            else:
                failed_urls.append((tweet_url, result))

        if added_count > 0:
            # Notify suggestions channel about the new suggestion(s)
            if batch_total == 1:
                self.message_queue.send_message(
                    chat_id=self.CHAT_ID,
                    text=f"📥 New suggestion from @{user_name}"
                )
            else:
                self.message_queue.send_message(
                    chat_id=self.CHAT_ID,
                    text=f"📥 New batch of {added_count} suggestions from @{user_name} (batch: {batch_id})"
                )

            # Show remaining submissions
            if self.user_tweet_limit > 0:
                remaining, total = self.db.get_user_remaining_submissions(user_name, self.user_tweet_limit)
                remaining_text = f"\n\n📊 Remaining submissions: {remaining}/{total}"
            else:
                remaining_text = ""

            if batch_total == 1:
                self.message_queue.send_message(
                    chat_id=chat_id,
                    text=f"✅ Your tweet suggestion has been added to the queue!\n\n"
                    f"📍 Position: {first_position}\n"
                    f"⏳ You'll be notified when it's processed."
                    f"{remaining_text}",
                    reply_markup=reply_markup
                )
            else:
                msg = f"✅ {added_count}/{batch_total} tweets added to queue!\n\n"
                msg += f"📍 Starting position: {first_position}\n"
                msg += f"📦 Batch ID: {batch_id}\n"
                msg += "⏳ All tweets will be combined into a single post."
                msg += remaining_text

                if failed_urls:
                    msg += f"\n\n⚠️ Failed to add {len(failed_urls)} tweet(s):"
                    for url, reason in failed_urls[:3]:
                        short_url = url[:40] + '...' if len(url) > 40 else url
                        msg += f"\n• {short_url}: {reason}"

                self.message_queue.send_message(
                    chat_id=chat_id,
                    text=msg,
                    reply_markup=reply_markup
                )
        else:
            error_msg = "❌ Could not add any tweets:\n"
            for url, reason in failed_urls[:5]:
                short_url = url[:40] + '...' if len(url) > 40 else url
                error_msg += f"\n• {short_url}: {reason}"
            self.message_queue.send_message(
                chat_id=chat_id,
                text=error_msg,
                reply_markup=reply_markup
            )

    def _extract_tweet_urls(self, text):
        """
        Extract all valid tweet URLs from text.
        
        Args:
            text: Message text potentially containing multiple URLs
            
        Returns:
            List of valid tweet URLs
        """
        import re

        # Pattern for twitter.com and x.com URLs
        pattern = r'https?://(?:mobile\.)?(?:twitter\.com|x\.com)/\w+/status/\d+'

        # Find all matches
        urls = re.findall(pattern, text)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            # Normalize URL
            normalized = self.twitter_api.normalize_tweet_url(url)
            if normalized not in seen:
                seen.add(normalized)
                unique_urls.append(normalized)

        return unique_urls

    def receive_feedback(self, update, context=None):
        """Process feedback message from user."""
        user_name = self.get_user_name(update) or 'Anonymous'
        chat_id = str(update.message.chat_id)
        message = update.message.text.strip()

        # Get the category
        category = self.user_feedback_category.get(chat_id, 'general')

        # Reset state and clear category
        self.db.set_state(chat_id, self.STATE_IDLE)
        if chat_id in self.user_feedback_category:
            del self.user_feedback_category[chat_id]

        # Save to database
        self.db.add_user_feedback(user_name, chat_id, category, message)

        # Format category for display
        category_display = {
            'suggestion': '💡 SUGGESTION',
            'bug': '🐛 BUG REPORT',
            'question': '❓ QUESTION'
        }
        category_text = category_display.get(category, '💬 FEEDBACK')

        # Forward to admin channel (async)
        admin_message = (
            f"{category_text} from @{user_name}:\n\n"
            f"\"{message}\""
        )
        self.message_queue.send_message(
            chat_id=self.CHAT_ID,
            text=admin_message
        )

        # Confirm to user
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        self.message_queue.send_message(
            chat_id=chat_id,
            text="✅ Thank you for your feedback!\n\n"
                 "Your message has been sent to the channel admins.",
            reply_markup=reply_markup
        )

    def receive_voice_message(self, update, context=None):
        """Process the text message for 'Send your voice'."""
        chat_id = str(update.message.chat_id)
        message = update.message.text.strip()

        if not message:
            self.message_queue.send_message(
                chat_id=chat_id,
                text="❌ Please send a text message."
            )
            return

        # Store message and move to next state
        self.user_voice_message[chat_id] = message
        self.db.set_state(chat_id, self.STATE_AWAITING_VOICE_NAME)

        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        self.message_queue.send_message(
            chat_id=chat_id,
            text="🎤 *Great!*\n\nNow, what name should be shown with your message?\n"
                 "(e.g., your real name, a pseudonym, or 'Anonymous')",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def receive_voice_name(self, update, context=None):
        """Process the name for 'Send your voice' and post to channel."""
        chat_id = str(update.message.chat_id)
        name = update.message.text.strip()
        user_name = self.get_user_name(update) or 'Unknown'

        if not name:
            self.message_queue.send_message(
                chat_id=chat_id,
                text="❌ Please send a name."
            )
            return

        # Get the stored message
        message = self.user_voice_message.get(chat_id)
        
        # Reset state and clear temporary storage
        self.db.set_state(chat_id, self.STATE_IDLE)
        if chat_id in self.user_voice_message:
            del self.user_voice_message[chat_id]

        if not message:
            self.message_queue.send_message(
                chat_id=chat_id,
                text="❌ Something went wrong. Please try again from the menu."
            )
            return

        # Format the final message for the suggestions channel
        # Iranian time for date
        now_utc = dt.datetime.now()
        current_time_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
        # Use existing utility to get Persian date
        current_date_persian = covert_tweet_time_to_desired_time(current_time_str, self.time_diff).split(' ')[0]
        
        # Channel name from creds (e.g. @Tweets_SUT)
        main_channel = self.CHANNEL_NAME

        channel_post = (
            f"🎤 *Your Voice*\n\n"
            f"\"{message}\"\n\n"
            f"👤 {name}\n"
            f"📅  {current_date_persian}\n"
            f"{main_channel}"
        )

        # Generate a unique ID for this voice message to allow scheduling
        voice_id = f"VOICE_{int(time.time())}"

        # Add to the scheduled line table so admins can pick it up
        self.db.add_tweet_to_line({
            'tweet_id': voice_id,
            'tweet_text': channel_post
        })

        # Send to suggestions channel (sync because we need the message_id to reply with options)
        sent_messages = self.message_queue.send_message_sync(
            chat_id=self.CHAT_ID,
            text=channel_post,
            parse_mode='Markdown'
        )

        # Add scheduling buttons as a reply in the suggestions channel
        reply_markup, markup_text = self.make_time_options(voice_id)
        self.message_queue.send_message_sync(
            chat_id=self.CHAT_ID,
            text=markup_text,
            reply_markup=reply_markup,
            reply_to_message_id=sent_messages.message_id
        )

        # Confirm to user
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="MENU|back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        self.message_queue.send_message(
            chat_id=chat_id,
            text="✅ Your voice has been shared in the suggestions channel!\n\n"
                 "Thank you for your contribution.",
            reply_markup=reply_markup
        )
