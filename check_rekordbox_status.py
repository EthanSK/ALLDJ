#!/usr/bin/env python3

"""
Check current status in Rekordbox to see what actually worked
"""

import sys
from pathlib import Path
from pyrekordbox import Rekordbox6Database

def main():
    print("🔍 Checking current Rekordbox status")
    
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
    print(f"📊 Total playlists: {len(playlists)}")
    
    # Look for wav folder and its contents
    wav_folders = [p for p in playlists if p.Name == "wav"]
    print(f"\n📁 'wav' folders found: {len(wav_folders)}")
    
    for wav_folder in wav_folders:
        print(f"   wav folder ID: {wav_folder.ID}")
        
        # Get children of wav folder
        wav_children = [p for p in playlists if getattr(p, 'ParentID', None) == wav_folder.ID]
        print(f"   Children under wav: {len(wav_children)}")
        
        for child in wav_children:
            print(f"     - {child.Name}")
            
            # Check if this has children (folder) or tracks (playlist)
            grandchildren = [p for p in playlists if getattr(p, 'ParentID', None) == child.ID]
            if grandchildren:
                print(f"       └─ {len(grandchildren)} subfolders/playlists")
    
    # Look for any WAV-related playlists
    wav_playlists = [p for p in playlists if 'WAV' in p.Name or 'wav' in p.Name.lower()]
    print(f"\n🎵 WAV-related playlists found: {len(wav_playlists)}")
    
    for playlist in wav_playlists[:10]:  # Show first 10
        print(f"   - {playlist.Name}")
    
    if len(wav_playlists) > 10:
        print(f"   ... and {len(wav_playlists) - 10} more")
    
    # Check some recent playlists
    print(f"\n📋 Recent playlists (last 10):")
    for playlist in playlists[-10:]:
        print(f"   - {playlist.Name}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
