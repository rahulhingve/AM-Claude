import asyncio
import subprocess
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
from utils.helpers import find_latest_album_folder, ensure_directory_exists

# Lock for queue processing
queue_lock = asyncio.Lock()

async def process_queue(client):
    """Process the download queue"""
    async with queue_lock:
        # Check active processing count
        active_count = get_active_processing_count()
        if active_count >= MAX_CONCURRENT_DOWNLOADS:
            return
        
        # Get queued requests
        queued_requests = get_requests_in_queue()
        if not queued_requests:
            return
        
        # Process one request (due to MAX_CONCURRENT_DOWNLOADS = 1)
        request = queued_requests[0]
        asyncio.create_task(process_request(client, request))

async def process_request(client, request):
    """Process a single download request"""
    request_id = request.id
    chat_id = request.chat_id
    url = request.url
    
    try:
        # Update status
        update_request_status(request_id, "processing")
        
        # Send initial message
        status_msg = await client.send_message(
            chat_id=chat_id,
            text=f"⚙️ Starting request ID `{request_id}`...\n"
                 f"🎵 Downloading {'full album' if request.download_type == 'album' else 'selected tracks'}..."
        )
        
        # Create unique download directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        request_download_dir = os.path.join(
            DOWNLOAD_DIR, 
            f"request_{request_id}_{timestamp}"
        )
        ensure_directory_exists(request_download_dir)
        
        # Download music
        if request.download_type == "album":
            await download_full_album(url, request_download_dir)
        else:  # select
            await download_selected_tracks(url, request.tracks, request_download_dir)
        
        # Find downloaded album folder
        album_folder = await find_latest_album_folder(request_download_dir)
        
        # Update status
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"📦 Download done for request ID `{request_id}`!\n"
                 f"🤐 Zipping files now..."
        )
        
        # Zip files
        zip_path = await zip_album_folder(album_folder)
        
        # Update status
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"☁️ Zipping done for request ID `{request_id}`!\n"
                 f"📤 Uploading to GoFile..."
        )
        
        # Upload to GoFile
        gofile_url = await upload_to_gofile(zip_path)
        
        # Update database
        update_request_status(
            request_id, 
            "completed", 
            download_path=album_folder,
            gofile_url=gofile_url
        )
        
        # Send final message
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"✅ Request ID `{request_id}` completed!\n"
                 f"📥 Download link: {gofile_url}\n\n"
                 f"⏳ Link expires soon—grab it quick!"
        )
        
        # Clean up entire DOWNLOAD_DIR
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(DOWNLOAD_DIR):
                shutil.rmtree(DOWNLOAD_DIR)
        except Exception as e:
            print(f"Cleanup error: {e}")
        
    except Exception as e:
        error_message = str(e)
        print(f"Error processing request {request_id}: {error_message}")
        
        # Update status
        update_request_status(request_id, "failed", error_message=error_message)
        
        # Notify user
        await client.send_message(
            chat_id=chat_id,
            text=f"❌ Request ID `{request_id}` failed!\n"
                 f"Error: {error_message}"
        )
    
    finally:
        # Trigger next in queue
        asyncio.create_task(process_queue(client))

async def download_full_album(url, download_dir):
    """Download a full album"""
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
    """Download selected tracks from an album"""
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
    
    # Send track selection
    tracks_input = f"{tracks}\n".encode()
    stdout, stderr = await process.communicate(input=tracks_input)
    
    if process.returncode != 0:
        raise Exception(f"Download failed: {stderr.decode()}")
    
    return True