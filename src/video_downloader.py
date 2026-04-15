"""
yt-dlp wrapper for downloading Twitter/X videos.

Isolated here so the rest of the project never imports yt-dlp directly,
making it easy to swap backends later if needed.
"""

import glob
import os
import tempfile

import yt_dlp


class VideoDownloadError(Exception):
    """Raised on unrecoverable yt-dlp failures (network error, crash)."""


def _build_cookie_file(auth_token):
    if not auth_token:
        return None
    fd, path = tempfile.mkstemp(prefix="ytdlp_cookies_", suffix=".txt")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("# Netscape HTTP Cookie File\n")
            fh.write(f".twitter.com\tTRUE\t/\tTRUE\t2147483647\tauth_token\t{auth_token}\n")
            fh.write(f".x.com\tTRUE\t/\tTRUE\t2147483647\tauth_token\t{auth_token}\n")
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    return path


def download_tweet_videos(tweet_url, output_dir, tweet_id):
    """Download every video in a tweet to output_dir and return local MP4 paths.

    Returns [] when the tweet has no videos. Raises VideoDownloadError only on
    infrastructure failures (yt-dlp itself crashed, network unreachable, etc).
    """
    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    def hook(d):
        if d.get("status") == "finished":
            filename = d.get("filename")
            if filename:
                downloaded.append(filename)

    cookie_file = _build_cookie_file(os.environ.get("AUTH_TOKEN"))

    ydl_opts = {
        "outtmpl": os.path.join(output_dir, f"{tweet_id}_%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
        "progress_hooks": [hook],
    }
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([tweet_url])
    except yt_dlp.utils.DownloadError as e:
        # yt-dlp raises DownloadError both for "no video in this tweet" and for
        # transient network errors. Treat it as "no videos"; the caller decides
        # whether to fall back to ScrapeBadger's preview thumbnail.
        print(f"[DEBUG] yt-dlp DownloadError for {tweet_url}: {e}")
        return []
    except Exception as e:
        raise VideoDownloadError(f"yt-dlp crashed for {tweet_url}: {e}") from e
    finally:
        if cookie_file:
            try:
                os.remove(cookie_file)
            except OSError:
                pass

    # Resolve any paths yt-dlp may have merged/remuxed into a different filename
    resolved = []
    for path in downloaded:
        if os.path.exists(path):
            resolved.append(path)
            continue
        # yt-dlp sometimes reports the pre-merge filename; look for mp4 siblings
        base = os.path.splitext(path)[0]
        matches = glob.glob(base + ".mp4") + glob.glob(base + ".*")
        for m in matches:
            if os.path.exists(m) and m not in resolved:
                resolved.append(m)
                break
    return resolved
