from configs import * 

class TelegramBot():
    def __init__(self, creds, db_log, twitter_api) -> None:
        self.creds = creds
        self.db_log = db_log
        self.twitter_api = twitter_api

    def start(self, update, context=None):
        update.message.reply_text('Hello {}'.format(update.message.from_user.first_name))

    def on_data(self,tweet):
            try:
                tweet_id = tweet['tweet_id']
                tg_text = tweet['text']
                tw_screen_name = tweet['displayname']
                tweet_url = tweet['url']
                tw_name = tweet['name']
                tweet_date_persian = tweet['tweet_date_persian']
                media_array = []
                tg_text = f"{tg_text} \n\n🌐 <a href='{tweet_url}'>{tw_screen_name}</a>"
                tg_text = f"{tg_text} \n📅 {tweet_date_persian}"
                tg_text = f"{tg_text} \n\n {self.CHANNEL_NAME}"
                if not self.db_log.check_tweet_existence(tweet_id):
                    if len(tweet['media']) > 0:
                        for indx, media in enumerate(tweet['media']):
                            if indx==0:
                                caption = tg_text
                            else:
                                caption = ""
                            if media[1] == "photo":
                                media_tmp = InputMediaPhoto(media[0], caption=caption, parse_mode="HTML")
                            elif media[1] == "video":
                                media_tmp = InputMediaVideo(media[0], caption=caption, parse_mode="HTML")
                            media_array.append(media_tmp)
                        self.bot.sendMediaGroup(chat_id=self.CHAT_ID,media=media_array,timeout=1000)
                    else:
                        self.bot.sendMessage(chat_id=self.CHAT_ID, text=tg_text, parse_mode="HTML",disable_web_page_preview=True,timeout=1000)
                    log_args = {'tweet_id': tweet_id, 'tweet_text': tg_text, 'user_name': '', 'status': 'Success'}
                    return True, 'Success', log_args
                else:
                    log_args = {'tweet_id': tweet_id, 'tweet_text': '', 'user_name': '', 'status': 'Already Posted'}
                    return False, 'Already Posted', log_args
            except Exception as e:
                self.db_log.error_log(e)
                log_args = {'tweet_id': tweet_id, 'tweet_text': tg_text, 'user_name': '', 'status': 'Failed'}
                return False, 'Error: {}'.format(e), log_args

    def check_admin(self, update):
        try:
            user_name = update.message.chat['username']
        except:
            user_name = update.message['from']['username']
        if user_name in self.creds["ADMIN_ID"]:
            return True, user_name
        else:
            return False, user_name


class TelegramAdminBot(TelegramBot):
    def __init__(self, creds, twitter_api, db_log) -> None:
        super(TelegramAdminBot, self).__init__(creds, db_log, twitter_api)
        self.CHAT_ID = creds["ADMIN_CHAT_ID"]
        self.TOKEN = creds["ADMIN_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.bot = Bot(token=self.TOKEN)


    def receive_tweet(self, update, context=None):
        admin_bool, user_name = self.check_admin(update)
        if admin_bool:
            tweet_url = update.message.text
            if "twitter.com" in tweet_url:
                tweet = self.twitter_api.get_tweet(tweet_url)
                status = self.on_data(tweet)
                update.message.reply_text(status[1])
            else:
                update.message.reply_text('Please send a valid tweet url')
        log_args = status[-1]
        log_args['user_name'] = user_name
        log_args['admin'] = admin_bool
        self.db_log.tweet_log(log_args)


class TelegramSuggestedTweetsBot(TelegramBot):
    def __init__(self, creds, twitter_api, db_log) -> None:
        super(TelegramSuggestedTweetsBot, self).__init__(creds, db_log, twitter_api)
        self.CHAT_ID = creds["SUGGESTIONS_CHAT_ID"]
        self.TOKEN = creds["SUGGESTIONS_TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.bot = Bot(token=self.TOKEN)


    def receive_tweet(self, update, context=None):
        _, user_name = self.check_admin(update)
        tweet_url = update.message.text
        if "twitter.com" in tweet_url:
            tweet = self.twitter_api.get_tweet(tweet_url)
            self.bot.sendMessage(chat_id=self.CHAT_ID, text=f'@{user_name}',timeout=1000)
            status = self.on_data(tweet)
            update.message.reply_text(status[1])
        else:
            update.message.reply_text('Please send a valid tweet url')
        log_args = status[-1]
        log_args['user_name'] = user_name
        log_args['admin'] = False
        self.db_log.tweet_log(log_args)

