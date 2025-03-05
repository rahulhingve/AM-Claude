import asyncio
import subprocess
import re

async def upload_to_gofile(file_path):
    """Upload a file to GoFile and return the download URL."""
    process = await asyncio.create_subprocess_exec(
        'gofilepy', file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"GoFile upload failed: {stderr.decode()}")
    output = stdout.decode()
    download_url_match = re.search(r"Download page: (https://gofile\.io/\S+)", output)
    if download_url_match:
        return download_url_match.group(1)
    else:
        raise Exception("Failed to extract GoFile download URL from output")
