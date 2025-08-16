#!/usr/bin/env python3

print("Starting debug test...")

try:
    print("Testing imports...")
    import json
    print("✓ json imported")
    
    import os
    print("✓ os imported")
    
    from pathlib import Path
    print("✓ pathlib imported")
    
    print("Testing pyrekordbox import...")
    from pyrekordbox import Rekordbox6Database
    print("✓ pyrekordbox imported")
    
    print("Testing metadata file loading...")
    with open("music_collection_metadata.json", 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    print(f"✓ Loaded metadata with {len(metadata.get('tracks', []))} tracks")
    
    print("Testing stems directory...")
    stems_dir = Path("/Volumes/T7 Shield/3000AD/alldj_stem_separated")
    print(f"Stems directory exists: {stems_dir.exists()}")
    
    print("All tests passed!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()