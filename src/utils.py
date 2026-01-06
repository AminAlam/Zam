"""
Utility functions for Zam Telegram Bot.
"""

import os
import re
import datetime as dt
from telegraph import Telegraph
from persiantools.jdatetime import JalaliDate


def load_credentials():
    """
    Load credentials from environment variables.
    
    Returns:
        dict: Credentials dictionary
    """
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    admin_ids = [x.strip() for x in admin_ids_str.split(',') if x.strip()]

    return {
        'ADMIN_TELEGRAM_BOT': os.getenv('ADMIN_TELEGRAM_BOT', ''),
        'SUGGESTIONS_TELEGRAM_BOT': os.getenv('SUGGESTIONS_TELEGRAM_BOT', ''),
        'MAIN_CHANNEL_CHAT_ID': os.getenv('MAIN_CHANNEL_CHAT_ID', ''),
        'ADMIN_CHAT_ID': os.getenv('ADMIN_CHAT_ID', ''),
        'SUGGESTIONS_CHAT_ID': os.getenv('SUGGESTIONS_CHAT_ID', ''),
        'CHANNEL_NAME': os.getenv('CHANNEL_NAME', ''),
        'ADMIN_IDS': admin_ids,
    }


def covert_tweet_time_to_desired_time(date, time_diff):
    """
    Convert a tweet time to the desired timezone.
    
    Args:
        date: Date string in format '%Y-%m-%d %H:%M:%S'
        time_diff: Dict with 'hours' and 'minutes' keys
        
    Returns:
        Formatted date string with Persian date
    """
    date = dt.datetime.strptime(date, '%Y-%m-%d %H:%M:%S') + dt.timedelta(
        hours=int(time_diff['hours']),
        minutes=int(time_diff['minutes'])
    )
    date = f"{JalaliDate(date).strftime('%Y/%m/%d')} {date.strftime('%H:%M:%S')}"
    return date


def form_time_counter_message(diff_time, message_txt):
    """
    Format the time counter message.
    
    Args:
        diff_time: timedelta object
        message_txt: Message template
        
    Returns:
        Formatted message string
    """
    days = diff_time.days
    seconds = diff_time.seconds
    hours = seconds // 3600
    minutes = (seconds // 60) % 60
    message_txt = f"{days} days, {hours} hours, and {minutes} {message_txt}"
    return message_txt


def parse_text(text):
    """
    Parse tweet text to add HTML formatting.
    
    Args:
        text: Raw tweet text
        
    Returns:
        Formatted text with HTML links
    """
    text = re.sub(r' https://t.co/\w{10}', '', text)
    text = re.sub(r'(https?://\S+)', r'<a href="\1">Link</a>', text)
    text = re.sub(r'@(\w+)', r'<a href="https://twitter.com/\1">\1</a>', text)
    return text


def deleted_snapshots(media_list):
    """
    Delete local screenshot files.
    
    Args:
        media_list: List of media items
    """
    if not media_list:
        return

    for media in media_list:
        if len(media) >= 2 and media[1] == 'photo':
            if not media[0].startswith("http"):
                try:
                    os.remove(media[0])
                except Exception as e:
                    print(f"Failed to delete screenshot: {e}")


class telegraph:
    """Telegraph API wrapper for creating pages."""

    def __init__(self, account_name):
        self.account_name = account_name
        self.telegraph = Telegraph()
        self.api_url = 'https://api.telegra.ph'
        self.create_account()

    def create_account(self):
        """Create a Telegraph account."""
        try:
            short_name = self.account_name
            author_name = self.account_name
            self.author_url = f'https://t.me/{self.account_name}'
            self.access_token = self.telegraph.create_account(
                short_name=short_name,
                author_name=author_name,
                author_url=self.author_url,
                replace_token=True
            )['access_token']
        except Exception as e:
            print(f'Error in creating account: {e}')

    def create_page(self, title, html_content):
        """
        Create a Telegraph page.
        
        Args:
            title: Page title
            html_content: HTML content for the page
            
        Returns:
            Page URL or None on error
        """
        try:
            page = self.telegraph.create_page(
                title=title,
                html_content=html_content,
                author_name=self.account_name,
                author_url=self.author_url,
                return_content=True
            )
            return page['url']
        except Exception as e:
            print(f'Error in creating page: {e}')
            return None
