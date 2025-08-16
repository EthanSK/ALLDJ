#!/usr/bin/env python3

print("Testing database connection...")

try:
    from pyrekordbox import Rekordbox6Database
    from pathlib import Path
    
    print("Finding database path...")
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6", 
        Path.home() / "Library/Pioneer/rekordbox"
    ]
    
    db_path = None
    for path in db_paths:
        print(f"Checking: {path}")
        if path.exists():
            db_path = path
            print(f"✓ Found database at: {db_path}")
            break
    
    if db_path is None:
        print("❌ No Rekordbox database directory found")
        exit(1)
    
    print("Attempting connection...")
    db = Rekordbox6Database(db_dir=str(db_path))
    print("✓ Connected successfully!")
    
    print("Testing basic query...")
    # Try a simple query
    count = len(list(db.get_content()))
    print(f"✓ Found {count} tracks in database")
    
    db.close()
    print("✓ Connection closed successfully")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()