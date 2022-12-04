from configs import * 

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
        tweet = self.Client.get_tweet(id, expansions=["attachments.media_keys", "author_id", "entities.mentions.username"], media_fields=["url", "preview_image_url", "type", "variants"], tweet_fields=["author_id", "created_at", "referenced_tweets"], user_fields=["username"])
        
        if 'referenced_tweets' in tweet.data:
            for field in tweet.data['referenced_tweets']:
                if field['type'] == 'replied_to':
                    parent_tweet_id = field['id']
                    break
            else:
                parent_tweet_id = None
        else:
            parent_tweet_id = None

        tweet_date = tweet.data['created_at']
        # converting to Tehran time-zone
        tweet_date = tweet_date + dt.timedelta(hours=3, minutes=30)
        tweet_date_persian = JalaliDate(tweet_date).strftime("%Y/%m/%d")
        
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

        tweet = {'text': tweet_body, 'media': media_url, 'displayname': displayname, 'tweet_id': id, 'name': username, 'url': tweet_url, 'tweet_date_persian':tweet_date_persian, 'parent_tweet_id': parent_tweet_id}
        return tweet