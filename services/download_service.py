import asyncio
import os
import shutil
from datetime import datetime

from config import DOWNLOAD_DIR, MAX_CONCURRENT_DOWNLOADS
from database.db_handler import (
    get_requests_in_queue,
    update_request_status,
    get_active_processing_count
)
from services.zip_service import zip_album_folder
from services.gofile_service import upload_to_gofile
from utils.helpers import ensure_directory_exists, find_album_folder_with_m4a

# Lock for queue processing
queue_lock = asyncio.Lock()

async def process_queue(client):
    """Process the download queue sequentially."""
    async with queue_lock:
        active_count = get_active_processing_count()
        if active_count >= MAX_CONCURRENT_DOWNLOADS:
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
            text=f"⚙️ Processing your request (ID: {request_id})...\nDownloading {'full album' if request.download_type == 'album' else 'selected tracks'}..."
        )
        
        # Ensure the DOWNLOAD_DIR exists and use it directly.
        ensure_directory_exists(DOWNLOAD_DIR)
        
        if request.download_type == "album":
            await download_full_album(url, DOWNLOAD_DIR)
        else:  # "select"
            await download_selected_tracks(url, request.tracks, DOWNLOAD_DIR)
        
        # Search within DOWNLOAD_DIR for the album folder containing .m4a files.
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
        
        # Cleanup: Delete the entire DOWNLOAD_DIR and then recreate it.
        if os.path.exists(DOWNLOAD_DIR):
            shutil.rmtree(DOWNLOAD_DIR)
            ensure_directory_exists(DOWNLOAD_DIR)
        
        # Also remove the zip file if it still exists.
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

async def download_full_album(url, download_dir):
    """Download a full album using the external Go downloader."""
    cmd = ['go', 'run', 'main.go', url]
    env = os.environ.copy()
    env['AM_DL_DIR'] = download_dir
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd='apple-music-alac-atmos-downloader',
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"Download failed: {stderr.decode()}")
    return True

async def download_selected_tracks(url, tracks, download_dir):
    """Download selected tracks from an album using the external Go downloader with --select flag."""
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
    tracks_input = f"{tracks}\n".encode()
    stdout, stderr = await process.communicate(input=tracks_input)
    if process.returncode != 0:
        raise Exception(f"Download failed: {stderr.decode()}")
    return True
