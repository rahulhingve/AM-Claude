import os
import shutil
import tempfile
import asyncio

async def zip_album_folder(album_folder):
    """Zip an album folder and return the path to the zip file"""
    # Get album name for the zip file
    album_name = os.path.basename(album_folder)
    
    # Create temporary directory if it doesn't exist
    temp_dir = tempfile.gettempdir()
    os.makedirs(temp_dir, exist_ok=True)
    
    # Define zip file path
    zip_file_base = os.path.join(temp_dir, f"{album_name}")
    zip_file_path = f"{zip_file_base}.zip"
    
    # Remove existing zip file if it exists
    if os.path.exists(zip_file_path):
        os.remove(zip_file_path)
    
    # Zip the album folder
    def make_archive():
        return shutil.make_archive(
            base_name=zip_file_base,
            format='zip',
            root_dir=os.path.dirname(album_folder),
            base_dir=os.path.basename(album_folder)
        )
    
    # Run zip operation in a thread pool to avoid blocking
    zip_file = await asyncio.to_thread(make_archive)
    
    return zip_file