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
    print("Warning: difflib not available, fuzzy matching disabled")

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

def find_fuzzy_match(target_title, flac_mapping, threshold=0.75):
    """Find the best fuzzy match for a target title."""
    if not FUZZY_AVAILABLE or not target_title:
        return None, 0
    
    target_normalized = normalize_for_fuzzy(target_title)
    best_match = None
    best_score = 0
    
    for flac_title in flac_mapping.keys():
        flac_normalized = normalize_for_fuzzy(flac_title)
        score = similarity(target_normalized, flac_normalized)
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = flac_title
    
    return best_match, best_score

def scan_flac_files(flac_dir):
    """Scan FLAC directory and build title->filename mapping."""
    flac_path = Path(flac_dir)
    if not flac_path.exists():
        print(f"Error: FLAC directory not found: {flac_dir}")
        sys.exit(1)
    
    title_to_file = {}
    
    for flac_file in flac_path.glob("*.flac"):
        filename = flac_file.name
        title = filename.replace('.flac', '')
        normalized_title = normalize_title(title)
        
        if normalized_title:
            title_to_file[normalized_title] = filename
    
    print(f"Found {len(title_to_file)} FLAC files")
    return title_to_file

def main():
    parser = argparse.ArgumentParser(description='Fix ALLDJ Rekordbox file paths with fuzzy matching')
    parser.add_argument('--flac-dir', required=True, help='Path to FLAC files directory')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')
    parser.add_argument('--fuzzy-threshold', type=float, default=0.75, help='Fuzzy matching threshold (0.0-1.0, default: 0.75)')
    parser.add_argument('--show-fuzzy', action='store_true', help='Show fuzzy matches in detail')
    
    args = parser.parse_args()
    
    print("ALLDJ Rekordbox Path Fixer (with Fuzzy Matching)")
    print("=" * 55)
    print(f"Fuzzy matching threshold: {args.fuzzy_threshold}")
    if not FUZZY_AVAILABLE:
        print("⚠️  Fuzzy matching unavailable - only exact matches will be found")
    print()
    
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
    exact_matches = 0
    fuzzy_matches = 0
    no_matches = 0
    fuzzy_match_details = []
    no_match_details = []
    
    for track in tracks:
        # Check if this is an ALLDJ track
        if (track.FolderPath and 
            'ALLDJ' in track.FolderPath and 
            'flac' in track.FolderPath.lower() and
            track.FileNameL):
            
            total_alldj_tracks += 1
            
            # Normalize the track title for matching
            normalized_track_title = normalize_title(track.Title or "")
            
            new_filename = None
            match_type = None
            fuzzy_score = 0
            fuzzy_original = None
            
            # Try exact match first
            if normalized_track_title in title_to_file:
                new_filename = title_to_file[normalized_track_title]
                match_type = "exact"
                exact_matches += 1
            elif FUZZY_AVAILABLE:
                # Try fuzzy match
                fuzzy_match, score = find_fuzzy_match(track.Title or "", title_to_file, args.fuzzy_threshold)
                if fuzzy_match:
                    new_filename = title_to_file[fuzzy_match]
                    match_type = "fuzzy"
                    fuzzy_score = score
                    fuzzy_original = fuzzy_match
                    fuzzy_matches += 1
                    fuzzy_match_details.append((track.Title, fuzzy_match, score))
                else:
                    no_matches += 1
                    no_match_details.append(track.Title)
            else:
                no_matches += 1
                no_match_details.append(track.Title)
            
            # Update track if we found a match
            if new_filename:
                new_folder_path = f"{args.flac_dir}/{new_filename}"
                
                # Check if paths need updating
                if (track.FileNameL != new_filename or 
                    track.FolderPath != new_folder_path):
                    
                    match_indicator = "🎯" if match_type == "exact" else "🔍"
                    print(f"\n{match_indicator} Updating: {track.Title}")
                    
                    if match_type == "fuzzy":
                        print(f"  Fuzzy matched to: {fuzzy_original} (score: {fuzzy_score:.3f})")
                    
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
    
    # Show fuzzy match details if requested
    if args.show_fuzzy and fuzzy_match_details:
        print(f"\n=== Fuzzy Matches (score >= {args.fuzzy_threshold}) ===")
        for original, matched, score in sorted(fuzzy_match_details, key=lambda x: x[2], reverse=True)[:20]:
            print(f"  {original} -> {matched} (score: {score:.3f})")
        if len(fuzzy_match_details) > 20:
            print(f"  ... and {len(fuzzy_match_details) - 20} more")
    
    # Show some no-match examples
    if no_match_details:
        print(f"\n=== No Matches Found (showing first 10) ===")
        for title in no_match_details[:10]:
            print(f"  {title}")
        if len(no_match_details) > 10:
            print(f"  ... and {len(no_match_details) - 10} more")
    
    if args.apply:
        # Commit changes
        db.session.commit()
        print(f"\n=== Final Summary ===")
        print(f"Total ALLDJ tracks: {total_alldj_tracks}")
        print(f"Exact matches: {exact_matches}")
        print(f"Fuzzy matches: {fuzzy_matches}")
        print(f"No matches: {no_matches}")
        print(f"Tracks updated: {updated_count}")
        print(f"\nDatabase updated successfully!")
        print(f"Backup available at: {backup_path}")
    else:
        print(f"\n=== Dry Run Summary ===")
        print(f"Total ALLDJ tracks: {total_alldj_tracks}")
        print(f"Exact matches: {exact_matches}")
        print(f"Fuzzy matches: {fuzzy_matches}")
        print(f"No matches: {no_matches}")
        print(f"Tracks that would be updated: {updated_count}")
        print(f"\nRun with --apply to make changes")
        print(f"Use --show-fuzzy to see fuzzy match details")
    
    db.close()

if __name__ == "__main__":
    main()

