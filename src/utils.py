import json 
from configs import *
from telegraph import Telegraph
from persiantools.jdatetime import JalaliDate

def read_credentials(creds_file):
    with open(creds_file) as f:
        creds = json.load(f)
    return creds

def covert_tweet_time_to_desired_time(date, time_diff):
    date = dt.datetime.strptime(date, '%Y-%m-%d %H:%M:%S') + dt.timedelta(hours=int(time_diff['hours']), minutes=int(time_diff['minutes']))
    date = f"{JalaliDate(date).strftime('%Y/%m/%d')} {date.strftime('%H:%M:%S')}"
    return date

def set_state(conn, args):
    chat_id = args['chat_id']
    state = args['state']
    cursor = conn.cursor()
    # check if the chat_id already exists
    cursor.execute('select * from States where chat_id=?', (chat_id,))
    states = cursor.fetchall()

    if len(states)==0:
        # create a new state
        rows = [(chat_id, state, None)]
        cursor.executemany('insert into States values (?, ?, ?)', rows)
        conn.commit()

    else:
        # update the state
        cursor.execute('update States set state=? where chat_id=?', (state, chat_id))
        conn.commit()

def check_state(conn, args):
    chat_id = args['chat_id']
    cursor = conn.cursor()
    cursor.execute('select * from States where chat_id=?', (chat_id,))
    states = cursor.fetchall()

    if len(states)==0:
        return None
    else:
        return states[0][1]
    
def get_time_counter_message_id(conn):
    cursor = conn.cursor()
    cursor.execute('select * from time_counter')
    time_counter = cursor.fetchall()
    if len(time_counter)==0:
        return None
    else:
        return time_counter[0][0]
    
def set_time_counter_message_id(conn, message_id):
    cursor = conn.cursor()
    cursor.execute('insert into time_counter values (?)', (message_id,))
    conn.commit()

def form_time_counter_message(diff_time, message_txt):
    days = diff_time.days
    seconds = diff_time.seconds
    hours = seconds//3600
    minutes = (seconds//60) % 60
    message_txt = f"{days} days, {hours} hours, and {minutes} {message_txt}"
    return message_txt

def parse_text(text):
    text = re.sub(r' https://t.co/\w{10}', '', text)
    text = re.sub(r'(https?://\S+)', r'<a href="\1">Link</a>', text)
    text = re.sub(r'@(\w+)', r'<a href="https://twitter.com/\1">\1</a>', text)
    return text

def get_next_sending_time(tweets_line, desired_num_tweets_per_hour=6):
    tweets_sent_time = [dt.datetime.strptime(tweet[3], '%Y-%m-%d %H:%M:%S') for tweet in tweets_line if tweet[3] is not None]
    time_now = dt.datetime.now()
    current_hour = int(time_now.strftime('%H'))
    current_minute = int(time_now.strftime('%M'))
    for hour in range(current_hour, 24):
        tweets_in_this_hour = [tweet for tweet in tweets_sent_time if tweet.hour==hour]
        if len(tweets_in_this_hour)<desired_num_tweets_per_hour:
            random_minute = random.randint(current_minute, 59)
            random_hour = random.randint(current_hour, current_hour+2)
            if random_hour < 0 :
                random_hour = 0
            elif random_hour >=24 :
                random_hour = 23 
            desired_time = time_now.replace(hour=random_hour, minute=random_minute, second=0)
            break
    else:
        random_hour = random.randint(current_hour, 23)
        random_minute = random.randint(current_minute, 59)
        desired_time = time_now.replace(hour=random_hour, minute=random_minute, second=0)
    
    return desired_time

def deleted_snapshots(media_list):
    for media in media_list:
        if media[1]=='photo':
            if not media[0].startswith("http"):
                os.remove(media[0])

def user_limit_exceeded(conn, user_name, user_tweet_limit):
    time_1_hour_ago = dt.datetime.now() - dt.timedelta(hours=1)
    cursor = conn.cursor()
    cursor.execute('select * from Tweets where user_name=? and time>?', (user_name, time_1_hour_ago))
    tweets = cursor.fetchall()
    if len(tweets)>=user_tweet_limit:
        return True
    else:
        return False


class telegraph():
    def __init__(self, account_name):
        self.account_name = account_name
        self.telegraph = Telegraph()
        self.api_url = 'https://api.telegra.ph'
        self.create_account()

    def create_account(self):
        try:
            short_name = self.account_name
            author_name = self.account_name
            self.author_url = 'https://t.me/{}'.format(self.account_name)
            self.access_token = self.telegraph.create_account(short_name=short_name, author_name=author_name, 
                                                            author_url=self.author_url, replace_token=True)['access_token']
        except:
            print('Error in creating account')

    def create_page(self, title, html_content):
        try:
            page = self.telegraph.create_page(title=title, html_content=html_content, author_name=self.account_name, 
                                            author_url=self.author_url, return_content=True)
            return page['url']
        except:
            print('Error in creating page')
            return None