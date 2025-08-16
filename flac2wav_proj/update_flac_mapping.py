#!/usr/bin/env python3

import json
import os
import re
from pathlib import Path
from mutagen.flac import FLAC
from mutagen.id3 import ID3NoHeaderError

def clean_title(title):
    """Clean title for comparison by removing common variations and normalizing"""
    if not title:
        return ""
    
    # Convert to lowercase and strip
    title = title.lower().strip()
    
    # Remove common patterns that might differ
    title = re.sub(r'\s*\(.*?\)\s*', '', title)  # Remove parentheses content
    title = re.sub(r'\s*\[.*?\]\s*', '', title)  # Remove bracket content
    title = re.sub(r'\s*feat\.?\s+.*$', '', title)  # Remove featuring info
    title = re.sub(r'\s*ft\.?\s+.*$', '', title)  # Remove ft. info
    title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
    
    return title.strip()

def extract_title_from_filename(filename):
    """Extract potential title from filename as fallback"""
    # Remove file extension
    title = os.path.splitext(filename)[0]
    
    # Remove common prefixes like track numbers
    title = re.sub(r'^\d+[\s_\-\.]*', '', title)
    
    return clean_title(title)

def get_flac_metadata(file_path):
    """Extract title from FLAC metadata"""
    try:
        audio = FLAC(file_path)
        
        # Try to get title from metadata
        title = None
        if audio and 'title' in audio:
            title = audio['title'][0] if audio['title'] else None
        
        # If no title in metadata, use filename
        if not title:
            title = extract_title_from_filename(os.path.basename(file_path))
        
        return clean_title(title)
    except Exception as e:
        print(f"Error reading FLAC metadata for {file_path}: {e}")
        # Fallback to filename
        return extract_title_from_filename(os.path.basename(file_path))

def main():
    # Load existing mapping
    mapping_file = "/Users/ethansarif-kattan/Music/ALLDJ/flac2wav_proj/flac_to_wav_mapping.json"
    
    print("Loading existing mapping...")
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)
    
    # Extract titles from existing WAV files in mapping
    print("Extracting titles from existing WAV files...")
    wav_titles = {}
    for flac_path, wav_path in mapping.items():
        # Extract title from WAV filename
        wav_filename = os.path.basename(wav_path)
        wav_title = extract_title_from_filename(wav_filename)
        if wav_title:
            wav_titles[wav_title] = wav_path
    
    print(f"Found {len(wav_titles)} unique WAV titles in existing mapping")
    
    # Get all FLAC files
    flac_dir = "/Users/ethansarif-kattan/Music/ALLDJ/flac"
    flac_files = list(Path(flac_dir).glob("*.flac"))
    
    print(f"Found {len(flac_files)} FLAC files to process")
    
    # Process FLAC files and find matches
    matches = []
    no_matches = []
    
    for flac_file in flac_files:
        flac_path = str(flac_file)
        
        # Skip if already in mapping
        if flac_path in mapping:
            print(f"Skipping {flac_file.name} - already in mapping")
            continue
        
        # Get FLAC title
        flac_title = get_flac_metadata(flac_path)
        
        if not flac_title:
            no_matches.append((flac_path, "No title found"))
            continue
        
        # Try to find matching WAV
        if flac_title in wav_titles:
            wav_path = wav_titles[flac_title]
            matches.append((flac_path, wav_path, flac_title))
            print(f"✓ Matched: {flac_file.name} -> {os.path.basename(wav_path)}")
        else:
            no_matches.append((flac_path, f"No match for title: {flac_title}"))
    
    print(f"\nResults:")
    print(f"Matches found: {len(matches)}")
    print(f"No matches: {len(no_matches)}")
    
    if matches:
        # Update mapping with new matches
        print(f"\nUpdating mapping with {len(matches)} new entries...")
        for flac_path, wav_path, title in matches:
            mapping[flac_path] = wav_path
        
        # Save updated mapping
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f, indent=2)
        
        print("✓ Mapping updated successfully!")
    
    if no_matches:
        print(f"\nFiles without matches:")
        for flac_path, reason in no_matches[:10]:  # Show first 10
            print(f"  - {os.path.basename(flac_path)}: {reason}")
        if len(no_matches) > 10:
            print(f"  ... and {len(no_matches) - 10} more")

if __name__ == "__main__":
    main()