from configs import * 

class TelegramBot():
    def __init__(self, creds, db_log, twitter_api, time_diff, gpt_suggestions_rate) -> None:
        self.creds = creds
        self.db_log = db_log
        self.twitter_api = twitter_api
        self.time_diff = time_diff
        self.gpt_suggestions_rate = gpt_suggestions_rate
        if self.gpt_suggestions_rate > 0:
            import gpt_model
            self.gpt_model = gpt_model.fa_GPT()

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

    def on_data(self,tweet):
            try:
                tweet_id = tweet['tweet_id']
                tg_text = tweet['text']
                tw_screen_name = tweet['displayname']
                tweet_url = tweet['url']
                tw_name = tweet['name']
                tweet_date_persian = tweet['tweet_date_persian']

                if 'telegraph_url' in tweet:
                    tg_text = f"📝 This is a thread (<a href='{tweet['telegraph_url']}'>read in Telegra.ph</a>):\n\n{tg_text}"
                    tg_text = f'{tg_text} ...'

                if random.random() < self.gpt_suggestions_rate and len(tg_text) < 100:
                    gpt_suggestion = self.gpt_model.generate(tg_text)
                    tg_text = f"👤 Real tweet: {tg_text}\n\n🤖 GPT Story: {gpt_suggestion}"

                tg_text = f"{tg_text} \n\n🌐 <a href='{tweet_url}'>{tw_screen_name}</a>"
                tg_text = f"{tg_text} \n📅 {tweet_date_persian}"
                tg_text = f"{tg_text} \n\n {self.CHANNEL_NAME}"
                tweet_line_args ={'tweet_id': tweet_id, 'tweet_text': tg_text, 'media_list': ''}

                # if tweet is a qoute retweet and has no media, take snapshot of the quoted tweet and save it as media
                if tweet['quoted_tweet_id'] != None or tweet['parent_tweet_id'] != None:
                    if tweet['quoted_tweet_id'] != None:
                        reference_tweet_id = tweet['quoted_tweet_id']
                    elif tweet['parent_tweet_id'] != '':
                        reference_tweet_id = tweet['parent_tweet_id']
                    reference_tweet_url = f'https://twitter.com/{tw_name}/status/{reference_tweet_id}'
                    reference_tweet_snapshot_as_media = self.twitter_api.get_reference_tweet_snapshot_as_media(reference_tweet_url, reference_tweet_id)
                    tweet['media'].append(reference_tweet_snapshot_as_media)

                    if len(tweet['media']) == 1:
                        tg_text = f"🔗 Photo is a snapshot of <a href='{reference_tweet_url}'>this tweet</a> \n\n{tg_text}"
                    elif len(tweet['media']) > 1:
                        tg_text = f"🔗 One of the media is a snapshot of <a href='{reference_tweet_url}'>this tweet</a> \n\n{tg_text}"

                if not self.db_log.check_tweet_existence(tweet_id):
                    if len(tweet['media']) > 0:
                        media_array = self.make_media_array(tg_text, tweet['media'])
                        sent_message = self.bot.sendMediaGroup(chat_id=self.CHAT_ID,media=media_array,timeout=1000)[0]
                        tweet_line_args['media_list'] = tweet['media']
                    else:
                        sent_message = self.bot.sendMessage(chat_id=self.CHAT_ID, text=tg_text, parse_mode="HTML",disable_web_page_preview=True,timeout=1000)
                    
                    reply_markup, markup_text = self.make_time_options(tweet_id)
                    self.bot.sendMessage(chat_id=self.CHAT_ID, text=markup_text, reply_markup=reply_markup, timeout=1000, reply_to_message_id=sent_message.message_id)

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
        user_name = self.get_user_name(update)
        query = update.callback_query
        query_text = query.data.split('|')
        query_type = query_text[0]
        query_dict = query.to_dict()
        chat_id = query_dict['message']['chat']['id']

        try:
            tg_text = query.message.reply_to_message.text
            entities = query.to_dict()['message']['reply_to_message']['entities']

            if tg_text == None:
                tg_text = query.message.reply_to_message.caption
                entities = query.to_dict()['message']['reply_to_message']['caption_entities']
        except:
            pass

        if query_type == 'TIME':
            tweet_id = query_text[2]
            time_now = dt.datetime.now()
            time_now = time_now.replace(second=0, microsecond=0)
            if query_text[1] == 'AUTO':
                desired_time = utils.get_next_sending_time(tweets_line = self.db_log.get_tweets_line())
            else:
                desired_time = time_now + dt.timedelta(minutes=int(query_text[1]))
            desired_time = desired_time.strftime("%Y-%m-%d %H:%M:%S")
            desired_time_persian = utils.covert_tweet_time_to_desired_time(desired_time, self.time_diff)
            self.db_log.set_sending_time_for_tweet_in_line(tweet_id, sending_time=desired_time, tweet_text=tg_text, entities=entities, query=query_dict)

            button_list = [InlineKeyboardButton("Cancel ❌", callback_data=f"CANCEL|{tweet_id}")]
            reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
            success_message = f"Tweet has been scheduled for {desired_time_persian} (Iran time-zone).\n You can edit the text or caption of the message till the sending time.\n Also, you can cancel it via Cancel button."
            query.edit_message_text(text=success_message, reply_markup=reply_markup)

        if query_type == 'CANCEL':
            tweet_id = query_text[1]
            reply_markup, markup_text = self.make_time_options(tweet_id)
            self.db_log.set_sending_time_for_tweet_in_line(tweet_id, sending_time=None, tweet_text=tg_text, entities=None, query=None)
            query.edit_message_text(text=markup_text, reply_markup=reply_markup)

        if query_type == 'SENT':
            tweet_id = query_text[2]
            sent_time = query_text[1]
            tweet = self.db_log.get_tweet_by_tweet_id(tweet_id)
            admin_user_name = tweet[2]
            query.answer(text=f"Sent by {admin_user_name} at {sent_time} Iran time-zone")

        if query_type == 'GetFullThreadMessage':
            tweet_id = query_text[2]
            tweet_user_name = query_text[1]
            tweet_url = f"https://twitter.com/{tweet_user_name}/status/{tweet_id}"
            self.send_thread_tweet(tweet_url, chat_id=chat_id, user_name=user_name) 

            args = {'chat_id': chat_id, 'state': None}
            utils.set_state(self.db_log.conn, args)

            button_list = [InlineKeyboardButton("Full thread selected (Message)", callback_data="None")]
            reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
            query.edit_message_text(text=query.message.text, reply_markup=reply_markup)

        if query_type == 'GetFullThreadTelegraph':
            tweet_id = query_text[2]
            tweet_user_name = query_text[1]
            tweet_url = f"https://twitter.com/{tweet_user_name}/status/{tweet_id}"
            self.send_thread_tweet_telegraph(tweet_url, chat_id=chat_id, user_name=user_name) 

            args = {'chat_id': chat_id, 'state': None}
            utils.set_state(self.db_log.conn, args)
            
            button_list = [InlineKeyboardButton("Full thread selected (Telegraph)", callback_data="None")]
            reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
            query.edit_message_text(text=query.message.text, reply_markup=reply_markup)

        if query_type == 'GetThisTweet':
            tweet_id = query_text[2]
            tweet_user_name = query_text[1]
            tweet_url = f"https://twitter.com/{tweet_user_name}/status/{tweet_id}"
            tweet = self.twitter_api.get_tweet(tweet_url)
            self.send_tweet(update, tweet, chat_id=query.message.chat_id)

            args = {'chat_id': chat_id, 'state': None}
            utils.set_state(self.db_log.conn, args)

            button_list = [InlineKeyboardButton("Single Tweet selected", callback_data="None")]
            reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
            query.edit_message_text(text=query.message.text, reply_markup=reply_markup)

    def make_time_options(self, tweet_id):
        button_list = []
        for time_option in range(0, 16*30, 30):
            inline_key = InlineKeyboardButton(f"{time_option} min later", callback_data=f"TIME|{time_option}|{tweet_id}")
            button_list.append(inline_key)
        # automatic option will sent twe tweet based on the number of tweets in the line
        inline_key = InlineKeyboardButton(f"Auto timing", callback_data=f"TIME|AUTO|{tweet_id}")
        button_list.append(inline_key)
        reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=3))
        markup_text = "Please select a time for sending this tweet."
        return reply_markup, markup_text

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
                    
                    try:
                        user_name = update.callback_query.from_user.username
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

