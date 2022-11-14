import tweepy
import json 
import re
import sys
import os
from telegram import Bot, InputMediaPhoto, InputMediaVideo, MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from pathlib import Path
import sqlite3
import datetime as dt

creds_file = "/home/amin/Documents/Twitter_Parser/src/creds.json"
db_conf_file = "/home/amin/Documents/Twitter_Parser/src/db_conf.json"
def read_credentials():
    with open(creds_file) as f:
        creds = json.load(f)
    return creds

# Authenticate to Twitter
creds = read_credentials()


class Database():
    def __init__(self) -> None:
        self.db_config = self.read_db_config()
        self.conn = self.create_connection()
        self.init_db()

    def create_connection(self):
        conn = None
        db_file = self.db_config['DB_NAME']
        try:
            conn = sqlite3.connect(db_file, check_same_thread=False)
            print('Connected to database using SQLite', sqlite3.version)
        except sqlite3.Error as e:
            print(e)
        return conn

    def init_db(self):
        print('Initilizing the databse ...')
        try:
            for table in self.db_config['TABLES_LIST']:
                self.create_table(table)
            print('- Initilized !')
        except sqlite3.Error as e:
            print(e)

    def create_table(self, create_table_sql):
        try:
            c = self.conn.cursor()
            c.execute(create_table_sql)
        except sqlite3.Error as e:
            print(e)

    def read_db_config(self):
        with open(db_conf_file) as f:
            db_config = json.load(f)
        return db_config
    
    def error_log(self, error):
        error_tet = str(error)
        cursor = self.conn.cursor()
        time_now = dt.datetime.now()
        rows = [(error_tet, time_now, None)]
        cursor.executemany('insert into Errors values (?, ?, ?)', rows)
        self.conn.commit()
        print(error)

    def tweet_log(self, args):
        try:
            tweet_id = args['tweet_id']
            tweet_text = args['tweet_text']
            user_name = args['user_name']
            status = args['status']
            time_now = dt.datetime.now()

            cursor = self.conn.cursor()
            time_now = dt.datetime.now()
            rows = [(tweet_id, tweet_text, user_name, time_now, status, None)]
            cursor.executemany('insert into Tweets values (?, ?, ?, ?, ?, ?)', rows)
            self.conn.commit()
        except Exception as e:
            self.error_log(e)



class TwitterClient(object):

    def __init__(self, creds, db_log):
        self.db_log = db_log
        self.creds = creds
        consumer_key = creds["API_KEY"]
        consumer_secret = creds["API_KEY_SECRET"]
        access_token = creds["ACCESS_TOKEN"]
        access_token_secret = creds["ACCESS_TOKEN_SECRET"]
        bearer_token = creds["BEARER_TOKEN"]

        try:
            self.Client = tweepy.Client(bearer_token, consumer_key, consumer_secret, access_token, access_token_secret)
        except Exception as e:
            self.db_log.error_log(e)
  
    def get_tweet(self, tweet_url):
        if '?' in tweet_url:
            tweet_url = tweet_url.split('?')[0]
        id = tweet_url.split("/")[-1]
        tweet = self.Client.get_tweet(id, expansions=["attachments.media_keys", "author_id", "entities.mentions.username"], media_fields=["url", "preview_image_url", "type", "variants"], tweet_fields=["author_id"], user_fields=["username"])
        media_url = []
        if "media" in tweet.includes:
            media = tweet.includes['media']
            for i in media:
                if i.url:
                    media_url.append([i.url, i.type])
                else:
                    for variant in i.variants:
                        if variant['content_type'] == 'video/mp4':
                            media_url.append([variant['url'].split('?')[0], i.type])
                            break
                    else:
                        media_url.append([i['variant'][-1]['url'], i.type])
                            
        tweet_body = tweet.data.text
        displayname = tweet.includes['users'][0]['name']
        username = tweet.includes['users'][0]['username']
        try:
            media_link = re.search("(?P<url>https?://[^\s]+)", tweet_body).group("url")
            tweet_body = tweet_body.replace(media_link, "")
        except:
            media_link = ""
            pass

        tweet = {'text': tweet_body, 'media': media_url, 'displayname': displayname, 'tweet_id': id, 'name': username, 'url': tweet_url}
        return tweet


class TelegramBot():

    def __init__(self, creds, twitter_api, db_log) -> None:
        self.twitter_api = twitter_api
        self.db_log = db_log
        self.creds = creds
        self.CHAT_ID = creds["CHAT_ID"]
        self.TOKEN = creds["TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]
        self.bot = Bot(token=self.TOKEN)
        

    def start(self, update, context=None):
        update.message.reply_text('Hello {}'.format(update.message.from_user.first_name))

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
        db_log.tweet_log(log_args)

    def on_data(self,tweet):
        try:
            tweet_id = tweet['tweet_id']
            tg_text = tweet['text']
            tw_screen_name = tweet['displayname']
            tweet_url = tweet['url']
            tw_name = tweet['name']
            media_array = []
            tg_text = f"{tg_text} \n\n🔴 <a href='{tweet_url}'>{tw_screen_name}</a>"
            tg_text = f"{tg_text} \n\n {self.CHANNEL_NAME}"
            # tg_text = tg_text.encode('utf-16-le')
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
        except Exception as e:
            db_log.error_log(e)
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


if __name__ == "__main__":
    db_log = Database()
    twitter_api = TwitterClient(creds, db_log)
    bot = TelegramBot(creds, twitter_api, db_log)
    updater = Updater(bot.TOKEN , use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", bot.start))
    dp.add_handler(MessageHandler(Filters.text, bot.receive_tweet))
    updater.start_polling()
    updater.idle()