#!/usr/bin/env python3
import os
import json
from pathlib import Path

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required")
    exit(1)

def find_rekordbox_db():
    """Find the Rekordbox database directory"""
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6", 
        Path.home() / "Library/Pioneer/rekordbox"
    ]
    
    for path in db_paths:
        if path.exists():
            print(f"Found Rekordbox database: {path}")
            return path
    
    print("Rekordbox database not found in common locations")
    return None

def get_all_playlists(rb):
    """Get all actual playlists from Rekordbox database."""
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

def get_playlist_tracks(rb, playlist_id):
    """Get all tracks in a playlist."""
    tracks = []
    
    try:
        playlist_songs = rb.get_playlist_contents(playlist_id).all()
        
        for song in playlist_songs:
            track_info = {
                'title': song.Title or "Unknown",
                'artist': song.Artist or "Unknown Artist",
                'file_path': song.FolderPath or "",
                'filename_l': song.FileNameL or "",
                'filename_s': song.FileNameS or "",
                'comment': song.Commnt or ""
            }
            tracks.append(track_info)
    except Exception as e:
        print(f"Error getting tracks for playlist {playlist_id}: {e}")
    
    return tracks

def analyze_alldj_playlists(rb):
    """Find and analyze ALLDJ playlists"""
    playlists = get_all_playlists(rb)
    alldj_data = {}
    
    # Filter for ALLDJ playlists
    alldj_keywords = ['ALLDJ BAKED', 'ALLDJ STEMS', 'OG STEMS']
    
    for playlist in playlists:
        folder_path = '/'.join(playlist['folder_path'])
        
        # Check if this playlist is under any ALLDJ folder
        for keyword in alldj_keywords:
            if keyword in folder_path.upper() or keyword in playlist['name'].upper():
                if keyword not in alldj_data:
                    alldj_data[keyword] = []
                
                # Get tracks for this playlist
                tracks = get_playlist_tracks(rb, playlist['id'])
                
                playlist_data = {
                    'id': playlist['id'],
                    'name': playlist['name'],
                    'folder_path': playlist['folder_path'],
                    'full_path': playlist['full_path'],
                    'track_count': len(tracks),
                    'tracks': tracks
                }
                
                alldj_data[keyword].append(playlist_data)
                print(f"Found {keyword} playlist: {playlist['full_path']} ({len(tracks)} tracks)")
                break
    
    return alldj_data

def main():
    # Find Rekordbox database
    db_path = find_rekordbox_db()
    if not db_path:
        return
    
    print(f"Using database: {db_path}")
    rb = Rekordbox6Database(db_dir=str(db_path))
    
    try:
        # Analyze ALLDJ playlists
        alldj_data = analyze_alldj_playlists(rb)
        
        if alldj_data:
            # Save analysis to JSON
            output_file = "rekordbox_alldj_analysis.json"
            with open(output_file, 'w') as f:
                json.dump(alldj_data, f, indent=2, default=str)
            
            print(f"\nAnalysis saved to: {output_file}")
            
            total_playlists = sum(len(playlists) for playlists in alldj_data.values())
            print(f"Found {total_playlists} ALLDJ playlists")
            
            for folder_name, playlists in alldj_data.items():
                print(f"\n{folder_name}: {len(playlists)} playlists")
                for playlist in playlists[:3]:  # Show first 3 as examples
                    print(f"  - {playlist['name']} ({playlist['track_count']} tracks)")
                if len(playlists) > 3:
                    print(f"  ... and {len(playlists) - 3} more")
        else:
            print("No ALLDJ playlists found")
    
    finally:
        rb.close()

if __name__ == "__main__":
    main()