import asyncio
import sys
import logging
from pyrogram import Client, idle

from config import API_ID, API_HASH, BOT_TOKEN
from database.db_handler import init_db
from handlers.command_handlers import (
    start_command, help_command, dl_album_command, 
    dl_select_command, status_command, cancel_command
)
from handlers.message_handlers import handle_track_selection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Pyrogram client
app = Client(
    "apple_music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Register handlers
def register_handlers():
    # Commands
    app.add_handler(start_command)
    app.add_handler(help_command)
    app.add_handler(dl_album_command)
    app.add_handler(dl_select_command)
    app.add_handler(status_command)
    app.add_handler(cancel_command)
    
    # Message handlers
    app.add_handler(handle_track_selection)

async def main():
    # Initialize database
    init_db()
    
    # Register handlers
    register_handlers()
    
    # Start the bot
    await app.start()
    logger.info("🤖 Apple Music Downloader Bot started!")
    
    # Keep the bot running
    await idle()

if __name__ == "__main__":
    # Run the bot
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)