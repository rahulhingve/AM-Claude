import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API credentials
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Directory settings
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "apple-music-alac-atmos-downloader/AM-DL downloads/")
TEMP_DIR = os.getenv("TEMP_DIR", "/tmp/music_downloads/")

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot_database.db")

# Command timeout (in seconds)
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "30"))

# Maximum concurrent downloads
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))