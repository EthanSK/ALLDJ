#!/usr/bin/env python3

"""
Extract FLAC file paths from specific Rekordbox playlists and create a JSON array.
Targets: ALLDJ Bake, ALLDJ Stems, and OG Stems playlists.
"""

import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from pyrekordbox import Rekordbox6Database, db6

def normalize_rb_path(folder: str, name: str) -> Path:
    """Convert Rekordbox DjmdContent folder/name into a local absolute Path."""
    folder = (folder or "").strip()
    name = (name or "").strip()
    name = unquote(name)
    
    if folder.startswith("file://"):
        parsed = urlparse(folder)
        path_str = parsed.path or folder[len("file://"):]
        folder_path = unquote(path_str)
    else:
        folder_path = unquote(folder)
    
    try:
        return Path(folder_path).resolve()
    except Exception:
        return Path(folder_path)

def get_playlist_tracks(db, playlist_id):
    """Get all tracks from a specific playlist"""
    SP = db6.tables.DjmdSongPlaylist
    CT = db6.tables.DjmdContent
    
    tracks = (
        db.session.query(SP, CT)
        .join(CT, CT.ID == SP.ContentID)
        .filter(SP.PlaylistID == playlist_id)
        .all()
    )
    
    return tracks

def map_to_wav_path(flac_path_str):
    """Map a FLAC path to corresponding WAV path"""
    mappings = [
        ("/Volumes/T7 Shield/3000AD/alldj_stem_separated", "/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
        ("/Volumes/T7 Shield/3000AD/og_separated_v2", "/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
        ("/Volumes/T7 Shield/3000AD/flac_liked_songs", "/Volumes/T7 Shield/3000AD/wav_liked_songs"),
    ]
    
    for flac_base, wav_base in mappings:
        if flac_path_str.startswith(flac_base):
            tail = flac_path_str[len(flac_base):]
            wav_candidate = Path(wav_base + tail)
            # Change extension to .wav
            wav_candidate = wav_candidate.with_suffix(".wav")
            return str(wav_candidate)
    
    return None

def collect_tracks_from_folder(db, folder, playlists, track_data):
    """Recursively collect tracks from a folder and its subfolders"""
    # Get children of this folder
    children = [p for p in playlists if getattr(p, 'ParentID', None) == folder.ID]
    
    if not children:
        # This is a leaf playlist - get its tracks
        tracks = get_playlist_tracks(db, folder.ID)
        
        for song_playlist, content in tracks:
            folder_path = getattr(content, 'FolderPath', '') or ''
            file_name = getattr(content, 'FileNameL', '') or getattr(content, 'FileNameS', '') or ''
            
            # Create full path
            full_path = normalize_rb_path(folder_path, file_name)
            flac_path_str = str(full_path)
            
            # Only include FLAC files
            if flac_path_str.lower().endswith('.flac'):
                track_data.append({
                    "flac_path": flac_path_str
                })
        
        flac_count = len([t for t in tracks if str(normalize_rb_path(getattr(t[1], 'FolderPath', ''), getattr(t[1], 'FileNameL', '') or getattr(t[1], 'FileNameS', ''))).lower().endswith('.flac')])
        print(f"   📁 {folder.Name}: {len(tracks)} tracks ({flac_count} FLAC)")
    else:
        # This is a folder - recurse into children
        for child in children:
            collect_tracks_from_folder(db, child, playlists, track_data)

def main():
    print("🎵 Extracting FLAC paths from Rekordbox playlists")
    
    # Connect to Rekordbox
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6", 
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    db_dir = next((p for p in db_paths if p.exists()), None)
    if db_dir is None:
        print("❌ Rekordbox database not found")
        return 1
    
    print(f"📂 Connected to: {db_dir}")
    db = Rekordbox6Database(db_dir=str(db_dir))
    
    # Get all playlists
    playlists = db.get_playlist().all()
    print(f"📋 Found {len(playlists)} total playlists")
    
    # Find target playlists
    target_playlist_names = ["ALLDJ Baked", "ALLDJ Stems", "OG Stems"]
    target_playlists = []
    
    for playlist in playlists:
        playlist_name = getattr(playlist, 'Name', '')
        if playlist_name in target_playlist_names:
            target_playlists.append(playlist)
            print(f"✅ Found target playlist: {playlist_name}")
    
    if not target_playlists:
        print(f"❌ No target playlists found. Looking for: {target_playlist_names}")
        print("Available playlists:")
        for p in playlists[:20]:  # Show first 20
            print(f"   - {getattr(p, 'Name', '')}")
        return 1
    
    # Collect track data from all target playlists
    track_data = []
    
    for playlist in target_playlists:
        print(f"\n🔍 Processing playlist: {playlist.Name}")
        collect_tracks_from_folder(db, playlist, playlists, track_data)
    
    # Remove duplicates while preserving order
    unique_tracks = []
    seen = set()
    for track in track_data:
        flac_path = track["flac_path"]
        if flac_path not in seen:
            unique_tracks.append(track)
            seen.add(flac_path)
    
    print(f"\n📊 Results:")
    print(f"   Total FLAC files found: {len(track_data)}")
    print(f"   Unique FLAC files: {len(unique_tracks)}")
    
    # Use unique tracks as output data
    output_data = unique_tracks
    
    # Save to JSON file
    output_file = "playlist_flac_paths.json"
    print(f"\n💾 Saving to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ JSON file created successfully!")
    print(f"   File: {output_file}")
    print(f"   Total objects: {len(output_data)}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())