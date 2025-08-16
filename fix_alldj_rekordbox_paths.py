#!/usr/bin/env python3

import sys
import re
from pathlib import Path
import shutil
from datetime import datetime
import argparse

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required")
    print("Install with: pip install pyrekordbox")
    sys.exit(1)

try:
    from difflib import SequenceMatcher
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

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

def similarity(a, b):
    """Calculate similarity between two strings using SequenceMatcher."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_for_fuzzy(title):
    """More aggressive normalization for fuzzy matching."""
    if not title:
        return ""
    
    # Start with regular normalization
    title = normalize_title(title)
    
    # Remove common suffixes that might differ
    suffixes_to_remove = [
        r'\s*\(.*?\)\s*$',  # Remove anything in parentheses at the end
        r'\s*\[.*?\]\s*$',  # Remove anything in brackets at the end
        r'\s*-\s*.*$',      # Remove everything after a dash (often version info)
        r'\s*remaster.*$',  # Remove remaster info
        r'\s*remix.*$',     # Remove remix info
        r'\s*edit.*$',      # Remove edit info
        r'\s*version.*$',   # Remove version info
        r'\s*single.*$',    # Remove single info
        r'\s*album.*$',     # Remove album info
        r'\s*explicit.*$',  # Remove explicit info
        r'\s*clean.*$',     # Remove clean info
    ]
    
    for suffix in suffixes_to_remove:
        title = re.sub(suffix, '', title, flags=re.IGNORECASE)
    
    # Remove extra punctuation and normalize
    title = re.sub(r'[^\w\s]', '', title)  # Remove all punctuation
    title = ' '.join(title.split())        # Normalize whitespace
    
    return title.strip().lower()

def find_fuzzy_match(target_title, flac_titles, threshold=0.8):
    """Find the best fuzzy match for a target title."""
    if not FUZZY_AVAILABLE or not target_title:
        return None
    
    target_normalized = normalize_for_fuzzy(target_title)
    best_match = None
    best_score = 0
    
    for flac_title in flac_titles:
        flac_normalized = normalize_for_fuzzy(flac_title)
        score = similarity(target_normalized, flac_normalized)
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = flac_title
    
    return best_match, best_score if best_match else (None, 0)

def scan_flac_files(flac_dir):
    """Scan FLAC directory and build title->filename mapping."""
    flac_path = Path(flac_dir)
    if not flac_path.exists():
        print(f"Error: FLAC directory does not exist: {flac_dir}")
        sys.exit(1)
    
    title_to_file = {}
    
    print(f"Scanning FLAC files in: {flac_dir}")
    for flac_file in flac_path.glob("*.flac"):
        filename = flac_file.name
        # Extract title from filename (remove extension)
        title = filename.replace('.flac', '')
        normalized_title = normalize_title(title)
        
        if normalized_title:
            title_to_file[normalized_title] = filename
    
    print(f"Found {len(title_to_file)} FLAC files")
    return title_to_file

def main():
    parser = argparse.ArgumentParser(description='Fix ALLDJ Rekordbox file paths after removing number prefixes')
    parser.add_argument('--flac-dir', required=True, help='Path to FLAC files directory')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')
    
    args = parser.parse_args()
    
    print("ALLDJ Rekordbox Path Fixer")
    print("=" * 50)
    
    # Build FLAC file mapping
    title_to_file = scan_flac_files(args.flac_dir)
    
    # Connect to Rekordbox database
    db = Rekordbox6Database()
    
    if args.apply:
        # Create backup
        backup_name = f"rekordbox_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = Path.home() / "Library/Pioneer" / backup_name
        original_path = Path.home() / "Library/Pioneer/rekordbox"
        
        print(f"Creating backup: {backup_path}")
        shutil.copytree(original_path, backup_path)
        print(f"Backup created at: {backup_path}")
    
    # Get all tracks
    tracks = db.get_content()
    
    print("Scanning Rekordbox database...")
    
    updated_count = 0
    total_alldj_tracks = 0
    
    for track in tracks:
        # Check if this is an ALLDJ track
        if (track.FolderPath and 
            'ALLDJ' in track.FolderPath and 
            'flac' in track.FolderPath.lower() and
            track.FileNameL):
            
            total_alldj_tracks += 1
            
            # Normalize the track title for matching
            normalized_track_title = normalize_title(track.Title or "")
            
            # Check if we have a matching FLAC file
            if normalized_track_title in title_to_file:
                new_filename = title_to_file[normalized_track_title]
                new_folder_path = f"{args.flac_dir}/{new_filename}"
                
                # Check if paths need updating
                if (track.FileNameL != new_filename or 
                    track.FolderPath != new_folder_path):
                    
                    print(f"\nUpdating: {track.Title}")
                    print(f"  Old FileNameL: {track.FileNameL}")
                    print(f"  New FileNameL: {new_filename}")
                    print(f"  Old FolderPath: {track.FolderPath}")
                    print(f"  New FolderPath: {new_folder_path}")
                    
                    if args.apply:
                        # Update the track
                        track.FileNameL = new_filename
                        track.FolderPath = new_folder_path
                        db.session.merge(track)
                    
                    updated_count += 1
            else:
                # Track title doesn't match any FLAC file
                if args.apply:
                    print(f"No match found for: {track.Title} (normalized: {normalized_track_title})")
    
    if args.apply:
        # Commit changes
        db.session.commit()
        print(f"\n=== Summary ===")
        print(f"Total ALLDJ tracks: {total_alldj_tracks}")
        print(f"Tracks updated: {updated_count}")
        print(f"\nDatabase updated successfully!")
        print(f"Backup available at: {backup_path}")
    else:
        print(f"\n=== Dry Run Summary ===")
        print(f"Total ALLDJ tracks: {total_alldj_tracks}")
        print(f"Tracks that would be updated: {updated_count}")
        print(f"\nRun with --apply to make changes")
    
    db.close()

if __name__ == "__main__":
    main()
