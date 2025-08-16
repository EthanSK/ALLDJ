#!/usr/bin/env python3
"""
Copy metadata from all_og_lossless (various formats) to og_separated_v2 FLAC files
"""

import argparse
import sys
import json
from pathlib import Path
from mutagen import File
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.aiff import AIFF
import difflib
import re
import subprocess

def flush_print(msg):
    print(msg, flush=True)

def normalize_title(title):
    """Normalize title for matching"""
    if not title:
        return ""
    
    # Convert to lowercase and remove extra spaces
    title = re.sub(r'\s+', ' ', title.strip().lower())
    
    # Remove common punctuation but preserve essential characters
    title = re.sub(r'[^\w\s\-\(\)\[\]&\']', '', title)
    
    # Remove common release descriptors
    descriptors = [
        r'\b(radio\s+edit|extended\s+mix|club\s+mix|original\s+mix|vocal\s+mix|instrumental)',
        r'\b(feat\.|featuring|ft\.|with)\s+[^)]*',
        r'\[edit\]|\(edit\)|\[remix\]|\(remix\)',
        r'\bsped\s+up\s+version\b',
        r'\bslowed\s+down\s+version\b'
    ]
    
    for desc in descriptors:
        title = re.sub(desc, '', title, flags=re.IGNORECASE)
    
    # Clean up extra spaces again
    title = re.sub(r'\s+', ' ', title.strip())
    
    return title

def extract_clean_track_name(stem_filename):
    """Extract clean track name from stem filename, removing prefix and suffix"""
    stem_name = Path(stem_filename).stem
    
    # Remove _(Vocals) or _(Instrumental) suffix
    if stem_name.endswith('_(Vocals)'):
        stem_name = stem_name[:-9]  # Remove _(Vocals)
    elif stem_name.endswith('_(Instrumental)'):
        stem_name = stem_name[:-14]  # Remove _(Instrumental)
    
    # Remove numeric prefix (e.g., "123_" at the start)
    stem_name = re.sub(r'^\d+_', '', stem_name)
    
    return stem_name

def find_matching_source(stem_file, source_dir):
    """Find matching source file for a stem file"""
    base_name = extract_clean_track_name(stem_file)
    
    # Look for matching files in source directory
    source_files = list(Path(source_dir).glob('*'))
    
    # First try exact match (ignoring extension)
    for source_file in source_files:
        if source_file.stem == base_name:
            return source_file
    
    # Try fuzzy matching with normalized titles
    normalized_base = normalize_title(base_name)
    best_match = None
    best_score = 0.0
    
    for source_file in source_files:
        normalized_source = normalize_title(source_file.stem)
        if normalized_source and normalized_base:
            score = difflib.SequenceMatcher(None, normalized_base, normalized_source).ratio()
            if score > best_score and score > 0.8:  # 80% similarity threshold
                best_score = score
                best_match = source_file
    
    return best_match

