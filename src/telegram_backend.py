from configs import * 

class TelegramBot():
    def __init__(self, creds, db_log, twitter_api) -> None:
        self.creds = creds
        self.db_log = db_log
        self.twitter_api = twitter_api

    def start(self, update, context=None):
        update.message.reply_text('Hello {}'.format(update.message.from_user.first_name))

    def make_media_array(self, tg_text, media_list, entities=None):
        media_array = []
        for indx, media in enumerate(media_list):
            if indx==0:
                caption = tg_text
                caption_entities = entities
            else:
                caption = ""
                caption_entities = None
            if media[1] == "photo":
                if entities:
                    media_tmp = InputMediaPhoto(media[0], caption=caption, caption_entities=caption_entities)
                else:
                    media_tmp = InputMediaPhoto(media[0], caption=caption, parse_mode="HTML")
            elif media[1] == "video":
                if entities:
                    media_tmp = InputMediaVideo(media[0], caption=caption, caption_entities=caption_entities)
                else:
                    media_tmp = InputMediaVideo(media[0], caption=caption, parse_mode="HTML")
            media_array.append(media_tmp)
        return media_array

    def on_data(self,tweet):
            try:
                tweet_id = tweet['tweet_id']
                tg_text = tweet['text']
                tw_screen_name = tweet['displayname']
                tweet_url = tweet['url']
                tw_name = tweet['name']
                tweet_date_persian = tweet['tweet_date_persian']
                
                tg_text = f"{tg_text} \n\n🌐 <a href='{tweet_url}'>{tw_screen_name}</a>"
                tg_text = f"{tg_text} \n📅 {tweet_date_persian}"
                tg_text = f"{tg_text} \n\n {self.CHANNEL_NAME}"
                tweet_line_args ={'tweet_id': tweet_id, 'tweet_text': tg_text, 'media_list': ''}
                
                if not self.db_log.check_tweet_existence(tweet_id):
                    if len(tweet['media']) > 0:
                        media_array = self.make_media_array(tg_text, tweet['media'])
                        sent_message = self.bot.sendMediaGroup(chat_id=self.CHAT_ID,media=media_array,timeout=1000)[0]
                        tweet_line_args['media_list'] = tweet['media']
                    else:
                        sent_message = self.bot.sendMessage(chat_id=self.CHAT_ID, text=tg_text, parse_mode="HTML",disable_web_page_preview=True,timeout=1000)
                    
                    reply_markup = self.make_time_options(tweet_id)
                    self.bot.sendMessage(chat_id=self.CHAT_ID, text="Please select a time for this tweet to be posted.", reply_markup=reply_markup, timeout=1000, reply_to_message_id=sent_message.message_id)

                    self.db_log.add_tweet_to_line(tweet_line_args)

                    log_args = {'tweet_id': tweet_id, 'tweet_text': tg_text, 'user_name': '', 'status': 'Success'}
                    return True, 'Success', log_args
                else:
                    log_args = {'tweet_id': tweet_id, 'tweet_text': '', 'user_name': '', 'status': 'Already Posted'}
                    return False, 'Already Posted', log_args

            except Exception as e:
                self.db_log.error_log(e)
                log_args = {'tweet_id': tweet_id, 'tweet_text': tg_text, 'user_name': '', 'status': 'Failed'}
                return False, 'Error: {}'.format(e), log_args

    def callback_query_handler(self, update, context=None):
        query = update.callback_query
        query_text = query.data.split('_')
        query_type = query_text[0]

        tg_text = query.message.reply_to_message.text
        entities = query.to_dict()['message']['reply_to_message']['entities']
        
        if tg_text == None:
            tg_text = query.message.reply_to_message.caption
            entities = query.to_dict()['message']['reply_to_message']['caption_entities']
        if query_type == 'TIME':
            tweet_id = query_text[2]
            desired_time = query_text[1]
            self.db_log.set_sending_time_for_tweet_in_line(tweet_id, sending_time=desired_time, tweet_text=tg_text, entities=entities)

            button_list = [InlineKeyboardButton("Scheduled ✅", callback_data="None"),]
            reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
            query.edit_message_text(text=query.message.text, reply_markup=reply_markup)

    def make_time_options(self, tweet_id):
        time_now = dt.datetime.now()
        time_now = time_now.replace(second=0, microsecond=0)
        button_list = []
        for i in range(0, 9*30, 30):
            time_option = time_now + dt.timedelta(minutes=i)
            inline_key = InlineKeyboardButton(f"{i} min later", callback_data=f"TIME_{time_option}_{tweet_id}")
            button_list.append(inline_key)
        reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=3))
        return reply_markup

    def get_user_name(self, update):
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
                    pass

        return user_name

    def check_admin(self, update):
        user_name = self.get_user_name(update)
        if user_name in self.creds["ADMIN_ID"]:
            return True, user_name
        else:
            return False, user_name

    def build_menu(self, buttons, n_cols, header_buttons=None, footer_buttons=None):
        menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]

        if header_buttons:
            menu.insert(0, [header_buttons])
        if footer_buttons:
            menu.append([footer_buttons])

        return menu

    def check_for_tweet_in_line(self):
        # check for tweets in line every 30 seconds
        while True:
            tweets_line = self.db_log.get_tweets_line()
            if tweets_line:
                for tweet in tweets_line:
                    tweet_sent_time = tweet[3]
                    if tweet_sent_time:
                        tweet_sent_time = dt.datetime.strptime(tweet_sent_time, '%Y-%m-%d %H:%M:%S')
                        if tweet_sent_time <= dt.datetime.now():
                            entities = tweet[4]
                            entities = json.loads(entities)
                            entities_list_converted = []

                            for entity in entities:
                                converted_format = None
                                if 'url' in entity:
                                    converted_format = MessageEntity(type=entity['type'], offset=entity['offset'], length=entity['length'], url=entity['url'])
                                else:
                                    converted_format = MessageEntity(type=entity['type'], offset=entity['offset'], length=entity['length']) 

                                entities_list_converted.append(converted_format)
                                
                            entities = entities_list_converted
                            tweet_id = tweet[0]
                            tg_text = tweet[1]
                            media_list = tweet[2]
                            media_list = json.loads(media_list)
                            if media_list != '':    
                                media_array = self.make_media_array(tg_text, media_list, entities=entities)
                                self.bot.sendMediaGroup(chat_id=self.CHAT_ID,media=media_array,timeout=1000)
                            else:
                                self.bot.sendMessage(chat_id=self.MAIN_CHANNEL_CHAT_ID, text=tg_text,disable_web_page_preview=True,timeout=1000, entities=entities)
                            self.db_log.remove_tweet_from_line(tweet_id)
            time.sleep(1*60)

