#!/usr/bin/env python3
"""
Enhanced metadata matcher for OG separated files with better fuzzy search
"""

import argparse
import sys
import json
from pathlib import Path
from mutagen import File
from mutagen.flac import FLAC
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
        r'\bslowed\s+down\s+version\b',
        r'\bv\d+\s*\(\d+\)',  # Remove version numbers like "v3 (1)"
        r'\(\d+\)$',  # Remove trailing numbers in parentheses
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
        stem_name = stem_name[:-9]
    elif stem_name.endswith('_(Instrumental)'):
        stem_name = stem_name[:-14]
    
    # Remove numeric prefix (e.g., "123_" at the start)
    stem_name = re.sub(r'^\d+_', '', stem_name)
    
    return stem_name

def get_word_tokens(text):
    """Extract word tokens from text for token-based matching"""
    if not text:
        return set()
    
    # Split on non-alphanumeric characters and filter out short tokens
    tokens = re.findall(r'\w+', text.lower())
    return set(token for token in tokens if len(token) > 2)

def calculate_match_scores(track_name, source_files):
    """Calculate multiple types of match scores for a track"""
    normalized_track = normalize_title(track_name)
    track_tokens = get_word_tokens(track_name)
    
    matches = []
    
    for source_file in source_files:
        source_stem = source_file.stem
        normalized_source = normalize_title(source_stem)
        source_tokens = get_word_tokens(source_stem)
        
        # 1. Exact match (highest priority)
        exact_score = 1.0 if normalized_track == normalized_source else 0.0
        
        # 2. String similarity
        string_score = difflib.SequenceMatcher(None, normalized_track, normalized_source).ratio()
        
        # 3. Token overlap (Jaccard similarity)
        if track_tokens and source_tokens:
            intersection = track_tokens & source_tokens
            union = track_tokens | source_tokens
            token_score = len(intersection) / len(union) if union else 0.0
        else:
            token_score = 0.0
        
        # 4. Substring matching (check if one is contained in the other)
        substring_score = 0.0
        if normalized_track in normalized_source or normalized_source in normalized_track:
            substring_score = 0.8
        
        # 5. Starting words match
        track_words = normalized_track.split()
        source_words = normalized_source.split()
        start_match_score = 0.0
        if track_words and source_words:
            # Check how many starting words match
            matching_start_words = 0
            for i, (tw, sw) in enumerate(zip(track_words, source_words)):
                if tw == sw:
                    matching_start_words += 1
                else:
                    break
            if matching_start_words > 0:
                start_match_score = matching_start_words / max(len(track_words), len(source_words))
        
        # Combined score (weighted average)
        combined_score = (
            exact_score * 1.0 +
            string_score * 0.4 +
            token_score * 0.3 +
            substring_score * 0.2 +
            start_match_score * 0.3
        ) / 2.2
        
        matches.append({
            'file': source_file,
            'exact': exact_score,
            'string': string_score,
            'token': token_score,
            'substring': substring_score,
            'start_match': start_match_score,
            'combined': combined_score,
            'normalized_source': normalized_source
        })
    
    # Sort by combined score (descending)
    matches.sort(key=lambda x: x['combined'], reverse=True)
    
    return matches

