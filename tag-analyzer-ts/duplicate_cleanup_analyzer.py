#!/usr/bin/env python3
"""
Duplicate File Cleanup Analyzer

This script analyzes the music collection metadata and identifies which duplicate files
(files with numbers in parentheses) are not referenced in the metadata and can be safely deleted.
"""

import json
import os
from pathlib import Path

def load_metadata(metadata_path):
    """Load and parse the music collection metadata JSON file."""
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return None

def extract_filenames_from_metadata(metadata):
    """Extract all filenames from the metadata tracks array."""
    if not metadata or 'tracks' not in metadata:
        return set()
    
    filenames = set()
    for track in metadata['tracks']:
        if 'filename' in track:
            filenames.add(track['filename'])
    
    return filenames

def get_duplicate_files():
    """Return the list of duplicate files (with numbers in parentheses)."""
    duplicate_files = [
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Aline (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Aline (2).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Concrete Jungle (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Cooking Up Something Good (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Could Heaven Ever Be Like This (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Dark Fantasy (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Dog Days Are Over (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Flashing Lights (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Hallogallo (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Hector's House (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Lauren (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Lauren (2).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Lauren (3).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Leaf House (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 List Of People (To Try And Forget About) (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Lying Has To Stop (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Smile (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Sundown Syndrome (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 Virginia Tech (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 You & Me (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 You & Me (2).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 You've Got a Woman (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Anywhere but Here (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Call Me (feat. Maverick Sabre) (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Go Outside (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Guajira Con Arpa (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Guajira Con Arpa (2).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Heard 'Em Say (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Jack (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Lull (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Szerencsétlen (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-02 Where Or When (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-03 Didn't I (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-03 Golden Days (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-03 Heroes (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-03 No Diggity (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-03 Taking Out Time (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-04 Gleam (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-05 Hajnal (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-06 Ferry Lady (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-07 Baby Driver (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-07 California Girls (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-07 Smashing (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-07 Surfin' (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-07 Vidya (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-08 Szamár Madár (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-09 Drum N Bass (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-09 ili (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-09 Superego (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-10 Miss You (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-11 How Much A Dollar Cost (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-13 A Day in the Life (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-13 A Day In The Life (2).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-14 Gimme My Five (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-14 Gimme My Five (2).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-16 Hey Mama (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/01-18 Hey Ya! (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/02-04 Ignition (1).flac",
        "/Users/ethansarif-kattan/Music/ALLDJ/flac/02-10 Don't Matter To Me (1).flac"
    ]
    
    # Extract just the filenames from the full paths
    return [os.path.basename(path) for path in duplicate_files]

def check_file_exists(filepath):
    """Check if a file exists on the filesystem."""
    return os.path.exists(filepath)

def analyze_duplicates(metadata_path):
    """Main analysis function."""
    print("Duplicate File Cleanup Analyzer")
    print("=" * 50)
    print()
    
    # Load metadata
    print("Loading metadata...")
    metadata = load_metadata(metadata_path)
    if not metadata:
        return
    
    # Extract filenames from metadata
    print("Extracting filenames from metadata...")
    metadata_filenames = extract_filenames_from_metadata(metadata)
    print(f"Found {len(metadata_filenames)} files in metadata")
    
    # Get list of duplicate files
    duplicate_filenames = get_duplicate_files()
    print(f"Found {len(duplicate_filenames)} duplicate files to analyze")
    print()
    
    # Find which duplicates are referenced in metadata
    referenced_duplicates = []
    unreferenced_duplicates = []
    missing_referenced_files = []
    existing_unreferenced_files = []
    
    base_path = "/Users/ethansarif-kattan/Music/ALLDJ/flac"
    
    for duplicate_file in duplicate_filenames:
        full_path = os.path.join(base_path, duplicate_file)
        file_exists = check_file_exists(full_path)
        
        if duplicate_file in metadata_filenames:
            referenced_duplicates.append(duplicate_file)
            if not file_exists:
                missing_referenced_files.append(duplicate_file)
        else:
            unreferenced_duplicates.append(duplicate_file)
            if file_exists:
                existing_unreferenced_files.append(duplicate_file)
    
    # Display results
    print("ANALYSIS RESULTS:")
    print("=" * 50)
    print()
    
    print(f"✅ Referenced duplicates (in metadata - KEEP): {len(referenced_duplicates)}")
    if referenced_duplicates:
        for file in sorted(referenced_duplicates):
            full_path = os.path.join(base_path, file)
            exists = "✓" if check_file_exists(full_path) else "✗ MISSING"
            print(f"   - {file} [{exists}]")
    print()
    
    print(f"❌ Unreferenced duplicates (not in metadata): {len(unreferenced_duplicates)}")
    if unreferenced_duplicates:
        for file in sorted(unreferenced_duplicates):
            full_path = os.path.join(base_path, file)
            exists = "EXISTS - SAFE TO DELETE" if check_file_exists(full_path) else "ALREADY GONE"
            print(f"   - {file} [{exists}]")
    print()
    
    # Show files that actually need action
    if existing_unreferenced_files:
        print("🗑️  FILES THAT CAN BE DELETED (exist on disk but not in metadata):")
        print("-" * 70)
        for file in sorted(existing_unreferenced_files):
            print(f"   - {file}")
        print()
    
    if missing_referenced_files:
        print("⚠️  WARNING - REFERENCED FILES THAT ARE MISSING:")
        print("-" * 50)
        for file in sorted(missing_referenced_files):
            print(f"   - {file}")
        print("   These files are in your metadata but missing from disk!")
        print()
    
    # Generate deletion commands only for files that actually exist
    if existing_unreferenced_files:
        print("DELETION COMMANDS:")
        print("=" * 50)
        print("# Commands to delete unreferenced files that actually exist:")
        print()
        for file in sorted(existing_unreferenced_files):
            full_path = f"/Users/ethansarif-kattan/Music/ALLDJ/flac/{file}"
            print(f'rm "{full_path}"')
        print()
        
        # Create a shell script for existing files only
        script_path = "/Users/ethansarif-kattan/Music/ALLDJ/tag-analyzer-ts/delete_duplicates.sh"
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Script to delete unreferenced duplicate files\n")
            f.write("# Generated by duplicate_cleanup_analyzer.py\n\n")
            f.write("echo 'Deleting unreferenced duplicate files...'\n\n")
            for file in sorted(existing_unreferenced_files):
                full_path = f"/Users/ethansarif-kattan/Music/ALLDJ/flac/{file}"
                f.write(f'if [ -f "{full_path}" ]; then\n')
                f.write(f'  echo "Deleting: {file}"\n')
                f.write(f'  rm "{full_path}"\n')
                f.write(f'else\n')
                f.write(f'  echo "File not found (already deleted?): {file}"\n')
                f.write(f'fi\n\n')
            f.write("echo 'Deletion complete!'\n")
        
        os.chmod(script_path, 0o755)  # Make executable
        print(f"💾 Created deletion script: {script_path}")
        print("   Run with: ./delete_duplicates.sh")
    elif unreferenced_duplicates:
        print("ℹ️  No deletion needed - all unreferenced duplicate files are already gone!")
    
    print()
    print("SUMMARY:")
    print("-" * 30)
    print(f"Total duplicate files analyzed: {len(duplicate_filenames)}")
    print(f"Files in metadata (to keep): {len(referenced_duplicates)}")
    print(f"Files not in metadata: {len(unreferenced_duplicates)}")
    print(f"Files that can be deleted (exist but not referenced): {len(existing_unreferenced_files)}")
    print(f"Files missing from disk (referenced but gone): {len(missing_referenced_files)}")

if __name__ == "__main__":
    metadata_path = "/Users/ethansarif-kattan/Music/ALLDJ/music_collection_metadata.json"
    analyze_duplicates(metadata_path)