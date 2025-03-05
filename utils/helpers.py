import os
import glob

def ensure_directory_exists(directory):
    """Ensure that a directory exists, creating it if necessary"""
    os.makedirs(directory, exist_ok=True)

async def find_latest_album_folder(download_dir):
    """Find the most recently created album folder in the download directory"""
    # Check if directory exists
    if not os.path.exists(download_dir):
        raise Exception(f"Download directory {download_dir} does not exist")
    
    # Look for artist directories
    artist_folders = []
    for item in os.listdir(download_dir):
        item_path = os.path.join(download_dir, item)
        if os.path.isdir(item_path):
            artist_folders.append(item_path)
    
    if not artist_folders:
        raise Exception(f"No artist folders found in {download_dir}")
    
    # Find latest artist folder
    latest_artist_folder = max(artist_folders, key=os.path.getctime)
    
    # Find album folders within
    album_folders = [
        os.path.join(latest_artist_folder, album) 
        for album in os.listdir(latest_artist_folder) 
        if os.path.isdir(os.path.join(latest_artist_folder, album))
    ]
    
    if not album_folders:
        raise Exception(f"No album folders found in {latest_artist_folder}")
    
    # Return latest album folder
    return max(album_folders, key=os.path.getctime)

def get_latest_created_folder(base_path):
    """Get the most recently created folder in a given path"""
    folders = [
        os.path.join(base_path, d) 
        for d in os.listdir(base_path) 
        if os.path.isdir(os.path.join(base_path, d))
    ]
    
    if not folders:
        return None
    
    return max(folders, key=os.path.getctime)