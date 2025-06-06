import os

class Config:
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_IDS = [int(i) for i in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if i.strip()]
    COOKIES_FILE = os.getenv("YT_DLP_COOKIES_FILE", "/cookies/cookies.txt")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    GOOGLE_DRIVE_FILE_ID = os.getenv("GOOGLE_DRIVE_COOKIES_FILE_ID", None)
    GOOGLE_DRIVE_SERVICE_ACCOUNT = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT", None)  # Path to service account json
    GOOGLE_DRIVE_REFRESH_INTERVAL = int(os.getenv("GOOGLE_DRIVE_REFRESH_INTERVAL", 3600))  # seconds
