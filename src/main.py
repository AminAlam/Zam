from configs import * 
sys.path.append(os.path.join(working_dir, 'database'))
from database import Database
from twitter_backend import TwitterClient
from telegram_backend import TelegramAdminBot, TelegramSuggestedTweetsBot

@click.command(help='Zam: A Telegram Bot for posting tweets in a Telegram channel')
@click.option('--time_diff', default='0:30', help="Difference between the time of the tweet and the time of the server running the bot. Format: HOURS:MINUTES")
@click.option('--mahsa_message', default=True, help="A message about Mahsa Amini's murder will be sent to the channel with a timer which is updated evety few seconds.")
@click.option('--reference_snapshot', default=True, help="A snapshot of the reference tweets (Qouted tweet or the tweet which main tweet is a reply to) will be set as one of the media of the post. Note that this feature needs chromium to function")
@click.option('--num_tweets_to_preserve', default=1000, type=click.IntRange(500, 5000, clamp=True), help="Number of tweets to be saved in the database. Only last num_tweets_to_preserve tweets in the line will be preserved and the old ones will be deleted")
def main(time_diff, mahsa_message, reference_snapshot, num_tweets_to_preserve):
    creds = utils.read_credentials(creds_file)
    db_log = Database()
    try:
        time_diff = {'hours':time_diff.split(':')[0], 'minutes':time_diff.split(':')[1]}
    except:
        raise Exception("the time_diff should be in format of HOURS:MINUTES")
    twitter_api = TwitterClient(creds, db_log)
    suggestions_bot = TelegramSuggestedTweetsBot(creds, twitter_api, db_log, time_diff, reference_snapshot)
    admin_bot = TelegramAdminBot(creds, twitter_api, db_log, suggestions_bot, time_diff, mahsa_message, num_tweets_to_preserve, reference_snapshot) 


if __name__ == '__main__':
    main()