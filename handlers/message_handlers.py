import re
from pyrogram import Client, filters
from pyrogram.types import Message

from handlers.command_handlers import waiting_for_tracks
from database.db_handler import add_download_request
from services.download_service import process_queue
import asyncio

@filters.private & filters.reply & ~filters.command
async def handle_track_selection(client: Client, message: Message):
    """Handle track selection replies"""
    # Check if this is a reply to a track selection message
    user_id = message.from_user.id
    
    if user_id not in waiting_for_tracks:
        return
    
    # Get the user's pending selection info
    selection_info = waiting_for_tracks[user_id]
    
    # Check if this is a reply to the correct message
    if message.reply_to_message_id != selection_info["message_id"]:
        return
    
    # Process the track selection
    tracks_text = message.text.strip()
    
    # Validate track input (should be comma-separated numbers)
    if not re.match(r'^[0-9,\s]+$', tracks_text):
        await message.reply(
            "❌ Invalid format. Please provide track numbers separated by commas.\n"
            "Example: `1,3,5`"
        )
        return
    
    # Clean up the tracks input
    tracks = ','.join([t.strip() for t in tracks_text.split(',') if t.strip()])
    
    # Add request to database
    request_id = add_download_request(
        chat_id=selection_info["chat_id"],
        user_id=user_id,
        url=selection_info["url"],
        download_type="select",
        tracks=tracks
    )
    
    # Inform user
    await client.edit_message_text(
        chat_id=selection_info["chat_id"],
        message_id=selection_info["message_id"],
        text=f"✅ Your track selection has been queued!\n"
             f"Selected tracks: {tracks}\n"
             f"Request ID: `{request_id}`\n\n"
             f"You will be notified when your download is ready."
    )
    
    # Clean up
    del waiting_for_tracks[user_id]
    
    # Trigger queue processing
    asyncio.create_task(process_queue(client))