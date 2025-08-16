#!/usr/bin/env python3
"""
Simple Rekordbox → USB Export Script
Copies all non-smart playlists and their tracks exactly as they are in Rekordbox.
"""

import os
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import Dict, List, Tuple

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    exit(1)


def normalize_rekordbox_path(folder: str, filename: str) -> Path:
    """Convert Rekordbox paths (may have file:// URLs and percent-encoding) to absolute paths."""
    folder = (folder or "").strip()
    filename = (filename or "").strip()
    
    if not filename:
        return None
    
    # Decode URL-encodings in filename
    filename = unquote(filename)
    
    # Handle file:// URL in folder
    if folder.startswith("file://"):
        parsed = urlparse(folder)
        path_str = parsed.path or folder[len("file://"):]
        folder_path = unquote(path_str)
    else:
        folder_path = unquote(folder) if folder else ""
    
    # Construct full path using EXACT Rekordbox paths (anywhere on computer)
    if folder_path:
        # Ensure proper path separator
        if folder_path and not folder_path.endswith("/"):
            folder_path += "/"
        full_path = folder_path + filename
    else:
        # If no folder path, filename might be absolute or relative
        full_path = filename
    
    try:
        return Path(full_path).resolve()
    except Exception:
        return Path(full_path)


def get_all_playlists(rb):
    """Get all actual playlists (not folders) from Rekordbox database."""
    playlists = []
    
    # Get all playlists using the correct API
    all_playlists = rb.get_playlist().all()
    
    for playlist in all_playlists:
        # Test if this is an actual playlist with tracks (not a folder)
        try:
            # Try to get contents - this will fail for folders
            track_count = len(rb.get_playlist_contents(playlist.ID).all())
            is_actual_playlist = True
        except ValueError as e:
            # This is a folder, skip it
            if "playlist folder" in str(e):
                is_actual_playlist = False
            else:
                # Some other error, treat as empty playlist
                is_actual_playlist = True
                track_count = 0
        except Exception:
            # Any other error, treat as empty playlist
            is_actual_playlist = True
            track_count = 0
            
        if not is_actual_playlist:
            continue
            
        folder_path = []
        parent_id = getattr(playlist, 'ParentID', None)
        
        # Build folder hierarchy
        while parent_id and parent_id != 0:
            parent_playlists = [p for p in all_playlists if getattr(p, 'ID', None) == parent_id]
            if parent_playlists:
                parent = parent_playlists[0]
                folder_path.insert(0, parent.Name)
                parent_id = getattr(parent, 'ParentID', None)
            else:
                break
        
        playlists.append({
            'id': playlist.ID,
            'name': playlist.Name,
            'folder_path': folder_path,
            'full_path': '/'.join(folder_path + [playlist.Name]) if folder_path else playlist.Name,
            'track_count': track_count
        })
    
    return playlists


def get_playlist_tracks(rb, playlist_id: int) -> List[Tuple[str, Path]]:
    """Get all tracks in a playlist with their source file paths."""
    tracks = []
    
    try:
        # Get tracks using the correct API
        playlist_songs = rb.get_playlist_contents(playlist_id).all()
        
        for song in playlist_songs:
            title = song.Title or (song.FileNameL or song.FileNameS or "Unknown")
            source_path = normalize_rekordbox_path(
                song.FolderPath or "", 
                song.FileNameL or song.FileNameS or ""
            )
            tracks.append((title, source_path))
    except Exception as e:
        print(f"  ✗ Error getting tracks for playlist {playlist_id}: {e}")
    
    return tracks


def copy_file_preserving_structure(source: Path, usb_music_dir: Path, base_music_dir: Path) -> Path:
    """Copy a file to USB, preserving its relative path structure."""
    try:
        # Try to get relative path from base music directory
        try:
            rel_path = source.relative_to(base_music_dir)
        except ValueError:
            # If file is outside base directory, use just the filename
            rel_path = source.name
        
        dest_path = usb_music_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not dest_path.exists():
            shutil.copy2(source, dest_path)
            print(f"  ✓ Copied: {source.name}")
        else:
            print(f"  - Exists: {source.name}")
        
        return dest_path
    except Exception as e:
        print(f"  ✗ Error copying {source}: {e}")
        return None


