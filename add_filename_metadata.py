#!/usr/bin/env python3
"""
Add filename-based metadata for files without TITLE/ARTIST metadata
"""

import argparse
import sys
import re
from pathlib import Path
from mutagen.flac import FLAC

def flush_print(msg):
    print(msg, flush=True)

def extract_clean_title_from_filename(filename):
    """Extract clean title from filename, removing prefix and suffix"""
    stem_name = Path(filename).stem
    
    # Remove _(Vocals) or _(Instrumental) suffix
    if stem_name.endswith('_(Vocals)'):
        stem_name = stem_name[:-9]
    elif stem_name.endswith('_(Instrumental)'):
        stem_name = stem_name[:-14]
    
    # Remove numeric prefix (e.g., "123_" at the start)
    stem_name = re.sub(r'^\d+_', '', stem_name)
    
    return stem_name

def add_filename_metadata(flac_file, dry_run=False):
    """Add filename-based metadata to FLAC file if it's missing TITLE/ARTIST"""
    try:
        flac = FLAC(flac_file)
        if not flac:
            return False, "Could not read FLAC file"
        
        # Check if it already has TITLE and ARTIST
        title = flac.get('TITLE')
        artist = flac.get('ARTIST')
        
        if title and artist:
            return False, "Already has complete metadata"
        
        # Extract clean title from filename
        clean_title = extract_clean_title_from_filename(flac_file.name)
        
        if dry_run:
            return True, f"Would set TITLE='{clean_title}', ARTIST='Unknown Artist'"
        
        # Set metadata
        flac['TITLE'] = [clean_title]
        flac['ARTIST'] = ['Unknown Artist']
        
        # Also set some basic defaults if missing
        if not flac.get('ALBUM'):
            flac['ALBUM'] = ['OG Separated Collection']
        
        flac.save()
        return True, f"Set TITLE='{clean_title}', ARTIST='Unknown Artist'"
        
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description='Add filename-based metadata for files missing TITLE/ARTIST')
    parser.add_argument('--target-dir', default='/Volumes/T7 Shield/3000AD/og_separated_v2',
                        help='Directory with FLAC files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    target_dir = Path(args.target_dir)
    if not target_dir.exists():
        flush_print(f"Error: Directory does not exist: {target_dir}")
        return 1
    
    # Get all FLAC files (skip hidden files)
    flac_files = [f for f in target_dir.glob('*.flac') if not f.name.startswith('._')]
    
    flush_print(f"Found {len(flac_files)} FLAC files")
    
    successful = 0
    failed = 0
    already_complete = 0
    
    for i, flac_file in enumerate(flac_files, 1):
        flush_print(f"[{i}/{len(flac_files)}] Processing: {flac_file.name}")
        
        success, message = add_filename_metadata(flac_file, args.dry_run)
        
        if success:
            if "Already has complete metadata" in message:
                already_complete += 1
                flush_print(f"  ✓ {message}")
            else:
                successful += 1
                flush_print(f"  ✓ {message}")
        else:
            if "Already has complete metadata" not in message:
                failed += 1
                flush_print(f"  ✗ {message}")
            else:
                already_complete += 1
                flush_print(f"  ✓ {message}")
    
    flush_print(f"\nSummary:")
    flush_print(f"  Updated with filename metadata: {successful}")
    flush_print(f"  Already had complete metadata: {already_complete}")
    flush_print(f"  Failed: {failed}")
    flush_print(f"  Total processed: {len(flac_files)}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())





