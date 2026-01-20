#!/usr/bin/env python3
"""
Zam: A Telegram Bot for posting tweets in a Telegram channel.

This bot captures tweets as screenshots and allows admins to schedule
them for posting to a Telegram channel.
"""

import os
import sys
import click
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the working directory to path
working_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(working_dir, 'database'))

from database import Database
from twitter_backend import TwitterClient
from telegram_backend import TelegramAdminBot, TelegramSuggestedTweetsBot
from utils import load_credentials
from migrations import run_migrations


@click.command(help='Zam: A Telegram Bot for posting tweets in a Telegram channel')
@click.option(
    '--time_diff',
    default='3:30',
    help="Difference between the time of the tweet and the time of the server running the bot. Format: HOURS:MINUTES (default: 3:30 for Tehran timezone)"
)
@click.option(
    '--mahsa_message/--no-mahsa_message',
    default=False,
    help="A message about Mahsa Amini's murder will be sent to the channel with a timer which is updated every few seconds."
)
@click.option(
    '--reference_snapshot/--no-reference_snapshot',
    default=True,
    help="A snapshot of the reference tweets (Quoted tweet or the tweet which main tweet is a reply to) will be set as one of the media of the post."
)
@click.option(
    '--num_tweets_to_preserve',
    default=1000,
    type=click.IntRange(500, 5000, clamp=True),
    help="Number of tweets to be saved in the database. Only last num_tweets_to_preserve tweets in the line will be preserved and the old ones will be deleted."
)
@click.option(
    '--user_tweet_limit',
    default=10,
    type=click.IntRange(0, 120, clamp=True),
    help="Maximum number of tweets that a user can send during 1 hour period. Set to 0 for unlimited."
)
def main(time_diff, mahsa_message, reference_snapshot, num_tweets_to_preserve, user_tweet_limit):
    """Main entry point for the Zam bot."""
    
    # Load credentials from environment variables
    creds = load_credentials()
    
    # Validate required credentials
    required_fields = ['ADMIN_TELEGRAM_BOT', 'SUGGESTIONS_TELEGRAM_BOT', 'MAIN_CHANNEL_CHAT_ID', 
                       'ADMIN_CHAT_ID', 'SUGGESTIONS_CHAT_ID', 'CHANNEL_NAME']
    missing_fields = [f for f in required_fields if not creds.get(f)]
    
    if missing_fields:
        print(f"Error: Missing required environment variables: {', '.join(missing_fields)}")
        print("Please ensure all required variables are set in your .env file.")
        sys.exit(1)
    
    # Initialize database
    db = Database()
    
    # Run database migrations to ensure schema is up to date
    print("Running database migrations...")
    run_migrations(db)
    print("Database migrations complete.")
    
    # Parse time difference
    try:
        time_diff_parts = time_diff.split(':')
        time_diff_dict = {
            'hours': time_diff_parts[0],
            'minutes': time_diff_parts[1]
        }
    except (IndexError, ValueError):
        raise click.ClickException("The time_diff should be in format of HOURS:MINUTES (e.g., 3:30)")
    
    # Initialize Twitter client
    twitter_api = TwitterClient(db)
    
    # Initialize Telegram bots
    suggestions_bot = TelegramSuggestedTweetsBot(
        creds=creds,
        twitter_api=twitter_api,
        db=db,
        time_diff=time_diff_dict,
        reference_snapshot=reference_snapshot,
        user_tweet_limit=user_tweet_limit
    )
    
    admin_bot = TelegramAdminBot(
        creds=creds,
        twitter_api=twitter_api,
        db=db,
        suggestions_bot=suggestions_bot,
        time_diff=time_diff_dict,
        mahsa_message=mahsa_message,
        num_tweets_to_preserve=num_tweets_to_preserve,
        reference_snapshot=reference_snapshot
    )
    
    print("=" * 50)
    print("Zam Telegram Bot is running!")
    print("=" * 50)
    print(f"Channel: {creds['CHANNEL_NAME']}")
    print(f"Time difference: {time_diff}")
    print(f"User tweet limit: {user_tweet_limit if user_tweet_limit > 0 else 'Unlimited'}")
    print(f"Mahsa message: {'Enabled' if mahsa_message else 'Disabled'}")
    print("=" * 50)
    
    # Keep the main thread alive
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nShutting down...")
        twitter_api.stop_queue_worker()
        db.close()
        print("Goodbye!")


if __name__ == '__main__':
    main()
