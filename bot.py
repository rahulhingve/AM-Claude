import asyncio
import sys
import logging
from pyrogram import Client, idle, filters
from pyrogram.handlers import MessageHandler

from config import API_ID, API_HASH, BOT_TOKEN
from database.db_handler import init_db
from handlers import command_handlers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Client(
    "apple_music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def register_handlers():
    # Register the merged /alac command along with /help, /status, and /cancel.
    app.add_handler(MessageHandler(command_handlers.alac_command, filters.command("alac")))
    app.add_handler(MessageHandler(command_handlers.help_command, filters.command("help")))
    app.add_handler(MessageHandler(command_handlers.status_command, filters.command("status")))
    app.add_handler(MessageHandler(command_handlers.cancel_command, filters.command("cancel")))

async def main():
    init_db()
    register_handlers()
    await app.start()
    logger.info("🤖 Bot started!")
    await idle()

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
