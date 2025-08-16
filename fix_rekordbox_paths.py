#!/usr/bin/env python3

import sys
import re
from pathlib import Path
import shutil
from datetime import datetime

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required")
    print("Install with: pip install pyrekordbox")
    sys.exit(1)

def normalize_title(title):
    """Normalize title for matching by removing common prefixes and cleaning."""
    if not title:
        return ""
    
    # Remove track number prefixes like "01-01 ", "12_", etc.
    title = re.sub(r'^\d+[-_]\d+\s+', '', title)
    title = re.sub(r'^\d+[-_]\s*', '', title)
    title = re.sub(r'^\d+\.\s*', '', title)
    
    # Remove file extensions
    title = re.sub(r'\.(flac|mp3|wav|aiff?)$', '', title, flags=re.IGNORECASE)
    
    # Normalize whitespace
    title = ' '.join(title.split())
    
    return title.strip()

def find_rekordbox_db():
    """Find the Rekordbox database directory."""
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6", 
        Path.home() / "Library/Pioneer/rekordbox"
    ]
    
    for path in db_paths:
        if path.exists():
            return path
    
    return None

def backup_database(db_path):
    """Create a backup of the Rekordbox database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"rekordbox_backup_{timestamp}"
    
    print(f"Creating backup: {backup_path}")
    shutil.copytree(db_path, backup_path)
    return backup_path

def fix_rekordbox_paths(flac_dir, dry_run=True):
    """Fix Rekordbox file paths to match renamed FLAC files."""
    
    # Find database
    db_path = find_rekordbox_db()
    if not db_path:
        print("Error: No Rekordbox database found")
        return False
    
    print(f"Using database: {db_path}")
    
    # Create backup unless dry run
    if not dry_run:
        backup_path = backup_database(db_path)
        print(f"Backup created at: {backup_path}")
    
    # Build index of FLAC files
    flac_path = Path(flac_dir)
    if not flac_path.exists():
        print(f"Error: FLAC directory not found: {flac_dir}")
        return False
    
    print(f"Scanning FLAC files in: {flac_dir}")
    flac_files = {}
    for flac_file in flac_path.glob("*.flac"):
        normalized_title = normalize_title(flac_file.stem)
        if normalized_title:
            flac_files[normalized_title] = flac_file
    
    print(f"Found {len(flac_files)} FLAC files")
    
    # Connect to database
    try:
        db = Rekordbox6Database(db_dir=str(db_path))
        
        # Get all tracks
        tracks = db.get_content().all()
        print(f"Found {len(tracks)} tracks in Rekordbox database")
        
        matched_count = 0
        updated_count = 0
        
        for track in tracks:
            # Normalize the track title for matching
            track_title_normalized = normalize_title(track.Title or "")
            
            if track_title_normalized in flac_files:
                matched_count += 1
                new_flac_path = flac_files[track_title_normalized]
                
                # Get current paths
                current_filename_l = track.FileNameL or ""
                current_filename_s = track.FileNameS or ""
                current_folder_path = track.FolderPath or ""
                
                # New paths
                new_filename = new_flac_path.name
                new_folder_path = str(new_flac_path.parent) + "/"
                
                # Check if update is needed
                needs_update = (
                    current_filename_l != new_filename or
                    current_filename_s != new_filename or
                    current_folder_path != new_folder_path
                )
                
                if needs_update:
                    print(f"\n{'[DRY RUN] ' if dry_run else ''}Updating: {track.Title}")
                    print(f"  Old FileNameL: {current_filename_l}")
                    print(f"  New FileNameL: {new_filename}")
                    print(f"  Old FolderPath: {current_folder_path}")
                    print(f"  New FolderPath: {new_folder_path}")
                    
                    if not dry_run:
                        # Update the track
                        track.FileNameL = new_filename
                        track.FileNameS = new_filename
                        track.FolderPath = new_folder_path
                        # Note: pyrekordbox should auto-commit changes
                    
                    updated_count += 1
        
        print(f"\n=== Summary ===")
        print(f"Tracks matched by title: {matched_count}")
        print(f"Tracks {'that would be ' if dry_run else ''}updated: {updated_count}")
        
        if dry_run:
            print("\nThis was a dry run. Use --apply to make actual changes.")
        else:
            print(f"\nDatabase updated successfully!")
            print(f"Backup available at: {backup_path}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"Error accessing database: {e}")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix Rekordbox file paths after removing number prefixes from FLAC files")
    parser.add_argument("--flac-dir", default="/Users/ethansarif-kattan/Music/ALLDJ/flac", 
                       help="Directory containing the renamed FLAC files")
    parser.add_argument("--apply", action="store_true", 
                       help="Actually apply changes (default is dry run)")
    
    args = parser.parse_args()
    
    print("Rekordbox Path Fixer")
    print("=" * 50)
    
    if not args.apply:
        print("Running in DRY RUN mode - no changes will be made")
        print("Use --apply to make actual changes")
        print()
    
    success = fix_rekordbox_paths(args.flac_dir, dry_run=not args.apply)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

