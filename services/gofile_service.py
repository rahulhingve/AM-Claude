import asyncio
import re

async def upload_to_gofile(file_path):
    """Upload a file to GoFile and return the download URL."""
    process = await asyncio.create_subprocess_exec(
        'gofilepy', file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    stdout_text = stdout.decode().strip()
    stderr_text = stderr.decode().strip()
    
    if process.returncode != 0:
        raise Exception(f"GoFile upload failed: {stderr_text if stderr_text else stdout_text}")
    
    download_url_match = re.search(r"Download\s*page:\s*(https://gofile\.io/\S+)", stdout_text)
    if download_url_match:
        return download_url_match.group(1)
    else:
        raise Exception("Failed to extract GoFile download URL from output: " + stdout_text)
