import os

def ensure_directory_exists(directory):
    """Ensure that a directory exists, creating it if necessary."""
    os.makedirs(directory, exist_ok=True)

def find_album_folder_with_m4a(base_path):
    """
    Recursively search for a folder within base_path that contains at least one .m4a file.
    Returns the path of the folder if found; otherwise, raises an Exception.
    """
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith('.m4a'):
                return root
    raise Exception(f"No folder containing .m4a files found in {base_path}")
