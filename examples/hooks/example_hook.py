"""
Example UpaPasta Hook

To use this:
1. Copy this file to ~/.config/upapasta/hooks/
2. Make sure it ends in .py
3. UpaPasta will automatically load and run it after every upload.
"""

from typing import Any


def on_upload_complete(metadata: dict[str, Any]) -> None:
    """
    This function is called by UpaPasta after a successful upload.
    
    metadata dictionary contains:
        - original_name (str): Original file/folder name
        - obfuscated_name (str | None): Random subject name if obfuscated
        - nzb_path (str | None): Absolute path to the .nzb file
        - nfo_path (str | None): Absolute path to the .nfo file
        - password (str | None): Archive password if set
        - size_bytes (int | None): Total upload size in bytes
        - usenet_group (str | None): The Usenet group used
        - category (str): Detected category (Movie, TV, Anime, Generic)
        - tmdb_id (int | None): TMDb ID if found
        - compressor (str | None): 'rar', '7z' or None
    """
    name = metadata.get("original_name")
    group = metadata.get("usenet_group")
    
    print(f"Hook log: Finished uploading '{name}' to {group}!")
    
    # You can add logic here to:
    # - Notify a custom API
    # - Move the NZB to a specific watch folder
    # - Update a local database
    # - Trigger a media manager scan (like Sonarr/Radarr)
