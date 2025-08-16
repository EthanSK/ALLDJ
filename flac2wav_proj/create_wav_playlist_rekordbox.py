#!/usr/bin/env python3
"""
Create WAV playlists in Rekordbox based on existing ALLDJ playlists
Using FLAC-to-WAV mapping to find corresponding WAV files
"""

import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required")
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
    
    # Construct full path
    if folder_path:
        if folder_path and not folder_path.endswith("/"):
            folder_path += "/"
        full_path = folder_path + filename
    else:
        full_path = filename
    
    try:
        return Path(full_path).resolve()
    except Exception:
        return Path(full_path)

def load_flac_wav_mapping():
    """Load the FLAC to WAV mapping JSON"""
    mapping_file = "flac_to_wav_mapping.json"
    if not os.path.exists(mapping_file):
        print(f"Error: {mapping_file} not found")
        return None
    
    with open(mapping_file, 'r') as f:
        return json.load(f)

def find_rekordbox_db():
    """Find the Rekordbox database directory"""
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6", 
        Path.home() / "Library/Pioneer/rekordbox"
    ]
    
    for path in db_paths:
        if path.exists():
            return path
    
    print("Rekordbox database not found")
    return None

def get_playlist_tracks(rb, playlist_id):
    """Get all tracks in a playlist."""
    tracks = []
    
    try:
        playlist_songs = rb.get_playlist_contents(playlist_id).all()
        
        for song in playlist_songs:
            # Get the file path from Rekordbox
            file_path = normalize_rekordbox_path(
                song.FolderPath or "", 
                song.FileNameL or song.FileNameS or ""
            )
            
            track_info = {
                'title': song.Title or "Unknown",
                'artist': song.Artist or "Unknown Artist",
                'file_path': str(file_path) if file_path else "",
                'comment': song.Commnt or ""
            }
            tracks.append(track_info)
    except Exception as e:
        print(f"Error getting tracks for playlist {playlist_id}: {e}")
    
    return tracks

def find_wav_equivalent(flac_path, mapping):
    """Find the WAV equivalent of a FLAC file using the mapping"""
    flac_path_str = str(flac_path)
    
    # Direct match
    if flac_path_str in mapping:
        return mapping[flac_path_str]
    
    # Try to match by filename if direct path fails
    flac_name = os.path.basename(flac_path_str)
    for flac_key, wav_path in mapping.items():
        if os.path.basename(flac_key) == flac_name:
            return wav_path
    
    return None

def add_track_to_rekordbox(rb, track_path, title=None, artist=None, comment=None):
    """Add a track to Rekordbox database (simplified - this is complex in practice)"""
    # This is a placeholder - actually adding tracks to Rekordbox programmatically
    # is very complex and requires understanding the full database schema
    print(f"Would add track: {track_path}")
    return True

def create_wav_playlist(rb, original_playlist_name, original_playlist_id, mapping, root_folder="WAV"):
    """Create a new WAV playlist based on an existing FLAC playlist"""
    
    print(f"\nProcessing playlist: {original_playlist_name}")
    
    # Get tracks from original playlist
    tracks = get_playlist_tracks(rb, original_playlist_id)
    print(f"Found {len(tracks)} tracks in original playlist")
    
    wav_tracks = []
    missing_tracks = []
    
    # Find WAV equivalents
    for track in tracks:
        if track['file_path']:
            wav_path = find_wav_equivalent(track['file_path'], mapping)
            if wav_path and os.path.exists(wav_path):
                wav_tracks.append({
                    'original_path': track['file_path'],
                    'wav_path': wav_path,
                    'title': track['title'],
                    'artist': track['artist'],
                    'comment': track['comment']
                })
                print(f"  ✓ Found WAV: {os.path.basename(wav_path)}")
            else:
                missing_tracks.append(track)
                print(f"  ✗ Missing WAV for: {os.path.basename(track['file_path'])}")
    
    print(f"WAV tracks found: {len(wav_tracks)}")
    print(f"Missing tracks: {len(missing_tracks)}")
    
    # For now, just create an M3U8 playlist file instead of adding to Rekordbox
    # (Adding to Rekordbox database programmatically is very complex)
    wav_playlist_name = f"{root_folder}_{original_playlist_name}"
    playlist_file = f"{wav_playlist_name}.m3u8"
    
    with open(playlist_file, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for track in wav_tracks:
            f.write(f"#EXTINF:-1,{track['artist']} - {track['title']}\n")
            f.write(f"{track['wav_path']}\n")
    
    print(f"Created playlist file: {playlist_file}")
    
    return {
        'playlist_name': wav_playlist_name,
        'playlist_file': playlist_file,
        'wav_tracks': len(wav_tracks),
        'missing_tracks': len(missing_tracks),
        'success': len(wav_tracks) > 0
    }

def main():
    # Load FLAC-WAV mapping
    mapping = load_flac_wav_mapping()
    if not mapping:
        return
    
    print(f"Loaded mapping for {len(mapping)} files")
    
    # Find Rekordbox database
    db_path = find_rekordbox_db()
    if not db_path:
        return
    
    print(f"Using database: {db_path}")
    rb = Rekordbox6Database(db_dir=str(db_path))
    
    try:
        # Get all playlists
        all_playlists = rb.get_playlist().all()
        
        # Find first ALLDJ Baked playlist for testing
        test_playlist = None
        for playlist in all_playlists:
            # Build folder hierarchy
            folder_path = []
            parent_id = getattr(playlist, 'ParentID', None)
            
            while parent_id and parent_id != 0:
                parent_playlists = [p for p in all_playlists if getattr(p, 'ID', None) == parent_id]
                if parent_playlists:
                    parent = parent_playlists[0]
                    folder_path.insert(0, parent.Name)
                    parent_id = getattr(parent, 'ParentID', None)
                else:
                    break
            
            full_path = '/'.join(folder_path + [playlist.Name]) if folder_path else playlist.Name
            
            # Look for a small ALLDJ Baked playlist to test with
            if 'ALLDJ Baked' in full_path and 'acoustic' in playlist.Name.lower():
                try:
                    track_count = len(rb.get_playlist_contents(playlist.ID).all())
                    if track_count > 0:  # Make sure it has tracks
                        test_playlist = {
                            'id': playlist.ID,
                            'name': playlist.Name,
                            'full_path': full_path,
                            'track_count': track_count
                        }
                        break
                except:
                    continue
        
        if test_playlist:
            print(f"Testing with playlist: {test_playlist['full_path']} ({test_playlist['track_count']} tracks)")
            
            result = create_wav_playlist(
                rb,
                test_playlist['name'],
                test_playlist['id'],
                mapping,
                root_folder="WAV"
            )
            
            if result['success']:
                print(f"\n✅ Successfully created WAV playlist!")
                print(f"   Playlist: {result['playlist_name']}")
                print(f"   File: {result['playlist_file']}")
                print(f"   WAV tracks: {result['wav_tracks']}")
                print(f"   Missing: {result['missing_tracks']}")
            else:
                print(f"\n❌ Failed to create WAV playlist")
        else:
            print("No suitable test playlist found")
    
    finally:
        rb.close()

if __name__ == "__main__":
    main()