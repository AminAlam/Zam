from configs import * 

class TwitterClient(object):
    def __init__(self, creds, db_log):
        self.db_log = db_log
        self.creds = creds
        self.TweetCapture = TweetCapture()
        self.TweetCapture.add_chrome_argument('--disable-gpu')
        self.TweetCapture.add_chrome_argument('--radius=0')
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
        parent_tweet_id = None
        quoted_tweet_id = None
        if 'referenced_tweets' in tweet.data:
            for field in tweet.data['referenced_tweets']:
                if field['type'] == 'replied_to':
                    parent_tweet_id = field['id']
                elif field['type'] == 'quoted':
                    quoted_tweet_id = field['id']

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
        tweet_body = utils.parse_text(tweet_body)

        tweet = {'text': tweet_body, 'media': media_url, 'displayname': displayname, 'tweet_id': id, 
                'name': username, 'url': tweet_url, 'tweet_date_persian':tweet_date_persian, 
                'parent_tweet_id': parent_tweet_id, 'quoted_tweet_id': quoted_tweet_id}

        return tweet

    def get_reference_tweet_snapshot_as_media(self, tweet_url, tweet_id):
        if not os.path.exists(os.path.join(working_dir, 'screenshots_null')):
            os.makedirs(os.path.join(working_dir, 'screenshots_null'))
        random_number = random.randint(1, 1000000000)
        file_path = os.path.join(working_dir, 'screenshots_null', f'{tweet_id}_{random_number}.png')
        asyncio.run(self.TweetCapture.screenshot(tweet_url, file_path, mode=4, night_mode=2))
        return [file_path, 'photo']