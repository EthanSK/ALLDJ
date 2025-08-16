#!/usr/bin/env python3

"""
Test script specifically for ALLDJ Baked playlists
Focuses on static playlists containing ALLDJ content, ignoring smart playlists.
"""

import sys
from pathlib import Path
from copy_rekordbox_playlists_to_usb import RekordboxPlaylistCopier

def main():
    print("🧪 Testing ALLDJ Baked Playlists Copy")
    print("="*50)
    
    # Create copier instance
    copier = RekordboxPlaylistCopier(
        usb_path="/Volumes/DJYING",
        test_mode=True,  # Always test mode
        resume=False     # Fresh start
    )
    
    try:
        # Initialize
        copier.usb_root.mkdir(exist_ok=True)
        copier.music_root.mkdir(parents=True, exist_ok=True)
        copier.playlists_root.mkdir(parents=True, exist_ok=True)
        
        copier.connect_to_database()
        copier.detect_smart_playlists()
        
        # Get all playlists
        all_playlists = copier.get_all_playlists()
        
        # Filter for Baked playlists only
        baked_playlists = []
        for playlist in all_playlists:
            if "baked" in playlist.name.lower() and playlist.track_count > 0:
                baked_playlists.append(playlist)
        
        print(f"📋 Found {len(baked_playlists)} Baked playlists with tracks:")
        for i, p in enumerate(baked_playlists[:10], 1):  # Show first 10
            print(f"  {i}. {p.name} ({p.track_count} tracks)")
        
        if not baked_playlists:
            print("❌ No Baked playlists found!")
            return
        
        # Test on first 3 Baked playlists
        test_playlists = baked_playlists[:3]
        print(f"\n🎯 Testing on first {len(test_playlists)} Baked playlists...")
        
        for i, playlist in enumerate(test_playlists, 1):
            print(f"\n[{i}/{len(test_playlists)}] Processing: {playlist.name}")
            print(f"  Tracks: {playlist.track_count}")
            
            # Get tracks for this playlist
            tracks = copier.get_playlist_tracks(playlist.id)
            print(f"  Retrieved {len(tracks)} track details")
            
            # Check how many files exist
            existing_count = sum(1 for track in tracks if track.exists)
            missing_count = len(tracks) - existing_count
            
            print(f"  ✅ {existing_count} files found")
            print(f"  ❌ {missing_count} files missing")
            
            if existing_count > 0:
                print(f"  🎵 Sample existing tracks:")
                for j, track in enumerate([t for t in tracks if t.exists][:3], 1):
                    print(f"    {j}. {track.title}")
            
            if missing_count > 0:
                print(f"  ⚠️  Sample missing tracks:")
                for j, track in enumerate([t for t in tracks if not t.exists][:2], 1):
                    print(f"    {j}. {track.title}")
                    print(f"       Path: {track.original_path}")
            
            # If we have some existing files, try copying this playlist
            if existing_count > 0:
                print(f"  🚀 Attempting copy...")
                try:
                    success = copier.copy_playlist(playlist)
                    if success:
                        print(f"  ✅ Copy successful!")
                    else:
                        print(f"  ❌ Copy failed")
                except Exception as e:
                    print(f"  ❌ Copy error: {e}")
            else:
                print(f"  ⏭️  Skipping (no existing files)")
        
        # Show final stats
        copier.print_stats()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if copier.db:
            copier.db.close()

if __name__ == "__main__":
    main()

