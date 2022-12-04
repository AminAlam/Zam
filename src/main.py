from configs import * 

import sys
sys.path.append('/home/amin/Documents/Twitter_Parser/src/database')
from database import Database
from twitter_backend import TwitterClient
from telegram_backend import TelegramAdminBot, TelegramSuggestedTweetsBot



if __name__ == "__main__":
    creds = utils.read_credentials(creds_file)
    db_log = Database()
    twitter_api = TwitterClient(creds, db_log)

    admin_bot = TelegramAdminBot(creds, twitter_api, db_log)
        
    suggestions_bot = TelegramSuggestedTweetsBot(creds, twitter_api, db_log)