def create_m3u8_playlist(playlist_name: str, tracks: List[Tuple[str, Path]], usb_playlists_dir: Path, usb_music_dir: Path):
    """Create an M3U8 playlist file on the USB."""
    playlist_path = usb_playlists_dir / f"{playlist_name}.m3u8"
    playlist_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(playlist_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for title, track_path in tracks:
            if track_path and track_path.exists():
                # Write relative path from playlist to music file
                try:
                    rel_path = os.path.relpath(track_path, playlist_path.parent)
                    f.write(f"#EXTINF:-1,{title}\n")
                    f.write(f"{rel_path}\n")
                except Exception:
                    print(f"  ✗ Error writing playlist entry for {title}")


def main():
    # Configuration
    USB_PATH = "/Volumes/DJYING"
    BASE_MUSIC_DIR = Path("/Users/ethansarif-kattan/Music/ALLDJ")
    
    usb_path = Path(USB_PATH)
    usb_music_dir = usb_path / "ALLDJ_MUSIC"
    usb_playlists_dir = usb_path / "PLAYLISTS"
    
    # Verify USB is connected
    if not usb_path.exists():
        print(f"❌ USB not found at {USB_PATH}")
        return
    
    # Find Rekordbox database directory
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6", 
        Path.home() / "Library/Pioneer/rekordbox"
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if db_path is None:
        print("❌ No Rekordbox database directory found")
        return
    
    print(f"📁 Using Rekordbox database: {db_path}")
    
    # Create USB directories
    usb_music_dir.mkdir(exist_ok=True)
    usb_playlists_dir.mkdir(exist_ok=True)
    
    print(f"🎚️  Exporting Rekordbox playlists to {USB_PATH}")
    print("=" * 50)
    
    # Connect to Rekordbox database
    rb = Rekordbox6Database(db_dir=str(db_path))
    
    try:
        # Get all playlists
        playlists = get_all_playlists(rb)
        print(f"Found {len(playlists)} playlists")
        
        for i, playlist in enumerate(playlists, 1):
            print(f"\n[{i}/{len(playlists)}] {playlist['full_path']}")
            print(f"  {playlist['track_count']} tracks")
            
            if playlist['track_count'] == 0:
                print("  (empty playlist, skipping)")
                continue
            
            # Get tracks for this playlist
            tracks = get_playlist_tracks(rb, playlist['id'])
            
            if not tracks:
                print("  (no tracks retrieved, skipping)")
                continue
            
            # Copy all tracks
            copied_tracks = []
            for title, source_path in tracks:
                if source_path.exists():
                    dest_path = copy_file_preserving_structure(source_path, usb_music_dir, BASE_MUSIC_DIR)
                    if dest_path:
                        copied_tracks.append((title, dest_path))
                else:
                    print(f"  ✗ Missing: {source_path}")
            
            # Create M3U8 playlist
            if copied_tracks:
                # Create folder structure for playlist if needed
                if playlist['folder_path']:
                    playlist_folder = usb_playlists_dir
                    for folder in playlist['folder_path']:
                        playlist_folder = playlist_folder / folder
                    playlist_folder.mkdir(parents=True, exist_ok=True)
                    playlist_file_path = playlist_folder / f"{playlist['name']}.m3u8"
                else:
                    playlist_file_path = usb_playlists_dir / f"{playlist['name']}.m3u8"
                
                # Write M3U8 file
                with open(playlist_file_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    for title, track_path in copied_tracks:
                        try:
                            rel_path = os.path.relpath(track_path, playlist_file_path.parent)
                            f.write(f"#EXTINF:-1,{title}\n")
                            f.write(f"{rel_path}\n")
                        except Exception as e:
                            print(f"  ✗ Error writing playlist entry: {e}")
                
                print(f"  ✓ Created playlist: {playlist_file_path.name}")
    
    finally:
        rb.close()
    
    # Final summary
    total_files = sum(1 for _ in usb_music_dir.rglob('*') if _.is_file())
    total_playlists = sum(1 for _ in usb_playlists_dir.rglob('*.m3u8'))
    
    print("\n" + "=" * 50)
    print(f"✅ Export complete!")
    print(f"📁 {total_files} music files copied")
    print(f"🎵 {total_playlists} playlists created")
    print(f"📍 Music: {usb_music_dir}")
    print(f"📍 Playlists: {usb_playlists_dir}")


if __name__ == "__main__":
    main()
