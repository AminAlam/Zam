#!/usr/bin/env python3
"""
Dry run test for quoted tweet extraction logic.
This simulates what extract_tweet_text() does but using BeautifulSoup instead of Selenium.
"""

import html
import json

from bs4 import BeautifulSoup


def extract_tweet_text_from_html(html_content):
    """
    Extract tweet text from HTML content using BeautifulSoup.
    Simulates the Selenium-based extract_tweet_text method.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    result = {
        'main_text': '',
        'quoted_tweet': None
    }

    # Find the main tweet article
    article = soup.find('article', {'data-testid': 'tweet'})
    if not article:
        print("❌ No tweet article found")
        return result

    print("✅ Found tweet article")

    # Find quoted tweet container - it's a clickable div with role="link" and tabindex="0"
    quoted_container = None
    quoted_text = ''
    quoted_author = ''
    quoted_handle = ''

    # Look for the quoted tweet container
    link_divs = article.find_all('div', {'role': 'link', 'tabindex': '0'})
    print(f"📌 Found {len(link_divs)} potential quoted tweet containers")

    for container in link_divs:
        # Check if this container has a tweetText inside
        inner_text = container.find('div', {'data-testid': 'tweetText'})
        if inner_text:
            quoted_container = container
            quoted_text = inner_text.get_text(strip=True)
            print(f"✅ Found quoted tweet text: {quoted_text[:50]}...")

            # Extract author name from the quoted tweet
            user_name_el = container.find('div', {'data-testid': 'User-Name'})
            if user_name_el:
                # Get author name - first span with actual text
                spans = user_name_el.find_all('span')
                for span in spans:
                    text = span.get_text(strip=True)
                    if text and not text.startswith('@') and text not in ['·', '']:
                        if not quoted_author:
                            quoted_author = text
                            print(f"✅ Found quoted author: {quoted_author}")
                    elif text.startswith('@'):
                        quoted_handle = text
                        print(f"✅ Found quoted handle: {quoted_handle}")
            break

    # Find all tweetText elements
    tweet_texts = article.find_all('div', {'data-testid': 'tweetText'})
    print(f"📌 Found {len(tweet_texts)} tweetText elements total")

    if tweet_texts:
        if quoted_container and len(tweet_texts) > 1:
            # The first tweetText is the main tweet, quoted is inside the container
            main_text = tweet_texts[0].get_text(strip=True)

            # Verify main text is not the quoted text
            if main_text == quoted_text and len(tweet_texts) > 1:
                main_text = tweet_texts[1].get_text(strip=True)

            result['main_text'] = main_text
            result['quoted_tweet'] = {
                'author': quoted_author,
                'handle': quoted_handle,
                'text': quoted_text
            }
        else:
            # No quoted tweet
            result['main_text'] = tweet_texts[0].get_text(strip=True)

    return result


def format_telegram_message(username, tweet_url, capture_date, ocr_text, quoted_tweet, channel_name):
    """
    Format the extracted data as a Telegram message.
    Simulates format_tweet_message() from telegram_backend.py
    """
    tg_text = f"✍️ <a href='{tweet_url}'>{username}</a>\n"
    tg_text += f"📅 {capture_date}\n"

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
    print("=" * 60)
    print("🧪 DRY RUN: Tweet Quote Extraction Test")
    print("=" * 60)

    # Read the sample HTML file
    with open('sample_tweet_article.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    print(f"\n📄 Loaded sample_tweet_article.html ({len(html_content)} bytes)\n")

    # Extract tweet text
    print("--- EXTRACTION PHASE ---\n")
    result = extract_tweet_text_from_html(html_content)

    print("\n--- EXTRACTION RESULT ---\n")
    print(f"Main text: {result['main_text']}")
    print(f"Quoted tweet: {json.dumps(result['quoted_tweet'], indent=2, ensure_ascii=False)}")

    # Format as Telegram message
    print("\n--- TELEGRAM MESSAGE FORMAT ---\n")

    tg_message = format_telegram_message(
        username="Mehdi70501002",
        tweet_url="https://twitter.com/Mehdi70501002/status/2013798653408722966",
        capture_date="1403/11/02",
        ocr_text=result['main_text'],
        quoted_tweet=result['quoted_tweet'],
        channel_name="@YourChannelName"
    )

    print("HTML formatted message:")
    print("-" * 40)
    print(tg_message)
    print("-" * 40)

    print("\n--- RENDERED PREVIEW (plain text) ---\n")
    # Simple rendering for preview
    preview = tg_message
    preview = preview.replace('<a href=', '[').replace('</a>', '')
    preview = preview.replace("'>", '] ')
    preview = preview.replace('<blockquote>', '\n  │ ').replace('</blockquote>', '\n')
    print(preview)

    print("\n" + "=" * 60)
    print("✅ Dry run complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