def find_metadata_in_json(track_name, json_file_path):
    """Find metadata for a track in music_collection_metadata.json"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        if 'tracks' in data:
            entries = data['tracks']
        elif isinstance(data, list):
            entries = data
        else:
            entries = []
        
        # Normalize the track name for matching
        normalized_track = normalize_title(track_name)
        
        # Search through all entries
        best_match = None
        best_score = 0.0
        
        for entry in entries:
            if 'TITLE' in entry:
                entry_title = normalize_title(entry['TITLE'])
                if entry_title:
                    score = difflib.SequenceMatcher(None, normalized_track, entry_title).ratio()
                    if score > best_score and score > 0.8:  # 80% similarity threshold
                        best_score = score
                        best_match = entry
        
        return best_match
    except Exception as e:
        flush_print(f"Error reading JSON metadata: {e}")
        return None

def copy_metadata_from_json(json_entry, target_file):
    """Copy metadata from JSON entry to target FLAC file"""
    try:
        target = FLAC(target_file)
        if not target:
            return False, f"Could not read target FLAC file: {target_file}"
        
        # Map JSON fields to FLAC tags
        json_to_flac_map = {
            'TITLE': 'TITLE',
            'ARTIST': 'ARTIST',
            'ALBUM': 'ALBUM',
            'ALBUMARTIST': 'ALBUMARTIST',
            'DATE': 'DATE',
            'GENRE': 'GENRE',
            'TRACKNUMBER': 'TRACKNUMBER',
            'DISCNUMBER': 'DISCNUMBER',
            'COMPOSER': 'COMPOSER'
        }
        
        updated = False
        for json_key, flac_tag in json_to_flac_map.items():
            if json_key in json_entry:
                value = json_entry[json_key]
                if value and str(value).strip():
                    target[flac_tag] = [str(value).strip()]
                    updated = True
        
        if updated:
            target.save()
            return True, "Metadata copied successfully (from JSON)"
        else:
            return False, "No usable metadata found in JSON"
            
    except Exception as e:
        return False, f"Error copying metadata from JSON: {str(e)}"

def copy_metadata_ffprobe(source_file, target_file):
    """Copy metadata using ffprobe as fallback for problematic WAV/AIFF files"""
    try:
        # Use ffprobe to extract metadata
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', str(source_file)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"ffprobe failed: {result.stderr}"
        
        import json
        data = json.loads(result.stdout)
        format_info = data.get('format', {})
        tags = format_info.get('tags', {})
        
        if not tags:
            return False, "No metadata found in source file"
        
        # Load target FLAC file
        target = FLAC(target_file)
        if not target:
            return False, f"Could not read target FLAC file: {target_file}"
        
        # Map common tag names to FLAC format
        tag_mapping = {
            'title': 'TITLE',
            'artist': 'ARTIST', 
            'album': 'ALBUM',
            'albumartist': 'ALBUMARTIST',
            'album_artist': 'ALBUMARTIST',
            'date': 'DATE',
            'year': 'DATE',
            'genre': 'GENRE',
            'track': 'TRACKNUMBER',
            'tracknumber': 'TRACKNUMBER',
            'disc': 'DISCNUMBER',
            'discnumber': 'DISCNUMBER',
            'composer': 'COMPOSER',
            'comment': 'COMMENT'
        }
        
        updated = False
        for source_tag, flac_tag in tag_mapping.items():
            if source_tag in tags:
                value = tags[source_tag]
                if value and str(value).strip():
                    target[flac_tag] = [str(value).strip()]
                    updated = True
        
        if updated:
            target.save()
            return True, "Metadata copied successfully (via ffprobe)"
        else:
            return False, "No usable metadata found"
            
    except Exception as e:
        return False, f"Error copying metadata via ffprobe: {str(e)}"

def copy_metadata(source_file, target_file):
    """Copy metadata from source to target FLAC file"""
    try:
        # Load target FLAC file
        target = FLAC(target_file)
        if not target:
            return False, f"Could not read target FLAC file: {target_file}"
        
        # Try different approaches based on file extension
        source_path = Path(source_file)
        ext = source_path.suffix.lower()
        
        # For WAV and AIFF files, try ffprobe first as it's more reliable
        if ext in ['.wav', '.aiff', '.aif']:
            success, message = copy_metadata_ffprobe(source_file, target_file)
            if success:
                return success, message
            # If ffprobe fails, fall back to mutagen
        
        # Try mutagen for all formats (original method)
        source = File(source_file)
        if not source:
            # If mutagen fails on WAV/AIFF, try ffprobe as final fallback
            if ext in ['.wav', '.aiff', '.aif']:
                return copy_metadata_ffprobe(source_file, target_file)
            return False, f"Could not read source file: {source_file}"
        
        # Metadata mapping for different source formats
        metadata_map = {
            # Standard tags
            'TITLE': ['TIT2', 'TITLE', '\xa9nam'],
            'ARTIST': ['TPE1', 'ARTIST', '\xa9ART'],
            'ALBUM': ['TALB', 'ALBUM', '\xa9alb'],
            'ALBUMARTIST': ['TPE2', 'ALBUMARTIST', 'aART'],
            'DATE': ['TDRC', 'DATE', '\xa9day'],
            'GENRE': ['TCON', 'GENRE', '\xa9gen'],
            'TRACKNUMBER': ['TRCK', 'TRACKNUMBER', 'trkn'],
            'DISCNUMBER': ['TPOS', 'DISCNUMBER', 'disk'],
            'COMPOSER': ['TCOM', 'COMPOSER', '\xa9wrt'],
            'COMMENT': ['COMM::eng', 'COMMENT', '\xa9cmt']
        }
        
        updated = False
        for flac_tag, source_tags in metadata_map.items():
            value = None
            
            # Try to get value from source using various tag names
            for tag in source_tags:
                if tag in source.tags:
                    raw_value = source.tags[tag]
                    if isinstance(raw_value, list):
                        value = str(raw_value[0]) if raw_value else None
                    else:
                        value = str(raw_value)
                    break
            
            # Set in target FLAC if we found a value
            if value and value.strip():
                target[flac_tag] = [value.strip()]
                updated = True
        
        if updated:
            target.save()
            return True, "Metadata copied successfully"
        else:
            return False, "No metadata found to copy"
            
    except Exception as e:
        # Final fallback for WAV/AIFF files
        if Path(source_file).suffix.lower() in ['.wav', '.aiff', '.aif']:
            return copy_metadata_ffprobe(source_file, target_file)
        return False, f"Error copying metadata: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description='Copy metadata from all_og_lossless to og_separated_v2 FLAC files')
    parser.add_argument('--source-dir', default='/Volumes/T7 Shield/3000AD/all_og_lossless',
                        help='Source directory with original files (various formats)')
    parser.add_argument('--target-dir', default='/Volumes/T7 Shield/3000AD/og_separated_v2',
                        help='Target directory with FLAC files')
    parser.add_argument('--json-file', default='music_collection_metadata.json',
                        help='JSON file with metadata fallback')
    parser.add_argument('--limit', type=int, help='Process only first N files (for testing)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    source_dir = Path(args.source_dir)
    target_dir = Path(args.target_dir)
    json_file = Path(args.json_file)
    
    if not source_dir.exists():
        flush_print(f"Error: Source directory does not exist: {source_dir}")
        return 1
    
    if not target_dir.exists():
        flush_print(f"Error: Target directory does not exist: {target_dir}")
        return 1
    
    if not json_file.exists():
        flush_print(f"Warning: JSON metadata file does not exist: {json_file}")
        json_file = None
    
    # Get all FLAC files in target directory (skip hidden files)
    flac_files = [f for f in target_dir.glob('*.flac') if not f.name.startswith('._')]
    if args.limit:
        flac_files = flac_files[:args.limit]
    
    flush_print(f"Found {len(flac_files)} FLAC files to process")
    
    successful = 0
    failed = 0
    no_match = 0
    json_fallback = 0
    
    for i, flac_file in enumerate(flac_files, 1):
        flush_print(f"[{i}/{len(flac_files)}] Processing: {flac_file.name}")
        
        # Find matching source file
        source_file = find_matching_source(flac_file, source_dir)
        
        if source_file:
            flush_print(f"  Matched with: {source_file.name}")
            
            if args.dry_run:
                flush_print(f"  [DRY RUN] Would copy metadata from {source_file.name}")
                successful += 1
            else:
                # Copy metadata from source file
                success, message = copy_metadata(source_file, flac_file)
                if success:
                    flush_print(f"  ✓ {message}")
                    successful += 1
                else:
                    flush_print(f"  ✗ {message}")
                    failed += 1
        else:
            # Try JSON fallback
            if json_file:
                clean_track_name = extract_clean_track_name(flac_file.name)
                flush_print(f"  No source file found, trying JSON fallback for: {clean_track_name}")
                
                json_entry = find_metadata_in_json(clean_track_name, json_file)
                if json_entry:
                    flush_print(f"  Found JSON metadata for: {json_entry.get('TITLE', 'Unknown')}")
                    
                    if args.dry_run:
                        flush_print(f"  [DRY RUN] Would copy metadata from JSON")
                        successful += 1
                    else:
                        success, message = copy_metadata_from_json(json_entry, flac_file)
                        if success:
                            flush_print(f"  ✓ {message}")
                            successful += 1
                            json_fallback += 1
                        else:
                            flush_print(f"  ✗ {message}")
                            failed += 1
                else:
                    flush_print(f"  No matching metadata found in JSON either")
                    no_match += 1
            else:
                flush_print(f"  No matching source file found and no JSON fallback available")
                no_match += 1
    
    flush_print(f"\nSummary:")
    flush_print(f"  Successful: {successful}")
    flush_print(f"  Failed: {failed}")
    flush_print(f"  No match: {no_match}")
    flush_print(f"  JSON fallback used: {json_fallback}")
    flush_print(f"  Total processed: {len(flac_files)}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
