"""
ScrapeBadger API client for fetching tweet metadata.

Provides tweet JSON retrieval and photo/thumbnail downloads with retry logic.
Video downloads are handled separately by src/video_downloader.py (yt-dlp).
"""

import os
import time

import requests

from .configs import ScrapeBadgerConfig


class ScrapeBadgerError(Exception):
    """Raised when the ScrapeBadger API cannot serve a tweet after retries."""


class ScrapeBadgerClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("SCRAPEBADGER_API_KEY", "")
        if not self.api_key:
            raise ScrapeBadgerError("SCRAPEBADGER_API_KEY env var is not set")
        self._session = requests.Session()
        self._session.headers.update({"x-api-key": self.api_key})

    def fetch_tweet(self, tweet_id):
        url = ScrapeBadgerConfig.BASE_URL + ScrapeBadgerConfig.TWEET_ENDPOINT.format(tweet_id=tweet_id)
        last_exc = None
        for attempt in range(ScrapeBadgerConfig.MAX_RETRIES):
            try:
                resp = self._session.get(url, timeout=ScrapeBadgerConfig.REQUEST_TIMEOUT)
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    last_exc = ScrapeBadgerError(
                        f"ScrapeBadger {resp.status_code} for tweet {tweet_id}: {resp.text[:200]}"
                    )
                    self._sleep_backoff(attempt)
                    continue
                if resp.status_code >= 400:
                    raise ScrapeBadgerError(
                        f"ScrapeBadger {resp.status_code} for tweet {tweet_id}: {resp.text[:200]}"
                    )
                return resp.json()
            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = ScrapeBadgerError(f"ScrapeBadger network error for tweet {tweet_id}: {e}")
                self._sleep_backoff(attempt)
                continue
        raise last_exc or ScrapeBadgerError(f"ScrapeBadger failed for tweet {tweet_id}")

    def download_media(self, url, dest_path):
        if not url:
            raise ScrapeBadgerError("download_media called with empty url")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            with self._session.get(
                url, stream=True, timeout=ScrapeBadgerConfig.MEDIA_DOWNLOAD_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            fh.write(chunk)
        except requests.RequestException as e:
            raise ScrapeBadgerError(f"Failed to download {url}: {e}") from e
        return dest_path

    @staticmethod
    def _sleep_backoff(attempt):
        time.sleep(ScrapeBadgerConfig.RETRY_BACKOFF_BASE * (2 ** attempt))
