#!/usr/bin/env python3
"""
Dry-run test script to demonstrate quoted tweet extraction from HTML.
This simulates what the extract_tweet_text method does without needing Selenium.
"""

import html

from bs4 import BeautifulSoup


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text - collapse multiple spaces/newlines to single space."""
    import re
    return re.sub(r'\s+', ' ', text).strip()


def extract_tweet_text_from_html(html_content: str) -> dict:
    """
    Extract tweet text from HTML content, including quoted tweets.
    
    This mirrors the logic in tweetcapture/screenshot.py extract_tweet_text()
    but uses BeautifulSoup instead of Selenium for testing.
    
    Args:
        html_content: HTML string of the tweet article element
        
    Returns:
        dict with:
            - main_text: The main tweet text
            - quoted_tweet: dict with author, handle, text (or None if no quote)
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    result = {
        'main_text': '',
        'quoted_tweet': None
    }

    # Find all tweetText elements
    text_elements = soup.find_all(attrs={'data-testid': 'tweetText'})

    # Find quoted tweet container - it's a div with role="link" and tabindex="0"
    quoted_container = None
    quoted_text = ''
    quoted_author = ''
    quoted_handle = ''

    # Look for quoted tweet containers
    for container in soup.find_all('div', attrs={'role': 'link', 'tabindex': '0'}):
        # Check if this container has a tweetText inside (indicates it's a quoted tweet)
        inner_text = container.find(attrs={'data-testid': 'tweetText'})
        if inner_text:
            quoted_container = container
            quoted_text = normalize_whitespace(inner_text.get_text())

            # Extract author name from the quoted tweet
            user_name_el = container.find(attrs={'data-testid': 'User-Name'})
            if user_name_el:
                # Get author name - look for spans with the actual name
                spans = user_name_el.find_all('span', class_='css-1jxf684')
                for span in spans:
                    text = normalize_whitespace(span.get_text())
                    if text and not text.startswith('@') and text not in ['·', '']:
                        # Check if it's not a timestamp or other metadata
                        if not any(c.isdigit() for c in text) or len(text) > 3:
                            if 'Verified' not in str(span.parent):
                                quoted_author = text
                                break

                # Look for the handle (@username)
                for span in spans:
                    text = normalize_whitespace(span.get_text())
                    if text.startswith('@'):
                        quoted_handle = text
                        break

            break

    # Get main tweet text (first tweetText that's not in the quoted container)
    if text_elements:
        for text_el in text_elements:
            text = normalize_whitespace(text_el.get_text())
            # If we have a quoted container, check if this text element is inside it
            if quoted_container:
                if text_el in quoted_container.descendants:
                    continue  # Skip - this is the quoted tweet text
            result['main_text'] = text
            break

        # Set quoted tweet info if found
        if quoted_container and quoted_text:
            result['quoted_tweet'] = {
                'author': quoted_author,
                'handle': quoted_handle,
                'text': quoted_text
            }

    return result


def format_telegram_message(tweet_data: dict) -> str:
    """
    Format the extracted tweet data as a Telegram message.
    
    This mirrors the logic in telegram_backend.py format_tweet_message()
    
    Args:
        tweet_data: Dict with main_text, quoted_tweet
        
    Returns:
        Formatted HTML message string
    """
    username = "Mehdi70501002"  # From the sample HTML
    tweet_url = "https://twitter.com/Mehdi70501002/status/2013798653408722966"
    capture_date_persian = "1403/11/02"
    channel_name = "@YourChannel"

    ocr_text = tweet_data.get('main_text', '')
    quoted_tweet = tweet_data.get('quoted_tweet')

    tg_text = f"✍️ <a href='{tweet_url}'>{username}</a>\n"
    tg_text += f"📅 {capture_date_persian}\n"

    # Add main tweet text if available
    if ocr_text and ocr_text.strip():
        clean_ocr = ocr_text.strip()
        if len(clean_ocr) > 400:
            clean_ocr = clean_ocr[:400] + '...'
        clean_ocr = html.escape(clean_ocr)
        tg_text += f"\n📝 {clean_ocr}\n"

    # Add quoted tweet as a blockquote if available
    if quoted_tweet and quoted_tweet.get('text'):
        quote_text = quoted_tweet.get('text', '').strip()
        quote_author = quoted_tweet.get('author', '')
        quote_handle = quoted_tweet.get('handle', '')

        if quote_text:
            if len(quote_text) > 300:
                quote_text = quote_text[:300] + '...'
            quote_text = html.escape(quote_text)
            quote_author = html.escape(quote_author) if quote_author else ''
            quote_handle = html.escape(quote_handle) if quote_handle else ''

            # Format the quote header
            if quote_author and quote_handle:
                quote_header = f"💬 {quote_author} ({quote_handle}):"
            elif quote_author:
                quote_header = f"💬 {quote_author}:"
            elif quote_handle:
                quote_header = f"💬 {quote_handle}:"
            else:
                quote_header = "💬 Quote:"

            tg_text += f"\n<blockquote>{quote_header}\n{quote_text}</blockquote>\n"

    tg_text += f"\n{channel_name}"

    return tg_text


def main():
    # Read the sample HTML file
    with open('sample_tweet_article.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    print("=" * 60)
    print("🔍 EXTRACTING TWEET TEXT FROM HTML")
    print("=" * 60)

    # Extract the tweet text
    result = extract_tweet_text_from_html(html_content)

    print("\n📊 EXTRACTION RESULT:")
    print("-" * 40)
    print(f"Main text: {result['main_text']}")
    print("-" * 40)

    if result['quoted_tweet']:
        print("Quoted tweet:")
        print(f"  Author: {result['quoted_tweet']['author']}")
        print(f"  Handle: {result['quoted_tweet']['handle']}")
        print(f"  Text: {result['quoted_tweet']['text']}")
    else:
        print("Quoted tweet: None")

    print("\n" + "=" * 60)
    print("📱 FORMATTED TELEGRAM MESSAGE (HTML)")
    print("=" * 60)

    # Format as Telegram message
    telegram_message = format_telegram_message(result)
    print("\n" + telegram_message)

    print("\n" + "=" * 60)
    print("📱 TELEGRAM MESSAGE PREVIEW (Rendered)")
    print("=" * 60)

    # Show a plain-text preview of how it would look
    preview = telegram_message
    preview = preview.replace('<a href=\'', '[')
    preview = preview.replace('\'>', '] ')
    preview = preview.replace('</a>', '')
    preview = preview.replace('<blockquote>', '\n  ┃ ')
    preview = preview.replace('</blockquote>', '\n  ┗━━━━━━━━━━━━━━━━━━━━━━━')

    print("\n" + preview)


if __name__ == '__main__':
    main()
