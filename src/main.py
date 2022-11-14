import tweepy
import json 
import re
import sys
from telegram import Bot, InputMediaPhoto, InputMediaVideo, MessageEntity
from pathlib import Path

def read_credentials():
    with open("src/creds.json") as f:
        creds = json.load(f)
    return creds

# Authenticate to Twitter
creds = read_credentials()


class TwitterClient(object):
    def __init__(self, creds):
        # keys and tokens from the Twitter Dev Console
        consumer_key = creds["API_KEY"]
        consumer_secret = creds["API_KEY_SECRET"]
        access_token = creds["ACCESS_TOKEN"]
        access_token_secret = creds["ACCESS_TOKEN_SECRET"]
        bearer_token = creds["BEARER_TOKEN"]
        try:
            self.Client = tweepy.Client(bearer_token, consumer_key, consumer_secret, access_token, access_token_secret)
        except:
            print("Error: Authentication Failed")
  
    def get_tweet(self, tweet_url):
        id = tweet_url.split("/")[-1]
        tweet = self.Client.get_tweet(id, expansions=["attachments.media_keys", "author_id", "entities.mentions.username"], media_fields=["url", "preview_image_url", "type", "variants"], tweet_fields=["author_id"], user_fields=["username"])
        media_url = []
        if "media" in tweet.includes:
            media = tweet.includes['media']
            for i in media:
                if i.url:
                    media_url.append([i.url, i.type])
                else:
                    media_url.append([i.variants[0]['url'], i.type])
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

    def __init__(self, creds) -> None:
        self.CHAT_ID = creds["CHAT_ID"]
        self.TOKEN = creds["TELEGRAM_BOT"]
        self.CHANNEL_NAME = creds["CHANNEL_NAME"]

    def on_data(self,tweet):
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
        else:
            pass
        tweet_link = "https://twitter.com/"+tw_screen_name+"/status/"+tweet_id
        bot = Bot(token=self.TOKEN)
        # bot.sendMessage(chat_id=self.CHAT_ID,text=tg_text+"\n"+tweet_url+"\n"+"Via"+"|"+"<a href='"+tweet_link+"'>"+tw_name+"</a>"+"|",timeout=200,disable_web_page_preview=False,parse_mode=ParseMode.HTML)
        bot.sendMediaGroup(chat_id=self.CHAT_ID,media=media_array,timeout=200)

        return True

    def on_error(self,status):
        print(status.text)
        
    def on_error(self,status_code):
        if status_code == 420:
            return False


if __name__ == "__main__":
    
    api = TwitterClient(creds)
    tweet = api.get_tweet(tweet_url="https://twitter.com/milaniabbas/status/1591764320576507907")
    bot = TelegramBot(creds)
    bot.on_data(tweet)