class TelegramAdminBot(TelegramBot):
    def __init__(self, creds, twitter_api, db_log, suggestions_bot, time_diff, mahsa_message, gpt_suggestions_rate, num_tweets_to_preserve) -> None:
        super(TelegramAdminBot, self).__init__(creds, db_log, twitter_api, time_diff, gpt_suggestions_rate)
        self.CHAT_ID = creds["ADMIN_CHAT_ID"]
        self.TOKEN = creds["ADMIN_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.MAIN_CHANNEL_CHAT_ID = creds["MAIN_CHANNEL_CHAT_ID"]
        self.bot = Bot(token=self.TOKEN)
        self.suggestions_bot = suggestions_bot
        self.mahsa_message = mahsa_message
        self.num_tweets_to_preserve = num_tweets_to_preserve
        self.telegraph = utils.telegraph(account_name=self.CHANNEL_NAME.split('@')[1])
        updater = Updater(self.TOKEN , use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(MessageHandler(Filters.text, self.text_handler))
        dp.add_handler(CallbackQueryHandler(self.callback_query_handler))
        updater.start_polling()

        self.check_for_tweet_in_line_thread = threading.Thread(target=self.check_for_tweet_in_line)
        self.check_for_tweet_in_line_thread.start()

        self.time_counter_thread = threading.Thread(target=self.time_counter)
        self.time_counter_thread.start()

    def text_handler(self, update, context=None):
        try:
            admin_bool, _ = self.check_admin(update)
            chat_id = update.message.chat_id
            args = {'chat_id': chat_id, 'state': None}
            utils.set_state(self.db_log.conn, args)
        except:
            pass

        if admin_bool:
            tweet_url = update.message.text

            if "twitter.com" in tweet_url:
                self.receive_tweet(update)
            else:
                update.message.reply_text('Please send a valid tweet url')

    def receive_tweet(self, update):
        tweet_url = update.message.text
        tweet = self.twitter_api.get_tweet(tweet_url)
        chat_id = update.message.chat_id

        tweet_id = tweet['tweet_id']
        if self.db_log.check_tweet_existence(tweet_id):
            update.message.reply_text('This tweet has already been sent to the bot')
            return

        if tweet['parent_tweet_id']:
            button_list = [InlineKeyboardButton("Get thread (Message)", callback_data=f"GetFullThreadMessage|{tweet['name']}|{tweet['tweet_id']}"),
                           InlineKeyboardButton("Get thread (Telegra.ph)", callback_data=f"GetFullThreadTelegraph|{tweet['name']}|{tweet['tweet_id']}"),
                           InlineKeyboardButton("Get only this tweet", callback_data=f"GetThisTweet|{tweet['name']}|{tweet['tweet_id']}")] 
            reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=2))
            success_message = f"It seems that this tweet is a reply to another tweet. Do you want to get the full thread or just this tweet?"
            update.message.reply_text(text=success_message, reply_markup=reply_markup)
            args = {'chat_id': chat_id, 'state': 'GET_FULL_THREAD_OR_THIS_TWEET'}
            utils.set_state(self.db_log.conn, args)
        else:
            self.send_tweet(update, tweet)

    def send_tweet(self, update=None, tweet=None, chat_id=None, user_name=None):
        if user_name is None:
            admin_bool, user_name = self.check_admin(update)
        else:
            admin_bool, _ = self.check_admin(update)

        # tell to wait for the tweet to be processed
        if chat_id:
            self.bot.send_message(chat_id=chat_id, text='Please wait for the tweet to be processed...')
        else:
            update.message.reply_text('Please wait for the tweet to be processed...')

        status = self.on_data(tweet)
        if chat_id:
            self.bot.send_message(chat_id=chat_id, text=status[1])
        else:
            update.message.reply_text(status[1])

        log_args = status[-1]
        log_args['user_name'] = user_name
        log_args['admin'] = admin_bool
        self.db_log.tweet_log(log_args)

    def send_thread_tweet(self, tweet_url, chat_id, user_name):
        thread_text, _ = self.make_thread_text(tweet_url)
        tweet_url = self.get_thread_first_tweet_id(tweet_url)
        tweet = self.twitter_api.get_tweet(tweet_url)
        tweet['text'] = thread_text
        self.send_tweet(self, tweet=tweet, chat_id=chat_id, user_name=user_name)

    def send_thread_tweet_telegraph(self, tweet_url, chat_id, user_name):
        html_content, _ = self.make_thread_text_telegraph(tweet_url)
        tweet_url = self.get_thread_first_tweet_id(tweet_url)
        print(tweet_url)
        tweet = self.twitter_api.get_tweet(tweet_url)
        page_title = f'Thread by {tweet["name"]}'
        page_url = self.telegraph.create_page(title=page_title, html_content=html_content)
        tweet['text'] = tweet['text']
        tweet['telegraph_url'] = page_url
        self.send_tweet(self, tweet=tweet, chat_id=chat_id, user_name=user_name)

    def make_thread_text(self, tweet_url):
        tweet = self.twitter_api.get_tweet(tweet_url)
        thread_text = tweet['text']

        if tweet['parent_tweet_id']:
            tweet_url = f"https://twitter.com/{tweet['name']}/status/{tweet['parent_tweet_id']}"
            return f"{self.make_thread_text(tweet_url)[0]} \n\n {thread_text}", tweet_url
        else:
            return thread_text, tweet_url

    def make_thread_text_telegraph(self, tweet_url):
        tweet = self.twitter_api.get_tweet(tweet_url)
        thread_text = tweet['text']
        tweet_media = tweet['media']

        if tweet['parent_tweet_id']:
            tweet_url = f"https://twitter.com/{tweet['name']}/status/{tweet['parent_tweet_id']}"
            html_content = f"<p>{self.make_thread_text_telegraph(tweet_url)[0]}</p>" + f"<p>{thread_text}</p>"
            if tweet_media:
                for media in tweet_media:
                    if media[1] == 'photo':
                        html_content += f"\n\n<img src='{media[0]}'/>"
                    elif media[1] == 'video':
                        html_content += f"\n\n<video src='{media[0]}'/>"
        else:
            html_content = thread_text + f" <p> <a href='{tweet_url}'>(Link to tweet)</a> </p>"
            if tweet_media:
                for media in tweet_media:
                    if media[1] == 'photo':
                        html_content += f"\n\n<img src='{media[0]}'/>"
                    elif media[1] == 'video' or media[1] == 'animated_gif':
                        html_content += f"\n\n<video src='{media[0]}'/>"
        return html_content, tweet_url
    
    def get_thread_first_tweet_id(self, tweet_url):
        tweet = self.twitter_api.get_tweet(tweet_url)
        while tweet['parent_tweet_id']:
            tweet_url = f"https://twitter.com/{tweet['name']}/status/{tweet['parent_tweet_id']}"
            tweet = self.twitter_api.get_tweet(tweet_url)        
        return tweet_url
        
    def time_counter(self):
        message_txt = "minutes have passed since when the brutal Islamic Regime took the life of our brave Mahsa, but our resolve remains unbroken. We will never forget, nor forgive the injustice that has been done 💔\n\nBut we do not mourn alone, for we stand united as a force to be reckoned with, a force that will fight with every breath and every beat of our hearts until justice is served ⚖️\n\nWe will not rest until we have reclaimed our rights and taken back what is rightfully ours. This is not just a cry for justice, but a call to arms - the sound of our REVOLUTION 🔥\n\n#MahsaAmini\n#WomanLifeFreedom\n\n@Tweets_SUT"
        mahsa_death_time = dt.datetime(2022, 9, 16, 19, 0)
        message_id = utils.get_time_counter_message_id(self.db_log.conn)
        if message_id is None:
            time_now = dt.datetime.now()
            diff_time = time_now - mahsa_death_time
            message_caption = utils.form_time_counter_message(diff_time, message_txt)
            media_array = self.make_media_array(message_caption, [['https://revolution.aminalam.info/static/images/wlf_flag.png', 'photo']])
            message_id = self.bot.sendMediaGroup(chat_id=self.MAIN_CHANNEL_CHAT_ID, media=media_array)
            message_id = message_id[0]['message_id']
            utils.set_time_counter_message_id(self.db_log.conn, message_id)

        while True:
            try:
                time_now = dt.datetime.now()
                diff_time =  time_now - mahsa_death_time
                message_caption = utils.form_time_counter_message(diff_time, message_txt)
                media_array = self.make_media_array(diff_time, [['https://revolution.aminalam.info/static/images/wlf_flag.png', 'photo']])
                self.bot.editMessageMedia(chat_id=self.MAIN_CHANNEL_CHAT_ID, message_id=message_id, media=InputMediaPhoto('https://revolution.aminalam.info/static/images/wlf_flag.png', message_caption))
            except Exception as e:
                print(e)
                pass
            time.sleep(61)

    def check_for_tweet_in_line(self):
        # check for tweets in line every 10 seconds
        while True:
            tweets_line = self.db_log.get_tweets_line()
            if tweets_line:

                for tweet in tweets_line:
                    tweet_sent_time = tweet[3]

                    if tweet_sent_time:
                        desired_time_persian = utils.covert_tweet_time_to_desired_time(tweet_sent_time, self.time_diff)
                        tweet_sent_time = dt.datetime.strptime(tweet_sent_time, '%Y-%m-%d %H:%M:%S')

                        if tweet_sent_time <= dt.datetime.now():
                            try:
                                query = tweet[5]
                                query = json.loads(query)
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
                                    self.bot.sendMediaGroup(chat_id=self.MAIN_CHANNEL_CHAT_ID,media=media_array,timeout=1000)
                                else:
                                    self.bot.sendMessage(chat_id=self.MAIN_CHANNEL_CHAT_ID, text=tg_text,disable_web_page_preview=True,timeout=1000, entities=entities)

                                self.db_log.remove_tweet_from_line(tweet_id)
                                self.db_log.remove_old_tweets_in_line(num_tweets_to_preserve=self.num_tweets_to_preserve)
                                utils.deleted_snapshots(media_list)
                                button_list = [InlineKeyboardButton("Sent ✅", callback_data=f"SENT|{desired_time_persian}|{tweet_id}")]
                                reply_markup = InlineKeyboardMarkup(self.build_menu(button_list, n_cols=1))
                                success_message = f"Sent successfully."
                                try:
                                    self.bot.editMessageText(chat_id=query['message']['chat']['id'], message_id=query['message']['message_id'], text=success_message, reply_markup=reply_markup)
                                except:
                                    self.suggestions_bot.bot.editMessageText(chat_id=query['message']['chat']['id'], message_id=query['message']['message_id'], text=success_message, reply_markup=reply_markup)
                            except Exception as e:
                                self.db_log.error_log(e)
                            
            time.sleep(1*10)

class TelegramSuggestedTweetsBot(TelegramBot):
    def __init__(self, creds, twitter_api, db_log, time_diff, gpt_suggestions_rate) -> None:
        super(TelegramSuggestedTweetsBot, self).__init__(creds, db_log, twitter_api, time_diff, gpt_suggestions_rate)
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
            tweet_id = tweet['tweet_id']
            if self.db_log.check_tweet_existence(tweet_id):
                update.message.reply_text('This tweet has already been sent to the bot')
                return
            self.bot.sendMessage(chat_id=self.CHAT_ID, text=f'@{user_name}',timeout=1000)
            update.message.reply_text('Please wait for the tweet to be processed...')
            status = self.on_data(tweet)
            update.message.reply_text(status[1])
            log_args = status[-1]
            log_args['user_name'] = user_name
            log_args['admin'] = False
            self.db_log.tweet_log(log_args)
        else:
            update.message.reply_text('Please send a valid tweet url')