import os
import json
import time
import threading
import datetime as dt
from telegram import Bot, InputMediaPhoto, InputMediaVideo, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from persiantools.jdatetime import JalaliDate

from utils import covert_tweet_time_to_desired_time, form_time_counter_message, deleted_snapshots, telegraph


class TelegramBot:
    """Base class for Telegram bots."""

    def __init__(self, creds, db, twitter_api, time_diff, reference_snapshot):
        self.creds = creds
        self.db = db
        self.twitter_api = twitter_api
        self.time_diff = time_diff
        self.reference_snapshot = reference_snapshot

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
                if entities:
                    media_tmp = InputMediaVideo(media[0], caption=caption, caption_entities=caption_entities)
                else:
                    media_tmp = InputMediaVideo(media[0], caption=caption, parse_mode="HTML")
            media_array.append(media_tmp)
        return media_array

    def format_tweet_message(self, tweet_data):
        """
        Format a captured tweet for display in Telegram.
        
        Args:
            tweet_data: Dict with screenshot_path, username, tweet_id, capture_date_persian, tweet_url
            
        Returns:
            Formatted message string
        """
        username = tweet_data['username']
        tweet_url = tweet_data['tweet_url']
        capture_date_persian = tweet_data['capture_date_persian']

        tg_text = f"✍️ <a href='{tweet_url}'>{username}</a>\n"
        tg_text += f"📅 {capture_date_persian}\n\n"
        tg_text += f"📢 {self.CHANNEL_NAME}"

        return tg_text

    def on_captured_tweet(self, tweet_data):
        """
        Handle a captured tweet from the queue worker.
        
        Args:
            tweet_data: Dict with screenshot_path, username, tweet_id, etc.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            tweet_id = tweet_data['tweet_id']
            screenshot_path = tweet_data['screenshot_path']
            chat_id = tweet_data.get('chat_id')
            user_name = tweet_data.get('user_name', '')
            bot_type = tweet_data.get('bot_type', 'suggestions')

            # Check if already posted
            if self.db.check_tweet_existence(tweet_id):
                return False

            # Format the message
            tg_text = self.format_tweet_message(tweet_data)

            # Create media array with the screenshot
            media_list = [[screenshot_path, 'photo']]
            media_array = self.make_media_array(tg_text, media_list)

            # Send to the appropriate channel
            sent_message = self.bot.sendMediaGroup(
                chat_id=self.CHAT_ID,
                media=media_array,
                timeout=1000
            )[0]

            # Add time selection buttons
            reply_markup, markup_text = self.make_time_options(tweet_id)
            self.bot.sendMessage(
                chat_id=self.CHAT_ID,
                text=markup_text,
                reply_markup=reply_markup,
                timeout=1000,
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
                'admin': bot_type == 'admin'
            }
            self.db.tweet_log(log_args)

            # Notify the user that their tweet was processed
            if chat_id:
                try:
                    self.bot.sendMessage(
                        chat_id=chat_id,
                        text=f"✅ Your tweet has been processed and sent to the admin channel!",
                        timeout=1000
                    )
                except Exception as e:
                    print(f"Failed to notify user: {e}")

            return True

        except Exception as e:
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
        for time_option in range(0, 16 * 30, 30):
            inline_key = InlineKeyboardButton(f"{time_option} min later", callback_data=f"TIME|{time_option}|{tweet_id}")
            button_list.append(inline_key)
        # Automatic option
        inline_key = InlineKeyboardButton("Auto timing", callback_data=f"TIME|AUTO|{tweet_id}")
        button_list.append(inline_key)
        reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=3))
        markup_text = "Please select a time for sending this tweet."
        return reply_markup, markup_text

    def _get_next_sending_time(self, desired_num_tweets_per_hour=6):
        """Calculate the next available sending time."""
        import random
        tweets_line = self.db.get_tweets_line()
        # PostgreSQL schema: id(0), tweet_id(1), tweet_text(2), media(3), sending_time(4), entities(5), query(6)
        tweets_sent_time = []
        for tweet in tweets_line:
            sending_time = tweet[4]  # sending_time is at index 4
            if sending_time is not None:
                # Handle both string and datetime objects
                if isinstance(sending_time, str):
                    tweets_sent_time.append(dt.datetime.strptime(sending_time, '%Y-%m-%d %H:%M:%S'))
                else:
                    tweets_sent_time.append(sending_time)
        time_now = dt.datetime.now()
        current_hour = int(time_now.strftime('%H'))
        current_minute = int(time_now.strftime('%M'))

        for hour in range(current_hour, 24):
            tweets_in_this_hour = [tweet for tweet in tweets_sent_time if tweet.hour == hour]
            if len(tweets_in_this_hour) < desired_num_tweets_per_hour:
                random_minute = random.randint(current_minute, 59)
                random_hour = random.randint(current_hour, current_hour + 2)
                if random_hour < 0:
                    random_hour = 0
                elif random_hour >= 24:
                    random_hour = 23
                desired_time = time_now.replace(hour=random_hour, minute=random_minute, second=0)
                break
        else:
            random_hour = random.randint(current_hour, 23)
            random_minute = random.randint(current_minute, 59)
            desired_time = time_now.replace(hour=random_hour, minute=random_minute, second=0)

        return desired_time

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

        # Set up the Twitter API callback for admin bot
        self.twitter_api.set_telegram_callback(self._handle_captured_tweet)

        # Set up handlers
        updater = Updater(self.TOKEN, use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("queue", self.queue_status))
        dp.add_handler(MessageHandler(Filters.text, self.text_handler_thread))
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

    def text_handler_thread(self, update, context=None):
        """Handle text messages in a separate thread."""
        text_handler_thread = threading.Thread(target=self.text_handler, args=(update, context,))
        text_handler_thread.start()

    def text_handler(self, update, context=None):
        """Handle incoming text messages."""
        try:
            admin_bool, user_name = self.check_admin(update)
            chat_id = update.message.chat_id
            self.db.set_state(str(chat_id), None)
        except:
            return

        if admin_bool:
            tweet_url = update.message.text.strip()

            # Check if it's a valid tweet URL
            if "twitter.com" in tweet_url or "x.com" in tweet_url:
                self.receive_tweet(update, user_name)
            else:
                update.message.reply_text('Please send a valid tweet URL (twitter.com or x.com)')

    def receive_tweet(self, update, user_name):
        """Process a received tweet URL."""
        tweet_url = update.message.text.strip()
        chat_id = str(update.message.chat_id)

        # Add to queue with high priority (admin)
        queue_id, result = self.twitter_api.add_to_queue(
            tweet_url=tweet_url,
            user_name=user_name,
            chat_id=chat_id,
            bot_type='admin'
        )

        if queue_id:
            update.message.reply_text(
                f"✅ Tweet added to queue!\n\n"
                f"📍 Position: {result}\n"
                f"⏳ You'll be notified when it's processed."
            )
        else:
            update.message.reply_text(f"❌ Could not add tweet: {result}")

    def time_counter(self):
        """Background thread for the Mahsa Amini time counter."""
        message_txt = "minutes have passed since when the brutal Islamic Regime took the life of our brave Mahsa, but our resolve remains unbroken. We will never forget, nor forgive the injustice that has been done 💔\n\nBut we do not mourn alone, for we stand united as a force to be reckoned with, a force that will fight with every breath and every beat of our hearts until justice is served ⚖️\n\nWe will not rest until we have reclaimed our rights and taken back what is rightfully ours. This is not just a cry for justice, but a call to arms - the sound of our REVOLUTION 🔥\n\n#MahsaAmini\n#WomanLifeFreedom\n\n@Tweets_SUT"
        mahsa_death_time = dt.datetime(2022, 9, 16, 19, 0)
        message_id = self.db.get_time_counter_message_id()

        if message_id is None:
            time_now = dt.datetime.now()
            diff_time = time_now - mahsa_death_time
            message_caption = form_time_counter_message(diff_time, message_txt)
            media_array = self.make_media_array(message_caption, [['https://revolution.aminalam.info/static/images/wlf_flag.png', 'photo']])
            message_id = self.bot.sendMediaGroup(chat_id=self.MAIN_CHANNEL_CHAT_ID, media=media_array)
            message_id = message_id[0]['message_id']
            self.db.set_time_counter_message_id(str(message_id))

        while True:
            try:
                time_now = dt.datetime.now()
                diff_time = time_now - mahsa_death_time
                message_caption = form_time_counter_message(diff_time, message_txt)
                self.bot.editMessageMedia(
                    chat_id=self.MAIN_CHANNEL_CHAT_ID,
                    message_id=message_id,
                    media=InputMediaPhoto('https://revolution.aminalam.info/static/images/wlf_flag.png', message_caption)
                )
            except Exception as e:
                print(f"Time counter error: {e}")
            time.sleep(61)

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

                                    if media_list:
                                        media_array = self.make_media_array(tweet_text, media_list, entities=entities_list_converted if entities_list_converted else None)
                                        self.bot.sendMediaGroup(chat_id=self.MAIN_CHANNEL_CHAT_ID, media=media_array, timeout=1000)
                                    else:
                                        self.bot.sendMessage(
                                            chat_id=self.MAIN_CHANNEL_CHAT_ID,
                                            text=tweet_text,
                                            disable_web_page_preview=True,
                                            timeout=1000,
                                            entities=entities_list_converted if entities_list_converted else None
                                        )

                                    self.db.remove_tweet_from_line(tweet_id)
                                    self.db.remove_old_tweets_in_line(num_tweets_to_preserve=self.num_tweets_to_preserve)
                                    deleted_snapshots(media_list)

                                    button_list = [InlineKeyboardButton("Sent ✅", callback_data=f"SENT|{desired_time_persian}|{tweet_id}")]
                                    reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
                                    success_message = "Sent successfully."

                                    try:
                                        if query and 'message' in query:
                                            self.bot.editMessageText(
                                                chat_id=query['message']['chat']['id'],
                                                message_id=query['message']['message_id'],
                                                text=success_message,
                                                reply_markup=reply_markup
                                            )
                                    except:
                                        pass

                                except Exception as e:
                                    self.db.error_log(e)

            except Exception as e:
                self.db.error_log(e)

            time.sleep(10)


class TelegramSuggestedTweetsBot(TelegramBot):
    """Bot for handling suggested tweets from users."""

    def __init__(self, creds, twitter_api, db, time_diff, reference_snapshot, user_tweet_limit):
        super().__init__(creds, db, twitter_api, time_diff, reference_snapshot)
        self.CHAT_ID = creds["SUGGESTIONS_CHAT_ID"]
        self.TOKEN = creds["SUGGESTIONS_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.bot = Bot(token=self.TOKEN)
        self.user_tweet_limit = user_tweet_limit

        # Set up handlers
        updater = Updater(self.TOKEN, use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(MessageHandler(Filters.text, self.text_handler_thread))
        dp.add_handler(CallbackQueryHandler(self.callback_query_handler))
        updater.start_polling()

    def text_handler_thread(self, update, context=None):
        """Handle text messages in a separate thread."""
        text_handler_thread = threading.Thread(target=self.receive_tweet, args=(update, context,))
        text_handler_thread.start()

    def receive_tweet(self, update, context=None):
        """Process a suggested tweet from a user."""
        _, user_name = self.check_admin(update)
        chat_id = str(update.message.chat_id)
        tweet_url = update.message.text.strip()

        # Check rate limit (if enabled)
        if self.user_tweet_limit > 0:
            user_count = self.db.get_user_tweet_count_last_hour(user_name)
            if user_count >= self.user_tweet_limit:
                update.message.reply_text(
                    f'⚠️ You have exceeded your hourly limit ({self.user_tweet_limit} tweets per hour).\n'
                    f'Please try again later.'
                )
                return

        # Check if it's a valid tweet URL
        if "twitter.com" not in tweet_url and "x.com" not in tweet_url:
            update.message.reply_text('Please send a valid tweet URL (twitter.com or x.com)')
            return

        # Add to queue with low priority (suggestions)
        queue_id, result = self.twitter_api.add_to_queue(
            tweet_url=tweet_url,
            user_name=user_name,
            chat_id=chat_id,
            bot_type='suggestions'
        )

        if queue_id:
            # Notify suggestions channel about the new suggestion
            try:
                self.bot.sendMessage(
                    chat_id=self.CHAT_ID,
                    text=f"📥 New suggestion from @{user_name}",
                    timeout=1000
                )
            except:
                pass

            update.message.reply_text(
                f"✅ Your tweet suggestion has been added to the queue!\n\n"
                f"📍 Position: {result}\n"
                f"⏳ You'll be notified when it's processed."
            )
        else:
            update.message.reply_text(f"❌ Could not add tweet: {result}")
