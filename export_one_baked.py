#!/usr/bin/env python3

"""
Export just ONE Baked playlist to test the system works
"""

import sys
from pathlib import Path
from copy_rekordbox_playlists_to_usb import RekordboxPlaylistCopier

def main():
    print("🎯 Exporting ONE Baked Playlist for Testing")
    print("="*50)
    
    # Create copier instance
    copier = RekordboxPlaylistCopier(
        usb_path="/Volumes/DJYING",
        test_mode=False,  # Full export mode
        resume=False      # Fresh start
    )
    
    try:
        # Initialize
        copier.usb_root.mkdir(exist_ok=True)
        copier.music_root.mkdir(parents=True, exist_ok=True)
        copier.playlists_root.mkdir(parents=True, exist_ok=True)
        
        print("📡 Connecting to Rekordbox...")
        copier.connect_to_database()
        copier.detect_smart_playlists()
        
        print("🔍 Finding Baked playlists...")
        all_playlists = copier.get_all_playlists()
        
        # Find a good Baked playlist to test with
        target_playlist = None
        for playlist in all_playlists:
            if ("baked" in playlist.name.lower() and 
                playlist.track_count > 20 and 
                playlist.track_count < 100):  # Good size for testing
                target_playlist = playlist
                break
        
        if not target_playlist:
            # Fallback to any baked playlist
            for playlist in all_playlists:
                if "baked" in playlist.name.lower() and playlist.track_count > 0:
                    target_playlist = playlist
                    break
        
        if not target_playlist:
            print("❌ No Baked playlists found!")
            return
        
        print(f"🎵 Selected playlist: {target_playlist.name}")
        print(f"📊 Track count: {target_playlist.track_count}")
        print(f"📂 Full path: {target_playlist.full_path}")
        
        # Get track details
        print("📋 Getting track details...")
        tracks = copier.get_playlist_tracks(target_playlist.id)
        
        existing_count = sum(1 for track in tracks if track.exists)
        missing_count = len(tracks) - existing_count
        
        print(f"✅ {existing_count} files found")
        print(f"❌ {missing_count} files missing")
        
        if existing_count == 0:
            print("⚠️  No files found - cannot test copy")
            return
        
        # Show a few sample tracks
        print(f"\n🎶 Sample tracks to copy:")
        for i, track in enumerate([t for t in tracks if t.exists][:5], 1):
            print(f"  {i}. {track.artist} - {track.title}")
        
        print(f"\n🚀 Starting copy process...")
        print(f"📁 USB Music: {copier.music_root}")
        print(f"📁 USB Playlists: {copier.playlists_root}")
        
        # Copy the playlist
        success = copier.copy_playlist(target_playlist)
        
        if success:
            print(f"\n✅ SUCCESS! Playlist exported:")
            print(f"   Name: {target_playlist.name}")
            print(f"   Tracks copied: {existing_count}")
            print(f"   Location: {copier.playlists_root}")
            
            # Show what was created
            playlist_files = list(copier.playlists_root.rglob("*.m3u8"))
            if playlist_files:
                print(f"\n📄 Created playlist files:")
                for pf in playlist_files:
                    rel_path = pf.relative_to(copier.usb_root)
                    print(f"   {rel_path}")
            
            print(f"\n🎯 Test this in Rekordbox by:")
            print(f"   1. Check USB at: {copier.usb_root}")
            print(f"   2. Import the .m3u8 file")
            print(f"   3. Verify tracks play correctly")
            
        else:
            print(f"❌ Export failed")
        
        # Final stats
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

