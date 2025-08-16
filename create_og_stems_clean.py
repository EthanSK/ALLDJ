#!/usr/bin/env python3
"""
Create OG Stems folder with Vocals and Instrumentals playlists in Rekordbox (clean version)
"""

import argparse
import sys
from pathlib import Path
from pyrekordbox import Rekordbox6Database

def flush_print(msg):
    print(msg, flush=True)

def get_or_create_folder(db, name: str, parent=None):
    """Create folder, checking for existing first"""
    existing = db.get_playlist(Name=name).first()
    if existing:
        flush_print(f"Using existing folder: {name}")
        return existing
    
    node = db.create_playlist_folder(name)
    if parent:
        try:
            db.move_playlist(node, parent)
            flush_print(f"Created folder: {name} under {getattr(parent, 'Name', 'ROOT')}")
        except Exception as e:
            flush_print(f"Warning: Could not move folder {name}: {e}")
    else:
        flush_print(f"Created root folder: {name}")
    return node

def get_or_create_playlist(db, name: str, parent=None):
    """Create playlist, checking for existing first"""
    existing = db.get_playlist(Name=name).first()
    if existing:
        flush_print(f"Using existing playlist: {name}")
        return existing
    
    node = db.create_playlist(name)
    if parent:
        try:
            db.move_playlist(node, parent)
            flush_print(f"Created playlist: {name} under {getattr(parent, 'Name', 'ROOT')}")
        except Exception as e:
            flush_print(f"Warning: Could not move playlist {name}: {e}")
    else:
        flush_print(f"Created root playlist: {name}")
    return node

def main():
    parser = argparse.ArgumentParser(description='Create OG Stems folder structure in Rekordbox')
    parser.add_argument('--stems-dir', default='/Volumes/T7 Shield/3000AD/og_separated_v2',
                        help='Directory with OG separated stem files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    stems_dir = Path(args.stems_dir)
    if not stems_dir.exists():
        flush_print(f"Error: Stems directory does not exist: {stems_dir}")
        return 1
    
    # Connect to Rekordbox database
    try:
        paths = [
            Path.home() / "Library/Pioneer/rekordbox7",
            Path.home() / "Library/Pioneer/rekordbox6", 
            Path.home() / "Library/Pioneer/rekordbox"
        ]
        db_dir = next((p for p in paths if p.exists()), None)
        if not db_dir:
            flush_print("Error: Could not find Rekordbox database directory")
            return 1
        
        db = Rekordbox6Database(db_dir=str(db_dir))
        flush_print(f"Connected to Rekordbox database at: {db_dir}")
        
    except Exception as e:
        flush_print(f"Error connecting to Rekordbox database: {e}")
        return 1
    
    # Get all FLAC files (skip hidden files)
    flac_files = [f for f in stems_dir.glob('*.flac') if not f.name.startswith('._')]
    flush_print(f"Found {len(flac_files)} FLAC files")
    
    # Classify files
    vocals_files = [f for f in flac_files if '_(Vocals).flac' in f.name]
    instrumental_files = [f for f in flac_files if '_(Instrumental).flac' in f.name]
    
    flush_print(f"Classified: {len(vocals_files)} vocals, {len(instrumental_files)} instrumentals")
    
    if args.dry_run:
        flush_print("\n[DRY RUN] Would create the following structure:")
        flush_print(f"  - 'OG Stems' folder containing:")
        flush_print(f"    - 'OG Vocals (All)' playlist with {len(vocals_files)} tracks")
        flush_print(f"    - 'OG Instrumentals (All)' playlist with {len(instrumental_files)} tracks")
        return 0
    
    # Create structure
    try:
        # Create OG Stems folder
        flush_print("\nCreating folder structure...")
        og_stems_folder = get_or_create_folder(db, "OG Stems")
        
        # Create playlists inside the folder
        vocals_playlist = get_or_create_playlist(db, "OG Vocals (All)", parent=og_stems_folder)
        instrumental_playlist = get_or_create_playlist(db, "OG Instrumentals (All)", parent=og_stems_folder)
        
        # Add tracks to vocals playlist
        flush_print(f"\nAdding {len(vocals_files)} tracks to vocals playlist...")
        for i, vocals_file in enumerate(vocals_files, 1):
            if i % 20 == 0 or i == len(vocals_files):
                flush_print(f"  Progress: {i}/{len(vocals_files)}")
            
            # Add track to Rekordbox if not present
            content = db.get_content(FileNameL=vocals_file.name).first()
            if not content:
                content = db.add_content(str(vocals_file))
                if not content:
                    continue
            
            # Add to playlist
            db.add_to_playlist(vocals_playlist, content)
        
        flush_print(f"✓ Added tracks to 'OG Vocals (All)'")
        
        # Add tracks to instrumentals playlist
        flush_print(f"\nAdding {len(instrumental_files)} tracks to instrumentals playlist...")
        for i, instrumental_file in enumerate(instrumental_files, 1):
            if i % 20 == 0 or i == len(instrumental_files):
                flush_print(f"  Progress: {i}/{len(instrumental_files)}")
            
            # Add track to Rekordbox if not present
            content = db.get_content(FileNameL=instrumental_file.name).first()
            if not content:
                content = db.add_content(str(instrumental_file))
                if not content:
                    continue
            
            # Add to playlist
            db.add_to_playlist(instrumental_playlist, content)
        
        flush_print(f"✓ Added tracks to 'OG Instrumentals (All)'")
        
        flush_print(f"\n✅ Successfully created OG Stems structure!")
        flush_print(f"   - OG Stems folder")
        flush_print(f"   - OG Vocals (All): {len(vocals_files)} tracks") 
        flush_print(f"   - OG Instrumentals (All): {len(instrumental_files)} tracks")
        
    except Exception as e:
        flush_print(f"Error creating structure: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())





