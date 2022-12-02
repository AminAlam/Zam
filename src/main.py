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
    updater_admin = Updater(admin_bot.TOKEN , use_context=True)
    dp_admin = updater_admin.dispatcher
    dp_admin.add_handler(CommandHandler("start", admin_bot.start))
    dp_admin.add_handler(MessageHandler(Filters.text, admin_bot.receive_tweet))
    updater_admin.start_polling()
    
    suggestions_bot = TelegramSuggestedTweetsBot(creds, twitter_api, db_log)
    updater_suggestions = Updater(suggestions_bot.TOKEN , use_context=True)
    dp_suggestions = updater_suggestions.dispatcher
    dp_suggestions.add_handler(CommandHandler("start", suggestions_bot.start))
    dp_suggestions.add_handler(MessageHandler(Filters.text, suggestions_bot.receive_tweet))
    updater_suggestions.start_polling()
