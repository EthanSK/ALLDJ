#!/usr/bin/env python3

"""
Delete Baked Playlists from Rekordbox

This script deletes all baked playlists and folders from Rekordbox so they can be recreated properly.
"""

import sys
from pathlib import Path

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    sys.exit(1)

def connect_to_database():
    """Connect to the Rekordbox database."""
    try:
        print("Connecting to Rekordbox database...")
        
        # Try to find the database directory (7 first, then 6, then legacy)
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
            raise Exception("No Rekordbox database directory found")
        
        print(f"Found Rekordbox database at: {db_path}")
        
        # Connect to the database with the found path
        db = Rekordbox6Database(db_dir=str(db_path))
        print("✓ Connected successfully")
        return db
    except Exception as e:
        print(f"Error: Failed to connect to Rekordbox database: {e}")
        sys.exit(1)

def delete_baked_playlists():
    """Delete all baked playlists and folders."""
    db = connect_to_database()
    
    print("\nDeleting baked playlists...")
    
    # Get all playlists
    all_playlists = db.get_playlist().all()
    
    deleted_count = 0
    
    # Delete playlists with "Baked" in the name
    for playlist in all_playlists:
        if "Baked" in playlist.Name:
            try:
                db.delete_playlist(playlist)
                print(f"  ✓ Deleted: '{playlist.Name}'")
                deleted_count += 1
            except Exception as e:
                print(f"  ✗ Failed to delete '{playlist.Name}': {e}")
    
    # Commit changes
    if deleted_count > 0:
        print(f"\nCommitting changes...")
        try:
            db.commit()
            print("✓ Changes committed successfully")
        except Exception as e:
            print(f"✗ Error committing changes: {e}")
    
    print(f"\n📊 Summary:")
    print(f"   Deleted: {deleted_count} playlists/folders")
    
    # Close database connection
    db.close()

if __name__ == "__main__":
    print("🎵 Delete Baked Playlists from Rekordbox")
    print("========================================")
    
    response = input("Are you sure you want to delete all baked playlists? (y/N): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        sys.exit(0)
    
    delete_baked_playlists()
    print("\n✅ Deletion complete!")