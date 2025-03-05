import os
import shutil
import tempfile
import asyncio

async def zip_album_folder(album_folder):
    """Zip an album folder and return the path to the zip file."""
    album_name = os.path.basename(album_folder)
    temp_dir = tempfile.gettempdir()
    os.makedirs(temp_dir, exist_ok=True)
    zip_file_base = os.path.join(temp_dir, f"{album_name}")
    zip_file_path = f"{zip_file_base}.zip"
    if os.path.exists(zip_file_path):
        os.remove(zip_file_path)
    def make_archive():
        return shutil.make_archive(
            base_name=zip_file_base,
            format='zip',
            root_dir=os.path.dirname(album_folder),
            base_dir=os.path.basename(album_folder)
        )
    zip_file = await asyncio.to_thread(make_archive)
    return zip_file
