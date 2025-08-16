#!/usr/bin/env python3
"""
Create giant OG Vocals (All) and OG Instrumentals (All) playlists in Rekordbox for og_separated_v2
"""

import argparse
import sys
from pathlib import Path
from pyrekordbox import Rekordbox6Database

def flush_print(msg):
    print(msg, flush=True)

def main():
    parser = argparse.ArgumentParser(description='Create giant OG playlists in Rekordbox')
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
    vocals_files = []
    instrumental_files = []
    
    for flac_file in flac_files:
        if '_(Vocals).flac' in flac_file.name:
            vocals_files.append(flac_file)
        elif '_(Instrumental).flac' in flac_file.name:
            instrumental_files.append(flac_file)
        else:
            flush_print(f"Warning: Unrecognized file pattern: {flac_file.name}")
    
    flush_print(f"Classified: {len(vocals_files)} vocals, {len(instrumental_files)} instrumentals")
    
    if args.dry_run:
        flush_print("\n[DRY RUN] Would create the following structure:")
        flush_print(f"  - 'OG Stems' folder containing:")
        flush_print(f"    - 'OG Vocals (All)' playlist with {len(vocals_files)} tracks")
        flush_print(f"    - 'OG Instrumentals (All)' playlist with {len(instrumental_files)} tracks")
        return 0
    
    # Create playlists
    try:
        # Create OG Stems folder first
        flush_print("Creating 'OG Stems' folder...")
        og_stems_folder = db.create_playlist_folder("OG Stems")
        
        # Create OG Vocals (All) playlist and move it inside the folder
        flush_print("Creating 'OG Vocals (All)' playlist...")
        vocals_playlist = db.create_playlist("OG Vocals (All)")
        db.move_playlist(vocals_playlist, og_stems_folder)
        
        # Add vocals files to playlist
        for i, vocals_file in enumerate(vocals_files, 1):
            flush_print(f"  [{i}/{len(vocals_files)}] Adding: {vocals_file.name}")
            
            # Add track to Rekordbox if not present
            content = db.get_content(FileNameL=vocals_file.name).first()
            if not content:
                content = db.add_content(str(vocals_file))
                if not content:
                    flush_print(f"    ✗ Failed to import track")
                    continue
                flush_print(f"    ✓ Imported track to Rekordbox")
            
            # Add to playlist
            db.add_to_playlist(vocals_playlist, content)
        
        flush_print(f"✓ Created 'OG Vocals (All)' with {len(vocals_files)} tracks")
        
        # Create OG Instrumentals (All) playlist and move it inside the folder
        flush_print("Creating 'OG Instrumentals (All)' playlist...")
        instrumental_playlist = db.create_playlist("OG Instrumentals (All)")
        db.move_playlist(instrumental_playlist, og_stems_folder)
        
        # Add instrumental files to playlist
        for i, instrumental_file in enumerate(instrumental_files, 1):
            flush_print(f"  [{i}/{len(instrumental_files)}] Adding: {instrumental_file.name}")
            
            # Add track to Rekordbox if not present
            content = db.get_content(FileNameL=instrumental_file.name).first()
            if not content:
                content = db.add_content(str(instrumental_file))
                if not content:
                    flush_print(f"    ✗ Failed to import track")
                    continue
                flush_print(f"    ✓ Imported track to Rekordbox")
            
            # Add to playlist
            db.add_to_playlist(instrumental_playlist, content)
        
        flush_print(f"✓ Created 'OG Instrumentals (All)' with {len(instrumental_files)} tracks")
        
        flush_print("\n✅ Successfully created both giant OG playlists!")
        
    except Exception as e:
        flush_print(f"Error creating playlists: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
