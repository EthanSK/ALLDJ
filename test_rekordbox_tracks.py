#!/usr/bin/env python3

import sys
from pathlib import Path

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required")
    sys.exit(1)

def test_rekordbox_tracks():
    """Test what tracks look like in Rekordbox database."""
    try:
        # Try to find the database directory
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
            print("No Rekordbox database found")
            return
        
        print(f"Using database: {db_path}")
        db = Rekordbox6Database(db_dir=str(db_path))
        
        # Get first 10 tracks to see their structure
        tracks = db.get_content().limit(10).all()
        
        print(f"\nFound {len(tracks)} tracks (showing first 10):")
        print("=" * 80)
        
        for i, track in enumerate(tracks, 1):
            print(f"{i}. Title: {track.Title}")
            print(f"   FileNameL: {track.FileNameL}")
            print(f"   FileNameS: {track.FileNameS}")
            print(f"   FolderPath: {track.FolderPath}")
            print(f"   Commnt: {track.Commnt}")
            print("-" * 40)
            if i >= 5:  # Show first 5
                break
        
        # Test finding a specific file we know exists
        test_filename = "01-01 15 Step.flac"
        print(f"\nTesting search for: {test_filename}")
        
        # Try exact match with FileNameL
        exact_match_l = db.get_content(FileNameL=test_filename).first()
        if exact_match_l:
            print(f"✓ Found by FileNameL: {exact_match_l.Title}")
        else:
            print("✗ Not found by FileNameL")
            
        # Try exact match with FileNameS  
        exact_match_s = db.get_content(FileNameS=test_filename).first()
        if exact_match_s:
            print(f"✓ Found by FileNameS: {exact_match_s.Title}")
        else:
            print("✗ Not found by FileNameS")
        
        
        # Check what methods are available on the database object
        print(f"\n\nDatabase methods containing 'playlist':")
        db_methods = [method for method in dir(db) if 'playlist' in method.lower()]
        for method in db_methods:
            print(f"  - {method}")
            
        print(f"\nDatabase methods containing 'content':")
        content_methods = [method for method in dir(db) if 'content' in method.lower()]
        for method in content_methods:
            print(f"  - {method}")
            
        db.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_rekordbox_tracks()