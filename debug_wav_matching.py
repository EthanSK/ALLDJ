#!/usr/bin/env python3

"""
Debug script to understand the current Rekordbox structure and find tracks to map
"""

import sys
from pathlib import Path
from pyrekordbox import Rekordbox6Database, db6

def main():
    print("🔍 Debugging Rekordbox structure and track mapping")
    
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
    print(f"📊 Found {len(playlists)} total playlists")
    
    # Find the main folders we care about
    main_folders = ["ALLDJ Baked", "ALLDJ Stems", "OG Stems", "wav"]
    
    for folder_name in main_folders:
        folders = [p for p in playlists if p.Name == folder_name]
        print(f"\n📁 {folder_name}: Found {len(folders)} folder(s)")
        
        for i, folder in enumerate(folders):
            parent_id = getattr(folder, 'ParentID', None)
            parent_name = "root" if not parent_id else next((p.Name for p in playlists if p.ID == parent_id), f"ID:{parent_id}")
            print(f"   {i+1}. ID: {folder.ID}, Parent: {parent_name}")
            
            # Get children
            children = [p for p in playlists if getattr(p, 'ParentID', None) == folder.ID]
            print(f"      Children: {len(children)}")
            
            # Show first few children with track counts
            for j, child in enumerate(children[:3]):
                SP = db6.tables.DjmdSongPlaylist
                track_count = db.session.query(SP).filter(SP.PlaylistID == child.ID).count()
                print(f"         {j+1}. {child.Name} ({track_count} tracks)")
            
            if len(children) > 3:
                print(f"         ... and {len(children) - 3} more")
    
    # Look for any playlist with tracks that we can use for testing
    print(f"\n🎵 Looking for playlists with tracks to test mapping...")
    
    SP = db6.tables.DjmdSongPlaylist
    CT = db6.tables.DjmdContent
    
    # Get playlists with tracks
    playlists_with_tracks = []
    for playlist in playlists:
        if hasattr(playlist, 'ID'):
            track_count = db.session.query(SP).filter(SP.PlaylistID == playlist.ID).count()
            if track_count > 0:
                parent_id = getattr(playlist, 'ParentID', None)
                parent_name = "root" if not parent_id else next((p.Name for p in playlists if p.ID == parent_id), f"ID:{parent_id}")
                playlists_with_tracks.append((playlist, track_count, parent_name))
    
    # Sort by track count and show top 10
    playlists_with_tracks.sort(key=lambda x: x[1], reverse=True)
    print(f"📊 Top 10 playlists with tracks:")
    
    for i, (playlist, count, parent) in enumerate(playlists_with_tracks[:10]):
        print(f"   {i+1}. {playlist.Name} ({count} tracks) - Parent: {parent}")
    
    # Test file mapping on the first playlist with tracks
    if playlists_with_tracks:
        test_playlist, track_count, parent = playlists_with_tracks[0]
        print(f"\n🧪 Testing file mapping with '{test_playlist.Name}':")
        
        # Get first few tracks
        tracks = (
            db.session.query(SP, CT)
            .join(CT, CT.ID == SP.ContentID)
            .filter(SP.PlaylistID == test_playlist.ID)
            .limit(3)
            .all()
        )
        
        for i, (sp, ct) in enumerate(tracks, 1):
            name = (ct.FileNameL or ct.FileNameS or "").strip()
            title = ct.Title or name
            folder_path = ct.FolderPath or ""
            
            print(f"   {i}. {title}")
            print(f"      File: {name}")
            print(f"      Folder: {folder_path}")
            
            # Check if this looks like it's from our expected directories
            if "/Volumes/T7 Shield/3000AD/" in folder_path:
                print(f"      🎯 This is from our expected T7 Shield directory!")
                
                # Try to map to WAV
                full_path = Path(folder_path) / name if folder_path else Path(name)
                print(f"      Full path: {full_path}")
                
                # Show mapping
                s = str(full_path)
                for src_base, dst_base in [
                    ("/Volumes/T7 Shield/3000AD/alldj_stem_separated", "/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
                    ("/Volumes/T7 Shield/3000AD/og_separated_v2", "/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
                    ("/Volumes/T7 Shield/3000AD/flac_liked_songs", "/Volumes/T7 Shield/3000AD/wav_liked_songs"),
                ]:
                    if s.startswith(src_base):
                        tail = s[len(src_base):]
                        wav_path = Path(dst_base + tail).with_suffix(".wav")
                        print(f"      📂 Would map to: {wav_path}")
                        print(f"      📁 WAV exists: {wav_path.exists()}")
                        break
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
