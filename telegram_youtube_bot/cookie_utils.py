import os
import logging
import time

from config import Config

def cookies_available():
    return os.path.isfile(Config.COOKIES_FILE)

def last_modified():
    if not cookies_available():
        return None
    return time.ctime(os.path.getmtime(Config.COOKIES_FILE))

def fetch_cookies_from_drive():
    """
    Download latest cookies.txt from Google Drive to Config.COOKIES_FILE.
    Requires Google Drive file ID and service account JSON.
    """
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive

    if not Config.GOOGLE_DRIVE_FILE_ID or not Config.GOOGLE_DRIVE_SERVICE_ACCOUNT:
        logging.error("Google Drive config missing, cannot update cookies.")
        return False

    try:
        gauth = GoogleAuth()
        gauth.LoadServiceConfigFile(Config.GOOGLE_DRIVE_SERVICE_ACCOUNT)
        gauth.ServiceAuth()
        drive = GoogleDrive(gauth)
        file = drive.CreateFile({'id': Config.GOOGLE_DRIVE_FILE_ID})
        file.GetContentFile(Config.COOKIES_FILE)
        logging.info("Successfully fetched cookies.txt from Google Drive.")
        return True
    except Exception as e:
        logging.error(f"Error fetching cookies from Google Drive: {e}")
        return False