class TelegramAdminBot(TelegramBot):
    def __init__(self, creds, twitter_api, db_log) -> None:
        super(TelegramAdminBot, self).__init__(creds, db_log, twitter_api)
        self.CHAT_ID = creds["ADMIN_CHAT_ID"]
        self.TOKEN = creds["ADMIN_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.MAIN_CHANNEL_CHAT_ID = creds["MAIN_CHANNEL_CHAT_ID"]
        self.bot = Bot(token=self.TOKEN)

        updater = Updater(self.TOKEN , use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(MessageHandler(Filters.text, self.receive_tweet))
        dp.add_handler(CallbackQueryHandler(self.callback_query_handler))
        updater.start_polling()

        self.check_for_tweet_in_line_thread = threading.Thread(target=self.check_for_tweet_in_line)
        self.check_for_tweet_in_line_thread.start()

    def receive_tweet(self, update, context=None):
        admin_bool, user_name = self.check_admin(update)
        if admin_bool:
            tweet_url = update.message.text
            if "twitter.com" in tweet_url:
                tweet = self.twitter_api.get_tweet(tweet_url)
                status = self.on_data(tweet)
                update.message.reply_text(status[1])
                log_args = status[-1]
                log_args['user_name'] = user_name
                log_args['admin'] = admin_bool
                self.db_log.tweet_log(log_args)
            else:
                update.message.reply_text('Please send a valid tweet url')



class TelegramSuggestedTweetsBot(TelegramBot):
    def __init__(self, creds, twitter_api, db_log) -> None:
        super(TelegramSuggestedTweetsBot, self).__init__(creds, db_log, twitter_api)
        self.CHAT_ID = creds["SUGGESTIONS_CHAT_ID"]
        self.TOKEN = creds["SUGGESTIONS_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.bot = Bot(token=self.TOKEN)

        updater = Updater(self.TOKEN , use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(MessageHandler(Filters.text, self.receive_tweet))
        dp.add_handler(CallbackQueryHandler(self.callback_query_handler))
        updater.start_polling()

    def receive_tweet(self, update, context=None):
        _, user_name = self.check_admin(update)
        tweet_url = update.message.text
        if "twitter.com" in tweet_url:
            tweet = self.twitter_api.get_tweet(tweet_url)
            self.bot.sendMessage(chat_id=self.CHAT_ID, text=f'@{user_name}',timeout=1000)
            status = self.on_data(tweet)
            update.message.reply_text(status[1])
            log_args = status[-1]
            log_args['user_name'] = user_name
            log_args['admin'] = False
            self.db_log.tweet_log(log_args)
        else:
            update.message.reply_text('Please send a valid tweet url')
            
        

