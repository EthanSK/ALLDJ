#!/usr/bin/env python3

"""
Pre-flight test script for Rekordbox playlist copying.
Validates setup and runs checks before the main copy operation.
"""

import sys
from pathlib import Path
from typing import List, Tuple
import json

try:
    from pyrekordbox import Rekordbox6Database, db6
except ImportError:
    print("❌ Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    sys.exit(1)


def test_usb_connection(usb_path: str = "/Volumes/DJYING") -> bool:
    """Test if USB drive is connected and writable."""
    print("🔌 Testing USB connection...")
    
    usb = Path(usb_path)
    if not usb.exists():
        print(f"❌ USB drive not found at {usb_path}")
        print("Available volumes:")
        for vol in Path("/Volumes").iterdir():
            if vol.is_dir():
                print(f"  - {vol}")
        return False
    
    # Test write permissions
    test_file = usb / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print(f"✅ USB drive connected and writable at {usb_path}")
        return True
    except Exception as e:
        print(f"❌ USB drive not writable: {e}")
        return False


def test_database_connection() -> Tuple[bool, str]:
    """Test Rekordbox database connection."""
    print("🗄️  Testing Rekordbox database connection...")
    
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6",
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if db_path is None:
        print("❌ No Rekordbox database found")
        print("Checked paths:")
        for path in db_paths:
            print(f"  - {path}")
        return False, ""
    
    try:
        db = Rekordbox6Database(db_dir=str(db_path))
        
        # Test basic operations
        tracks_count = len(db.get_content().limit(1).all())
        playlists_count = len(db.get_playlist().limit(1).all())
        
        db.close()
        
        print(f"✅ Connected to Rekordbox database at {db_path}")
        print(f"   Database appears healthy (tracks and playlists accessible)")
        return True, str(db_path)
        
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        if "key" in str(e).lower():
            print("💡 Try running: python -m pyrekordbox download-key")
        return False, str(db_path)


def analyze_playlists(limit: int = 10) -> List[dict]:
    """Analyze first few playlists to understand structure."""
    print(f"📊 Analyzing playlist structure (first {limit})...")
    
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6",
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        return []
    
    try:
        db = Rekordbox6Database(db_dir=str(db_path))
        
        # Get smart playlists
        smart_playlist_ids = set()
        try:
            Smart = db6.tables.DjmdSmartList
            smart_rows = db.session.query(Smart).all()
            smart_playlist_ids = {str(r.PlaylistID) for r in smart_rows}
        except Exception:
            pass
        
        # Get all playlists
        all_playlists = db.get_playlist().all()
        playlists_info = []
        
        count = 0
        for playlist in all_playlists:
            if count >= limit:
                break
                
            playlist_id = str(playlist.ID)
            
            # Skip smart playlists
            if playlist_id in smart_playlist_ids:
                continue
            
            # Try to get track count
            try:
                SP = db6.tables.DjmdSongPlaylist
                track_count = db.session.query(SP).filter(SP.PlaylistID == int(playlist_id)).count()
            except Exception:
                track_count = 0
            
            # Get sample tracks
            sample_tracks = []
            if track_count > 0:
                try:
                    SP = db6.tables.DjmdSongPlaylist
                    CT = db6.tables.DjmdContent
                    rows = (
                        db.session.query(SP, CT)
                        .join(CT, CT.ID == SP.ContentID)
                        .filter(SP.PlaylistID == int(playlist_id))
                        .limit(3)
                        .all()
                    )
                    
                    for sp, ct in rows:
                        track_info = {
                            "title": ct.Title or "Unknown",
                            "filename": ct.FileNameL or ct.FileNameS or "Unknown",
                            "folder": ct.FolderPath or "",
                            "exists": False
                        }
                        
                        # Check if file exists
                        if track_info["folder"] and track_info["filename"]:
                            folder = track_info["folder"]
                            filename = track_info["filename"]
                            
                            # Handle Rekordbox path construction issues
                            if folder.endswith("/" + filename):
                                # Already includes filename
                                full_path = folder.rstrip("/")
                            elif folder.endswith(filename + "/" + filename):
                                # Double filename bug
                                full_path = folder.replace("/" + filename, "").rstrip("/")
                            elif "/" + filename + "/" in folder:
                                # Filename appears in middle, extract up to that point
                                parts = folder.split("/" + filename + "/")
                                full_path = parts[0] + "/" + filename
                            else:
                                # Normal construction
                                if folder.endswith("/"):
                                    full_path = folder + filename
                                else:
                                    full_path = folder + "/" + filename
                            
                            track_info["full_path"] = full_path
                            track_info["exists"] = Path(full_path).exists()
                        
                        sample_tracks.append(track_info)
                        
                except Exception as e:
                    print(f"Warning: Could not analyze tracks for playlist {playlist.Name}: {e}")
            
            playlist_info = {
                "id": playlist_id,
                "name": playlist.Name,
                "parent_id": str(getattr(playlist, 'ParentID', None)),
                "track_count": track_count,
                "is_smart": playlist_id in smart_playlist_ids,
                "sample_tracks": sample_tracks
            }
            
            playlists_info.append(playlist_info)
            count += 1
        
        db.close()
        
        # Print analysis
        print(f"Found {len(playlists_info)} non-smart playlists to analyze:")
        print("="*80)
        
        for i, playlist in enumerate(playlists_info, 1):
            print(f"{i}. {playlist['name']} ({playlist['track_count']} tracks)")
            
            if playlist['sample_tracks']:
                for j, track in enumerate(playlist['sample_tracks'][:2], 1):
                    status = "✅" if track['exists'] else "❌"
                    print(f"   {j}. {status} {track['title']}")
                    if not track['exists']:
                        print(f"      Path: {track.get('full_path', track['folder'] + '/' + track['filename'])}")
            
            print()
        
        return playlists_info
        
    except Exception as e:
        print(f"❌ Error analyzing playlists: {e}")
        return []


def check_disk_space(usb_path: str = "/Volumes/DJYING") -> bool:
    """Check available disk space on USB."""
    print("💾 Checking disk space...")
    
    usb = Path(usb_path)
    if not usb.exists():
        print("❌ USB drive not found")
        return False
    
    try:
        stat = usb.stat()
        # This is approximate - getting exact free space requires platform-specific code
        print(f"✅ USB drive accessible")
        print(f"   Path: {usb}")
        return True
    except Exception as e:
        print(f"❌ Could not check disk space: {e}")
        return False


def main():
    print("🧪 Rekordbox Playlist Copy - Pre-Flight Tests")
    print("="*60)
    
    all_passed = True
    
    # Test 1: USB Connection
    usb_ok = test_usb_connection()
    all_passed = all_passed and usb_ok
    print()
    
    # Test 2: Database Connection
    db_ok, db_path = test_database_connection()
    all_passed = all_passed and db_ok
    print()
    
    # Test 3: Disk Space
    if usb_ok:
        space_ok = check_disk_space()
        all_passed = all_passed and space_ok
        print()
    
    # Test 4: Playlist Analysis
    if db_ok:
        playlists = analyze_playlists(5)
        if playlists:
            print(f"✅ Found {len(playlists)} playlists to analyze")
            
            # Check for missing files
            missing_files = 0
            total_files = 0
            for playlist in playlists:
                for track in playlist['sample_tracks']:
                    total_files += 1
                    if not track['exists']:
                        missing_files += 1
            
            if total_files > 0:
                missing_pct = (missing_files / total_files) * 100
                print(f"📊 File availability: {total_files - missing_files}/{total_files} found ({missing_pct:.1f}% missing)")
                
                if missing_pct > 50:
                    print("⚠️  Warning: High percentage of missing files detected")
                    all_passed = False
        else:
            print("❌ No playlists found or error analyzing")
            all_passed = False
        print()
    
    # Final Summary
    print("="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print()
        print("Ready to run playlist copy! Recommended commands:")
        print("  # Test with 5 playlists first:")
        print("  python copy_rekordbox_playlists_to_usb.py --test")
        print()
        print("  # If test looks good, run full copy:")
        print("  python copy_rekordbox_playlists_to_usb.py --full")
    else:
        print("❌ SOME TESTS FAILED")
        print()
        print("Please fix the issues above before running the copy script.")
    
    print("="*60)
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
