import os
import yt_dlp
import logging
import traceback
from config import Config

DOWNLOADS_DIR = os.environ.get("DOWNLOADS_DIR", "/input")
logger = logging.getLogger("telegram_youtube_bot.downloader")

def download_url(url, chat_id=None, progress_callback=None):
    """
    Downloads a given URL to the DOWNLOADS_DIR, using cookies if configured.
    Logs all exceptions with full tracebacks and yt-dlp output.
    """
    ydl_opts = {
        'outtmpl': f"{DOWNLOADS_DIR}/%(title)s.%(ext)s",
        'cookiefile': Config.COOKIES_FILE if Config.COOKIES_FILE else None,
        'progress_hooks': [progress_callback] if progress_callback else [],
        'quiet': False,         # Set to False to get all yt-dlp output
        'no_warnings': False,   # Show warnings for troubleshooting
        'logger': logger,
        # If you want to always overwrite, uncomment the next line:
        'overwrites': True,
    }

    logger.info(f"Download directory: {DOWNLOADS_DIR}")
    logger.info(f"yt-dlp options: {ydl_opts}")
    logger.info(f"Starting yt-dlp download for URL: {url}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])
        logger.info(f"yt-dlp download finished with result: {result}")
        return result
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Download failed for URL {url}:\nException: {e}\nTraceback:\n{tb}")
        return f"Download failed: {e}"

# Optional: Standalone test
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(download_url(test_url))
