import asyncio
import os
import subprocess
import tempfile
import shutil
import datetime
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.db_handler import (
    add_download_request,
    get_user_active_requests,
    cancel_request,
    get_request_by_id,
    update_request_status
)
from services.download_service import get_album_track_listing  # Import the function if needed
from config import COMMAND_TIMEOUT, DOWNLOAD_DIR
from services.gofile_service import upload_to_gofile  # Import GoFile upload
from services.zip_service import zip_album_folder  # Import zip service

# Note: The interactive waiting-for-track-selection functionality has been removed.

async def start_command(client: Client, message: Message):
    """Handle the /start command"""
    await message.reply(
        "👋 Welcome to Apple Music Downloader Bot!\n\n"
        "Available commands:\n"
        "• /dl_album [url] - Download complete album in ALAC format\n"
        "• /dl_select [url] [track_numbers] - Download selected tracks from an album\n"
        "   Example: `/dl_select https://music.apple.com/in/album/tu-jaane-na/1537029617 3,5,11`\n"
        "• /status - Check your request status\n"
        "• /cancel [id] - Cancel a download request\n"
        "• /help - Show this help message"
    )

async def help_command(client: Client, message: Message):
    """Handle the /help command"""
    await message.reply(
        "📚 **Bot Commands**\n\n"
        "• /dl_album [url] - Download complete album in ALAC format\n"
        "   Example: `/dl_album https://music.apple.com/in/album/album-name/1234567890`\n\n"
        "• /dl_select [url] [track_numbers] - Download selected tracks from an album\n"
        "   Example: `/dl_select https://music.apple.com/in/album/tu-jaane-na/1537029617 3,5,11`\n\n"
        "• /status - Check your current download requests\n\n"
        "• /cancel [id] - Cancel a download request\n"
        "   Example: `/cancel 42`\n\n"
        "• /help - Show this help message"
    )

async def dl_album_command(client: Client, message: Message):
    """Handle the /dl_album command"""
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Check command format
    if len(message.command) < 2:
        await message.reply("❌ Please provide an Apple Music album URL.\nExample: `/dl_album https://music.apple.com/album/xyz/123456789`")
        return

    url = message.command[1]

    # Validate URL (basic check)
    if not url.startswith("https://music.apple.com/") or "album" not in url:
        await message.reply("❌ Please provide a valid Apple Music album URL.")
        return

    # Add request to database (download type "album")
    request_id = add_download_request(
        chat_id=chat_id,
        user_id=user_id,
        url=url,
        download_type="album"
    )

    await message.reply(
        f"✅ Your album download request has been queued!\nRequest ID: `{request_id}`\n\nPlease wait while we process your request. 🚀"
    )

    # Trigger processing for this request (using the request ID)
    asyncio.create_task(process_download(client, request_id))

async def dl_select_command(client: Client, message: Message):
    """Handle the /dl_select command for downloading selected tracks"""
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Expect at least the URL and track numbers
    if len(message.command) < 3:
        await message.reply("❌ Please provide both an Apple Music album URL and track numbers.\nExample: `/dl_select https://music.apple.com/in/album/tu-jaane-na/1537029617 3,5,11`")
        return

    url = message.command[1]
    # Combine all remaining arguments (in case there are spaces) and remove spaces
    tracks = "".join(message.command[2:]).replace(" ", "")

    # Validate URL
    if not url.startswith("https://music.apple.com/") or "album" not in url:
        await message.reply("❌ Please provide a valid Apple Music album URL.")
        return

    # Validate track numbers format (only digits and commas allowed)
    if not re.match(r'^[0-9,]+$', tracks):
        await message.reply("❌ Invalid track numbers format. Please provide numbers separated by commas. Example: `3,5,11`")
        return

    # Add request to database with download type "select"
    request_id = add_download_request(
        chat_id=chat_id,
        user_id=user_id,
        url=url,
        download_type="select",
        tracks=tracks
    )

    await message.reply(
        f"✅ Your track selection request has been queued!\nSelected tracks: {tracks}\nRequest ID: `{request_id}`\n\nPlease wait while we process your request. 🚀"
    )

    # Trigger queue processing
    from services.download_service import process_queue
    asyncio.create_task(process_queue(client))

async def status_command(client: Client, message: Message):
    """Handle the /status command"""
    user_id = message.from_user.id

    # Get user's active requests
    requests = get_user_active_requests(user_id)

    if not requests:
        await message.reply("ℹ️ You don't have any active download requests.")
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

async def cancel_command(client: Client, message: Message):
    """Handle the /cancel command"""
    user_id = message.from_user.id

    if len(message.command) < 2:
        await message.reply("❌ Please provide a request ID to cancel.\nExample: `/cancel 42`")
        return

    try:
        request_id = int(message.command[1])
    except ValueError:
        await message.reply("❌ Invalid request ID. Please provide a valid number.")
        return

    request = get_request_by_id(request_id)
    if not request:
        await message.reply(f"❌ Request with ID {request_id} not found.")
        return

    if request.user_id != user_id:
        await message.reply("❌ You can only cancel your own requests.")
        return

    if request.status not in ["queued", "processing"]:
        await message.reply(f"❌ Request with status '{request.status}' cannot be cancelled.")
        return

    if cancel_request(request_id):
        await message.reply(f"✅ Request with ID {request_id} has been cancelled.")
    else:
        await message.reply(f"❌ Failed to cancel request with ID {request_id}.")

# Note: The interactive track selection functions have been removed as /dl_select now uses direct parameters.
