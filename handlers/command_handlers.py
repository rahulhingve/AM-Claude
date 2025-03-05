import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import Message

from database.db_handler import (
    add_download_request,
    get_user_active_requests,
    cancel_request,
    get_request_by_id,
    update_request_status
)
from config import COMMAND_TIMEOUT, DOWNLOAD_DIR
from services.download_service import process_queue

async def start_command(client: Client, message: Message):
    """Handle the /start command"""
    await message.reply(
        "👋 Welcome to Apple Music Downloader Bot!\n\n"
        "Available commands:\n"
        "• `/dl_album [url]` - Download an entire album\n"
        "• `/dl_select [url] [tracks]` - Download specific tracks (e.g., 3,5,11)\n"
        "• `/status` - Check your request status\n"
        "• `/cancel [id]` - Cancel a request\n"
        "• `/help` - Show this help message"
    )

async def help_command(client: Client, message: Message):
    """Handle the /help command"""
    await message.reply(
        "📚 **Bot Commands**\n\n"
        "• `/dl_album [url]` - Download an entire album\n"
        "  Example: `/dl_album https://music.apple.com/in/album/xyz/1234567890`\n\n"
        "• `/dl_select [url] [tracks]` - Download specific tracks\n"
        "  Example: `/dl_select https://music.apple.com/in/album/xyz/1234567890 3,5,11`\n\n"
        "• `/status` - Check your active requests\n\n"
        "• `/cancel [id]` - Cancel a request\n"
        "  Example: `/cancel 42`\n\n"
        "• `/help` - Show this help message"
    )

async def dl_album_command(client: Client, message: Message):
    """Handle the /dl_album command"""
    chat_id = message.chat_id
    user_id = message.from_user.id

    # Check command format
    if len(message.command) < 2:
        await message.reply("⚠️ Please provide an Apple Music album URL.\nExample: `/dl_album https://music.apple.com/in/album/xyz/123456789`")
        return

    url = message.command[1]

    # Validate URL
    if not url.startswith("https://music.apple.com/") or "album" not in url:
        await message.reply("❌ Invalid URL. Please provide a valid Apple Music album URL.")
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
        f"Request ID: `{request_id}`\n"
        f"🎵 We'll download the full album for you.\n\n"
        f"You'll get a link when it's ready!"
    )

    # Trigger queue processing
    asyncio.create_task(process_queue(client))

async def dl_select_command(client: Client, message: Message):
    """Handle the /dl_select command"""
    chat_id = message.chat_id
    user_id = message.from_user.id

    # Check command format
    if len(message.command) != 3:
        await message.reply("⚠️ Please provide an Apple Music album URL and track numbers.\nExample: `/dl_select https://music.apple.com/in/album/xyz/123456789 3,5,11`")
        return

    url = message.command[1]
    tracks = message.command[2]

    # Validate URL
    if not url.startswith("https://music.apple.com/") or "album" not in url:
        await message.reply("❌ Invalid URL. Please provide a valid Apple Music album URL.")
        return

    # Validate tracks format
    if not re.match(r'^[0-9,\s]+$', tracks):
        await message.reply("❌ Invalid track numbers. Use numbers separated by commas, e.g., `3,5,11`.")
        return

    # Clean up tracks
    tracks = ','.join([t.strip() for t in tracks.split(',') if t.strip()])

    # Add request to database
    request_id = add_download_request(
        chat_id=chat_id,
        user_id=user_id,
        url=url,
        download_type="select",
        tracks=tracks
    )

    # Inform user
    await message.reply(
        f"✅ Your track download request has been queued!\n"
        f"Request ID: `{request_id}`\n"
        f"🎵 Tracks: {tracks}\n\n"
        f"You'll get a link when it's ready!"
    )

    # Trigger queue processing
    asyncio.create_task(process_queue(client))

async def status_command(client: Client, message: Message):
    """Handle the /status command"""
    user_id = message.from_user.id

    # Get user's active requests
    requests = get_user_active_requests(user_id)

    if not requests:
        await message.reply("ℹ️ You have no active download requests.")
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
            status_text += f"**Link:** {req.gofile_url}\n"

        if req.error_message:
            status_text += f"**Error:** {req.error_message}\n"

        status_text += "\n" + "─" * 30 + "\n\n"

    status_text += "💡 Use `/cancel [id]` to cancel a request."

    await message.reply(status_text)

async def cancel_command(client: Client, message: Message):
    """Handle the /cancel command"""
    user_id = message.from_user.id

    # Check command format
    if len(message.command) < 2:
        await message.reply("⚠️ Please provide a request ID.\nExample: `/cancel 42`")
        return

    try:
        request_id = int(message.command[1])
    except ValueError:
        await message.reply("❌ Invalid ID. Please provide a number.")
        return

    # Get request info
    request = get_request_by_id(request_id)

    if not request:
        await message.reply(f"❌ Request ID `{request_id}` not found.")
        return

    # Check ownership
    if request.user_id != user_id:
        await message.reply("🚫 You can only cancel your own requests.")
        return

    # Check status
    if request.status not in ["queued", "processing"]:
        await message.reply(f"🚫 Request with status '{request.status}' cannot be cancelled.")
        return

    # Cancel request
    if cancel_request(request_id):
        await message.reply(f"✅ Request ID `{request_id}` cancelled successfully!")
    else:
        await message.reply(f"❌ Failed to cancel request ID `{request_id}`.")