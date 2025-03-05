import asyncio
import subprocess
import os
import tempfile
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
# Active downloads tracker
active_downloads = set()

async def process_queue(client):
    """Process the download queue"""
    async with queue_lock:
        # Check if we can process more downloads
        active_count = get_active_processing_count()
        if active_count >= MAX_CONCURRENT_DOWNLOADS:
            return
        
        # Get queued requests
        queued_requests = get_requests_in_queue()
        if not queued_requests:
            return
        
        # Process as many requests as we can within the limit
        available_slots = MAX_CONCURRENT_DOWNLOADS - active_count
        requests_to_process = queued_requests[:available_slots]
        
        for request in requests_to_process:
            # Start download task for each request
            asyncio.create_task(process_request(client, request))

async def process_request(client, request):
    """Process a single download request"""
    request_id = request.id
    chat_id = request.chat_id
    url = request.url
    
    try:
        # Update request status
        update_request_status(request_id, "processing")
        
        # Send status message
        status_msg = await client.send_message(
            chat_id=chat_id,
            text=f"⚙️ Processing your request (ID: {request_id})...\n"
                 f"Downloading {'album' if request.download_type == 'album' else 'selected tracks'}..."
        )
        
        # Create a unique download directory for this request
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        request_download_dir = os.path.join(
            DOWNLOAD_DIR, 
            f"request_{request_id}_{timestamp}"
        )
        ensure_directory_exists(request_download_dir)
        
        # Download the music
        if request.download_type == "album":
            await download_full_album(url, request_download_dir)
        else:  # select
            await download_selected_tracks(url, request.tracks, request_download_dir)
        
        # Find the album directory where files were downloaded
        album_folder = await find_latest_album_folder(request_download_dir)
        
        # Update status message
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"📦 Download completed for request {request_id}. Zipping files..."
        )
        
        # Zip the album folder
        zip_path = await zip_album_folder(album_folder)
        
        # Update status message
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"☁️ Uploading to GoFile for request {request_id}..."
        )
        
        # Upload to GoFile
        gofile_url = await upload_to_gofile(zip_path)
        
        # Update request in database
        update_request_status(
            request_id, 
            "completed", 
            download_path=album_folder,
            gofile_url=gofile_url
        )
        
        # Send completion message
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"✅ Download complete for request {request_id}!\n\n"
                 f"📥 Download link: {gofile_url}\n\n"
                 f"This link will expire after some time, so please download it soon."
        )
        
        # Clean up
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(request_download_dir):
                shutil.rmtree(request_download_dir)
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
    except Exception as e:
        # Handle errors
        error_message = str(e)
        print(f"Error processing request {request_id}: {error_message}")
        
        # Update request status
        update_request_status(request_id, "failed", error_message=error_message)
        
        # Notify user
        try:
            await client.send_message(
                chat_id=chat_id,
                text=f"❌ Error processing request {request_id}: {error_message}"
            )
        except Exception:
            pass
    
    finally:
        # Trigger queue processing again
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
    # First run with --select to get track listing
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

async def get_album_track_listing(url):
    """Get track listing for an album"""
    cmd = ['go', 'run', 'main.go', '--info', url]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd='apple-music-alac-atmos-downloader',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"Failed to get album info: {stderr.decode()}")
    
    output = stdout.decode()
    
    # Parse the output to extract album information
    album_info = {}
    
    # Extract artist and album title
    album_lines = [line for line in output.split('\n') if line.strip()]
    if len(album_lines) >= 2:
        album_info['artist'] = album_lines[0].strip()
        album_info['album_title'] = album_lines[1].strip()
    else:
        album_info['artist'] = "Unknown Artist"
        album_info['album_title'] = "Unknown Album"
    
    # Extract tracks
    track_lines = []
    in_track_section = False
    for line in output.split('\n'):
        if '+---+' in line and not in_track_section:
            in_track_section = True
            continue
        if '+---+' in line and in_track_section:
            break
        if in_track_section and '|' in line:
            parts = line.split('|')
            if len(parts) > 2 and parts[1].strip() and parts[1].strip().isdigit():
                track_num = parts[1].strip()
                track_name = parts[2].strip()
                track_lines.append(f"{track_name}")
    
    album_info['tracks'] = track_lines
    
    return album_info