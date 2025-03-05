import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.db_handler import (
    add_download_request,
    get_user_active_requests,
    cancel_request,
    get_request_by_id
)
from services.download_service import process_queue
from config import COMMAND_TIMEOUT

# Store waiting users for track selection
waiting_for_tracks = {}

@filters.command("start")
async def start_command(client: Client, message: Message):
    """Handle the /start command"""
    await message.reply(
        "👋 Welcome to Apple Music Downloader Bot!\n\n"
        "Available commands:\n"
        "• /dl_album [url] - Download complete album in ALAC format\n"
        "• /dl_select [url] - Download selected tracks from an album\n"
        "• /status - Check your request status\n"
        "• /cancel [id] - Cancel a download request\n"
        "• /help - Show this help message"
    )

@filters.command("help")
async def help_command(client: Client, message: Message):
    """Handle the /help command"""
    await message.reply(
        "📚 **Bot Commands**\n\n"
        "• /dl_album [url] - Download complete album in ALAC format\n"
        "Example: `/dl_album https://music.apple.com/in/album/album-name/1234567890`\n\n"
        "• /dl_select [url] - Download selected tracks from an album\n"
        "Example: `/dl_select https://music.apple.com/in/album/album-name/1234567890`\n\n"
        "• /status - Check your current download requests\n\n"
        "• /cancel [id] - Cancel a download request\n"
        "Example: `/cancel 42`\n\n"
        "• /help - Show this help message"
    )

@filters.command("dl_album")
async def dl_album_command(client: Client, message: Message):
    """Handle the /dl_album command"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Check command format
    if len(message.command) < 2:
        await message.reply("Please provide an Apple Music album URL.\nExample: `/dl_album https://music.apple.com/album/xyz/123456789`")
        return
    
    url = message.command[1]
    
    # Validate URL (basic check)
    if not url.startswith("https://music.apple.com/") or "album" not in url:
        await message.reply("Please provide a valid Apple Music album URL.")
        return
    
    # Add request to database
    request_id = add_download_request(
        chat_id=chat_id,
        user_id=user_id,
        url=url,
        download_type="album"
    )
    
    # Inform user
    await message.reply(
        f"✅ Your album download request has been queued!\n"
        f"Request ID: `{request_id}`\n\n"
        f"You will be notified when your download is ready."
    )
    
    # Trigger queue processing
    asyncio.create_task(process_queue(client))

@filters.command("dl_select")
async def dl_select_command(client: Client, message: Message):
    """Handle the /dl_select command for downloading selected tracks"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Check command format
    if len(message.command) < 2:
        await message.reply("Please provide an Apple Music album URL.\nExample: `/dl_select https://music.apple.com/album/xyz/123456789`")
        return
    
    url = message.command[1]
    
    # Validate URL (basic check)
    if not url.startswith("https://music.apple.com/") or "album" not in url:
        await message.reply("Please provide a valid Apple Music album URL.")
        return
    
    # Check if user already has a track selection request pending
    if user_id in waiting_for_tracks:
        await message.reply("You already have a pending track selection. Please complete that first or wait for it to time out.")
        return
    
    # Start the track listing process
    status_message = await message.reply("🔍 Fetching album tracks... Please wait.")
    
    # Store user information and start timeout
    waiting_for_tracks[user_id] = {
        "url": url,
        "chat_id": chat_id,
        "message_id": status_message.id,
        "original_message_id": message.id
    }
    
    # Start the track selection process
    asyncio.create_task(get_track_listing(client, url, chat_id, user_id, status_message.id))

async def get_track_listing(client, url, chat_id, user_id, message_id):
    """Get track listing from the URL and ask user to select tracks"""
    from services.download_service import get_album_track_listing
    
    try:
        # Get album tracks
        album_info = await get_album_track_listing(url)
        
        # Format track listing message
        tracks_text = "📋 **Track Listing**\n\n"
        tracks_text += f"**Album:** {album_info['album_title']}\n"
        tracks_text += f"**Artist:** {album_info['artist']}\n\n"
        
        for idx, track in enumerate(album_info['tracks']):
            tracks_text += f"`{idx+1}`. {track}\n"
        
        tracks_text += "\n⚠️ **Reply to this message with track numbers separated by commas**\n"
        tracks_text += "Example: `1,3,5` to download tracks 1, 3, and 5\n"
        tracks_text += f"You have {COMMAND_TIMEOUT} seconds to respond."
        
        # Update the message with track listing
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=tracks_text
        )
        
        # Start timeout task
        asyncio.create_task(handle_track_selection_timeout(client, user_id, chat_id, message_id))
        
    except Exception as e:
        # Handle error
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"❌ Error fetching album tracks: {str(e)}"
        )
        # Clean up
        if user_id in waiting_for_tracks:
            del waiting_for_tracks[user_id]

async def handle_track_selection_timeout(client, user_id, chat_id, message_id):
    """Handle timeout for track selection"""
    await asyncio.sleep(COMMAND_TIMEOUT)
    
    # Check if user still hasn't responded
    if user_id in waiting_for_tracks:
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏱️ Track selection timed out. Please try again with `/dl_select` command."
        )
        del waiting_for_tracks[user_id]

@filters.command("status")
async def status_command(client: Client, message: Message):
    """Handle the /status command"""
    user_id = message.from_user.id
    
    # Get user's active requests
    requests = get_user_active_requests(user_id)
    
    if not requests:
        await message.reply("You don't have any active download requests.")
        return
    
    status_text = "📊 **Your Download Requests**\n\n"
    
    for req in requests:
        status_emoji = {
            "queued": "🔄",
            "processing": "⚙️",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🚫"
        }.get(req.status, "❓")
        
        status_text += (
            f"**ID:** `{req.id}`\n"
            f"**Status:** {status_emoji} {req.status.title()}\n"
            f"**Type:** {'Full Album' if req.download_type == 'album' else 'Selected Tracks'}\n"
            f"**Requested:** {req.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        if req.gofile_url:
            status_text += f"**Download Link:** {req.gofile_url}\n"
        
        if req.error_message:
            status_text += f"**Error:** {req.error_message}\n"
        
        status_text += "\n" + "─" * 30 + "\n\n"
    
    status_text += "To cancel a request, use `/cancel [id]`"
    
    await message.reply(status_text)

@filters.command("cancel")
async def cancel_command(client: Client, message: Message):
    """Handle the /cancel command"""
    user_id = message.from_user.id
    
    # Check command format
    if len(message.command) < 2:
        await message.reply("Please provide a request ID to cancel.\nExample: `/cancel 42`")
        return
    
    try:
        request_id = int(message.command[1])
    except ValueError:
        await message.reply("Invalid request ID. Please provide a valid number.")
        return
    
    # Get request info
    request = get_request_by_id(request_id)
    
    if not request:
        await message.reply(f"Request with ID {request_id} not found.")
        return
    
    # Check if user owns this request
    if request.user_id != user_id:
        await message.reply("You can only cancel your own requests.")
        return
    
    # Check if request can be cancelled
    if request.status not in ["queued", "processing"]:
        await message.reply(f"Request with status '{request.status}' cannot be cancelled.")
        return
    
    # Cancel the request
    if cancel_request(request_id):
        await message.reply(f"✅ Request with ID {request_id} has been cancelled.")
    else:
        await message.reply(f"❌ Failed to cancel request with ID {request_id}.")