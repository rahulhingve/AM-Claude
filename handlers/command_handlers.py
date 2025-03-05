import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from database.db_handler import add_download_request, get_user_active_requests, cancel_request, get_request_by_id, update_request_status
from config import COMMAND_TIMEOUT
from services.download_service import process_queue

async def alac_command(client: Client, message: Message):
    """
    Handle the /alac command.
    Usage: /alac {url} {track_argument}
    Use "all" for a full album download or provide a comma-separated list (e.g., "2,3,5") for selective download.
    """
    chat_id = message.chat.id
    user_id = message.from_user.id

    if len(message.command) < 2:
        await message.reply(
            "❌ Please provide an Apple Music album URL.\n"
            "Example: `/alac https://music.apple.com/in/album/album-name all` or `/alac https://music.apple.com/in/album/album-name 2,3,5`"
        )
        return

    url = message.command[1]
    if not url.startswith("https://music.apple.com/") or "album" not in url:
        await message.reply("❌ Please provide a valid Apple Music album URL.")
        return

    # Default track argument is "all" if not provided.
    track_argument = "all"
    if len(message.command) >= 3:
        track_argument = "".join(message.command[2:]).replace(" ", "")
    
    # Validate track argument format (if not "all")
    if track_argument.lower() != "all" and not re.match(r'^[0-9,]+$', track_argument):
        await message.reply("❌ Invalid track numbers format. Please provide numbers separated by commas (e.g., `2,3,5`) or use `all`.")
        return

    # In this merged mode, we always use the '--select' mode.
    request_id = add_download_request(
        chat_id=chat_id,
        user_id=user_id,
        url=url,
        download_type="select",  # merged command uses one mode
        tracks=track_argument
    )

    await message.reply(
        f"✅ Your album download request has been queued!\nRequest ID: `{request_id}`\n\nPlease wait while we process your request. 🚀"
    )

    asyncio.create_task(process_queue(client))

async def help_command(client: Client, message: Message):
    """Handle the /help command."""
    await message.reply(
        "📚 **Bot Commands**\n\n"
        "• /alac [url] [track_numbers] - Download album in ALAC format.\n"
        "   Use `all` for a full album download or provide specific track numbers separated by commas.\n"
        "   Examples:\n"
        "      `/alac https://music.apple.com/in/album/tu-jaane-na/1537029617 all`\n"
        "      `/alac https://music.apple.com/in/album/tu-jaane-na/1537029617 2,3,5`\n\n"
        "• /status - Check your current download requests.\n"
        "• /cancel [id] - Cancel a download request. Example: `/cancel 42`"
    )

async def status_command(client: Client, message: Message):
    """Handle the /status command."""
    user_id = message.from_user.id
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
            f"**Type:** {'Full Album' if req.tracks.lower()=='all' else 'Selected Tracks'}\n"
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
    """Handle the /cancel command."""
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
