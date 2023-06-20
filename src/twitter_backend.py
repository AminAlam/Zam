from configs import * 


class TwitterClient(object):
    def __init__(self, creds, db_log):
        self.db_log = db_log
        self.creds = creds
        self.TweetCapture = TweetCapture()
        self.TweetCapture.add_chrome_argument('--disable-gpu')
        self.TweetCapture.add_chrome_argument('--radius=0')

        self.driver = webdriver.get_driver(gui=False)
        
    
    def make_tweet_object_from_tweet_url(self, tweet_url):
        self.driver.get(tweet_url)
        time.sleep(5)
        resp = self.driver.page_source
        soup = BeautifulSoup(resp,'html.parser')
        displayname = soup.find('div', {'class':'css-1dbjc4n r-1awozwy r-18u37iz r-1wbh5a2 r-dnmrzs'}).text
        username = soup.find('div', {'class': 'css-1dbjc4n r-18u37iz r-1wbh5a2'}).text
        username = username.split('@')[1]
        tweet_date = soup.find('time').text
        # convert tweet_date to datetime object
        tweet_date = dt.datetime.strptime(tweet_date, '%I:%M %p · %b %d, %Y')
        tweet_body = soup.find('div', {'class': 'css-1dbjc4n r-1s2bzr4'}).text
        tweet_body = tweet_body.split('Translate Tweet')[0]
        media_div = soup.find('div', {'class': 'css-1dbjc4n r-1ssbvtb r-1s2bzr4'})
        images = media_div.find_all('img')
        images = [image['src'] for image in images if '/profile_images/' not in image['src'] and '/media/' in image['src']]
        images = [image.split('&name')[0] for image in images]
        videos = media_div.find_all('video')
        videos = [video['src'] for video in videos]

        tweet = {}
        tweet['data'] = {}
        tweet['includes'] = {}
        tweet['includes']['users'] = [{'username': username, 'name': displayname}]
        tweet['data']['text'] = tweet_body
        tweet['data']['created_at'] = tweet_date

        if images is not None:
            tweet['includes']['media'] = []
            for image in images:
                tweet['includes']['media'].append({'type': 'photo', 'url': image})
        if videos is not None:
            if 'media' not in tweet['includes']:
                tweet['includes']['media'] = []
            for video in videos:
                tweet['includes']['media'].append({'type': 'video', 'url': video})

        return tweet

    def get_tweet(self, tweet_url):
        if '?' in tweet_url:
            tweet_url = tweet_url.split('?')[0]
        id = tweet_url.split("/")[-1]

        tweet = self.make_tweet_object_from_tweet_url(tweet_url)
        
        parent_tweet_id = None
        quoted_tweet_id = None
        if 'referenced_tweets' in tweet['data']:
            for field in tweet['data']['referenced_tweets']:
                if field['type'] == 'replied_to':
                    parent_tweet_id = field['id']
                elif field['type'] == 'quoted':
                    quoted_tweet_id = field['id']

        tweet_date = tweet['data']['created_at']
        # converting to Tehran time-zone
        tweet_date = tweet_date + dt.timedelta(hours=3, minutes=30)
        tweet_date_persian = JalaliDate(tweet_date).strftime("%Y/%m/%d")
        
        media_url = []
        if "media" in tweet['includes']:
            media = tweet['includes']['media']
            for i in media:
                if i['url']:
                    media_url.append([i['url'], i['type']])
                else:
                    for variant in i.variants:
                        if variant['content_type'] == 'video/mp4':
                            media_url.append([variant['url'].split('?')[0], i.type])
                            break
                    else:
                        media_url.append([i['variant'][-1]['url'], i.type])
                            
        tweet_body = tweet['data']['text']
        displayname = tweet['includes']['users'][0]['name']
        username = tweet['includes']['users'][0]['username']
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