def copy_metadata_smart(source_file, target_file):
    """Smart metadata copying with multiple fallback methods"""
    try:
        target = FLAC(target_file)
        if not target:
            return False, f"Could not read target FLAC file: {target_file}"
        
        source_path = Path(source_file)
        ext = source_path.suffix.lower()
        
        # Try ffprobe first for WAV/AIFF
        if ext in ['.wav', '.aiff', '.aif']:
            try:
                cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(source_file)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    tags = data.get('format', {}).get('tags', {})
                    
                    if tags:
                        tag_mapping = {
                            'title': 'TITLE', 'artist': 'ARTIST', 'album': 'ALBUM',
                            'albumartist': 'ALBUMARTIST', 'album_artist': 'ALBUMARTIST',
                            'date': 'DATE', 'year': 'DATE', 'genre': 'GENRE',
                            'track': 'TRACKNUMBER', 'tracknumber': 'TRACKNUMBER',
                            'disc': 'DISCNUMBER', 'discnumber': 'DISCNUMBER',
                            'composer': 'COMPOSER', 'comment': 'COMMENT'
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
            except Exception:
                pass  # Fall through to mutagen
        
        # Try mutagen
        source = File(source_file)
        if source and source.tags:
            metadata_map = {
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
                for tag in source_tags:
                    if tag in source.tags:
                        raw_value = source.tags[tag]
                        value = str(raw_value[0] if isinstance(raw_value, list) else raw_value)
                        if value and value.strip():
                            target[flac_tag] = [value.strip()]
                            updated = True
                        break
            
            if updated:
                target.save()
                return True, "Metadata copied successfully"
        
        return False, "No metadata found in source file"
        
    except Exception as e:
        return False, f"Error copying metadata: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description='Enhanced OG metadata matcher with better fuzzy search')
    parser.add_argument('--source-dir', default='/Volumes/T7 Shield/3000AD/all_og_lossless',
                        help='Source directory with original files')
    parser.add_argument('--target-dir', default='/Volumes/T7 Shield/3000AD/og_separated_v2',
                        help='Target directory with FLAC files')
    parser.add_argument('--min-score', type=float, default=0.3,
                        help='Minimum match score to consider (0.0-1.0)')
    parser.add_argument('--show-matches', type=int, default=3,
                        help='Number of top matches to show for assessment')
    parser.add_argument('--auto-threshold', type=float, default=0.8,
                        help='Auto-apply matches above this threshold')
    parser.add_argument('--dry-run', action='store_true', help='Show matches without applying')
    parser.add_argument('--unmatched-only', action='store_true', help='Only process previously unmatched files')
    
    args = parser.parse_args()
    
    source_dir = Path(args.source_dir)
    target_dir = Path(args.target_dir)
    
    if not source_dir.exists() or not target_dir.exists():
        flush_print(f"Error: Directories don't exist")
        return 1
    
    # Get source files
    source_files = list(source_dir.glob('*'))
    source_files = [f for f in source_files if f.is_file() and not f.name.startswith('.')]
    
    # Get target FLAC files
    flac_files = [f for f in target_dir.glob('*.flac') if not f.name.startswith('._')]
    
    flush_print(f"Found {len(source_files)} source files and {len(flac_files)} FLAC files")
    
    # Filter to unmatched files if requested
    if args.unmatched_only:
        # Check which files already have metadata
        unmatched_files = []
        for flac_file in flac_files:
            try:
                flac = FLAC(flac_file)
                if not flac or not flac.get('TITLE') or not flac.get('ARTIST'):
                    unmatched_files.append(flac_file)
            except:
                unmatched_files.append(flac_file)
        flac_files = unmatched_files
        flush_print(f"Processing {len(flac_files)} unmatched files")
    
    successful = 0
    failed = 0
    skipped = 0
    
    for i, flac_file in enumerate(flac_files, 1):
        clean_name = extract_clean_track_name(flac_file.name)
        flush_print(f"\n[{i}/{len(flac_files)}] Processing: {flac_file.name}")
        flush_print(f"  Clean name: '{clean_name}'")
        
        # Calculate match scores
        matches = calculate_match_scores(clean_name, source_files)
        
        if not matches or matches[0]['combined'] < args.min_score:
            flush_print(f"  No matches above threshold {args.min_score}")
            failed += 1
            continue
        
        # Show top matches
        flush_print(f"  Top {min(args.show_matches, len(matches))} matches:")
        for j, match in enumerate(matches[:args.show_matches]):
            flush_print(f"    {j+1}. {match['file'].name} (score: {match['combined']:.3f})")
            flush_print(f"       String: {match['string']:.3f}, Token: {match['token']:.3f}, "
                       f"Substring: {match['substring']:.3f}, Start: {match['start_match']:.3f}")
        
        best_match = matches[0]
        
        if best_match['combined'] >= args.auto_threshold:
            # Auto-apply high-confidence matches
            if args.dry_run:
                flush_print(f"  [DRY RUN] Would auto-apply: {best_match['file'].name}")
                successful += 1
            else:
                success, message = copy_metadata_smart(best_match['file'], flac_file)
                if success:
                    flush_print(f"  ✓ Auto-applied: {message}")
                    successful += 1
                else:
                    flush_print(f"  ✗ Failed: {message}")
                    failed += 1
        else:
            # Ask for manual confirmation for lower-confidence matches
            if not args.dry_run:
                response = input(f"  Apply match '{best_match['file'].name}'? (y/n/s=skip): ").strip().lower()
                if response == 'y':
                    success, message = copy_metadata_smart(best_match['file'], flac_file)
                    if success:
                        flush_print(f"  ✓ Applied: {message}")
                        successful += 1
                    else:
                        flush_print(f"  ✗ Failed: {message}")
                        failed += 1
                elif response == 's':
                    flush_print(f"  Skipped")
                    skipped += 1
                else:
                    flush_print(f"  Rejected")
                    failed += 1
            else:
                flush_print(f"  [DRY RUN] Would ask for confirmation")
                skipped += 1
    
    flush_print(f"\nSummary:")
    flush_print(f"  Successful: {successful}")
    flush_print(f"  Failed: {failed}")
    flush_print(f"  Skipped: {skipped}")
    flush_print(f"  Total processed: {len(flac_files)}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())





