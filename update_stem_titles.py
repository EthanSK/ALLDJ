#!/usr/bin/env python3
"""
Add (Vocals) or (Instrumental) suffix to TITLE metadata for stem files
"""

import argparse
import sys
from pathlib import Path
from mutagen.flac import FLAC

def flush_print(msg):
    print(msg, flush=True)

def update_stem_title(flac_file, dry_run=False):
    """Add (Vocals) or (Instrumental) suffix to TITLE metadata"""
    try:
        flac = FLAC(flac_file)
        if not flac:
            return False, "Could not read FLAC file"
        
        current_title = flac.get('TITLE')
        if not current_title:
            return False, "No TITLE metadata found"
        
        current_title = current_title[0] if isinstance(current_title, list) else current_title
        
        # Determine suffix based on filename
        if '_(Vocals).flac' in flac_file.name:
            suffix = " (Vocals)"
        elif '_(Instrumental).flac' in flac_file.name:
            suffix = " (Instrumental)"
        else:
            return False, "Could not determine stem type from filename"
        
        # Check if suffix already exists
        if current_title.endswith(suffix):
            return False, f"Title already has {suffix} suffix"
        
        # Create new title
        new_title = current_title + suffix
        
        if dry_run:
            return True, f"Would change title: '{current_title}' -> '{new_title}'"
        
        # Update metadata
        flac['TITLE'] = [new_title]
        flac.save()
        
        return True, f"Updated title: '{current_title}' -> '{new_title}'"
        
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description='Add (Vocals)/(Instrumental) suffix to TITLE metadata')
    parser.add_argument('--stems-dir', default='/Volumes/T7 Shield/3000AD/alldj_stem_separated',
                        help='Directory with stem files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--limit', type=int, help='Limit to first N files for testing')
    
    args = parser.parse_args()
    
    stems_dir = Path(args.stems_dir)
    if not stems_dir.exists():
        flush_print(f"Error: Directory does not exist: {stems_dir}")
        return 1
    
    # Get all FLAC files (skip hidden files)
    flac_files = [f for f in stems_dir.glob('*.flac') if not f.name.startswith('._')]
    
    if args.limit:
        flac_files = flac_files[:args.limit]
    
    flush_print(f"Found {len(flac_files)} FLAC files to process")
    
    if args.dry_run:
        flush_print("DRY RUN MODE - No changes will be made")
    
    successful = 0
    failed = 0
    skipped = 0
    
    for i, flac_file in enumerate(flac_files, 1):
        flush_print(f"[{i}/{len(flac_files)}] Processing: {flac_file.name}")
        
        success, message = update_stem_title(flac_file, args.dry_run)
        
        if success:
            if "already has" in message:
                skipped += 1
                flush_print(f"  ⏭️  {message}")
            else:
                successful += 1
                flush_print(f"  ✅ {message}")
        else:
            if "already has" in message:
                skipped += 1
                flush_print(f"  ⏭️  {message}")
            else:
                failed += 1
                flush_print(f"  ❌ {message}")
    
    flush_print(f"\n📊 Summary:")
    flush_print(f"  Updated: {successful}")
    flush_print(f"  Skipped (already had suffix): {skipped}")
    flush_print(f"  Failed: {failed}")
    flush_print(f"  Total processed: {len(flac_files)}")
    
    if args.dry_run:
        flush_print(f"\n💡 Run without --dry-run to apply changes")
    elif successful > 0:
        flush_print(f"\n✅ Successfully updated {successful} track titles!")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())





