import asyncio
import os
import shutil
from datetime import datetime

from config import DOWNLOAD_DIR, MAX_CONCURRENT_DOWNLOADS
from database.db_handler import get_requests_in_queue, update_request_status, get_active_processing_count
from services.zip_service import zip_album_folder
from services.gofile_service import upload_to_gofile
from utils.helpers import ensure_directory_exists, find_album_folder_with_m4a

# Lock to ensure only one queue loop runs at a time.
queue_lock = asyncio.Lock()

async def process_queue(client):
    """Continuously process queued requests sequentially."""
    while True:
        async with queue_lock:
            if get_active_processing_count() >= MAX_CONCURRENT_DOWNLOADS:
                return
            queued_requests = get_requests_in_queue()
            if not queued_requests:
                return
            request = queued_requests[0]
        await process_request(client, request)

async def process_request(client, request):
    """Process a single download request."""
    request_id = request.id
    chat_id = request.chat_id
    url = request.url

    try:
        update_request_status(request_id, "processing")
        status_msg = await client.send_message(
            chat_id=chat_id,
            text=f"⚙️ Processing your request (ID: {request_id})...\nDownloading album..."
        )
        
        # Ensure the DOWNLOAD_DIR exists.
        ensure_directory_exists(DOWNLOAD_DIR)
        
        # Always use the "--select" mode; pass track argument via stdin.
        # If no specific tracks were given, default to "all".
        track_arg = request.tracks if request.tracks is not None else "all"
        await download_album(url, track_arg, DOWNLOAD_DIR)
        
        # Find the album folder within DOWNLOAD_DIR that contains .m4a files.
        album_folder = await asyncio.to_thread(find_album_folder_with_m4a, DOWNLOAD_DIR)
        
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"📦 Download completed for request {request_id}.\nZipping folder: {album_folder}..."
        )
        
        zip_path = await zip_album_folder(album_folder)
        
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"☁️ Uploading your zipped album for request {request_id}..."
        )
        
        gofile_url = await upload_to_gofile(zip_path)
        
        update_request_status(
            request_id, 
            "completed", 
            download_path=album_folder,
            gofile_url=gofile_url
        )
        
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"✅ Download complete for request {request_id}!\n\n📥 Download link: {gofile_url}\n\nPlease download your album as the link will expire soon. ⏳"
        )
        
        # Cleanup: Delete the entire DOWNLOAD_DIR and recreate it.
        if os.path.exists(DOWNLOAD_DIR):
            shutil.rmtree(DOWNLOAD_DIR)
            ensure_directory_exists(DOWNLOAD_DIR)
        
        # Remove the temporary zip file.
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
    except Exception as e:
        error_message = str(e)
        print(f"Error processing request {request_id}: {error_message}")
        update_request_status(request_id, "failed", error_message=error_message)
        try:
            await client.send_message(
                chat_id=chat_id,
                text=f"❌ Error processing request {request_id}: {error_message}"
            )
        except Exception:
            pass
    finally:
        await process_queue(client)

async def download_album(url, track_argument, download_dir):
    """
    Download an album using the external Go downloader in '--select' mode.
    The track_argument (e.g. "all" or "2,3,5") is sent via stdin.
    """
    cmd = ['go', 'run', 'main.go', '--select', url]
    env = os.environ.copy()
    env['AM_DL_DIR'] = download_dir
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd='apple-music-alac-atmos-downloader',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    input_str = f"{track_argument}\n".encode()
    stdout, stderr = await process.communicate(input=input_str)
    if process.returncode != 0:
        raise Exception(f"Download failed: {stderr.decode()}")
    return True
