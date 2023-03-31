from configs import * 
sys.path.append(os.path.join(working_dir, 'database'))
from database import Database
from twitter_backend import TwitterClient
from telegram_backend import TelegramAdminBot, TelegramSuggestedTweetsBot

@click.command(help='Zam: A Telegram Bot for posting tweets in a channel')
@click.option('--time_diff', default='0:30', help="Difference between the time of the tweet and the time of the server running the bot. Format: HOURS:MINUTES")
@click.option('--mahsa_message', default=True, help="A message about Mahsa Amini's murder will be sent to the channel with a timer which is updated evety few seconds.")
def main(time_diff, mahsa_message):
    creds = utils.read_credentials(creds_file)
    db_log = Database()
    try:
        time_diff = {'hours':time_diff.split(':')[0], 'minutes':time_diff.split(':')[1]}
    except:
        raise Exception("the time_diff should be in format of HOURS:MINUTES")
    twitter_api = TwitterClient(creds, db_log)
    suggestions_bot = TelegramSuggestedTweetsBot(creds, twitter_api, db_log, time_diff)
    admin_bot = TelegramAdminBot(creds, twitter_api, db_log, suggestions_bot, time_diff, mahsa_message)    


if __name__ == '__main__':
    main()