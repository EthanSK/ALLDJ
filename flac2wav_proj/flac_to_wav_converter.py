#!/usr/bin/env python3
import os
import json
import subprocess
import sys
from pathlib import Path

def convert_flac_to_wav_with_metadata(flac_path, wav_path):
    """Convert FLAC to WAV using ffmpeg with metadata preservation"""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    
    cmd = [
        'ffmpeg', '-i', flac_path,
        '-acodec', 'pcm_s16le',  # 16-bit PCM
        '-ar', '44100',          # 44.1kHz sample rate
        '-map_metadata', '0',    # Copy all metadata
        '-id3v2_version', '3',   # Use ID3v2.3 for better compatibility
        '-write_id3v1', '1',     # Also write ID3v1
        '-y',                    # Overwrite output file
        wav_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error converting {flac_path}: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Exception converting {flac_path}: {e}")
        return False

def process_directory(source_dir, dest_dir, mapping_dict, limit=None):
    """Process all FLAC files in a directory"""
    count = 0
    
    # Find all FLAC files excluding hidden files
    flac_files = []
    for root, dirs, files in os.walk(source_dir):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.endswith('.flac') and not file.startswith('.'):
                flac_files.append(os.path.join(root, file))
    
    print(f"Found {len(flac_files)} FLAC files in {source_dir}")
    
    for flac_path in flac_files:
        if limit and count >= limit:
            break
            
        # Create relative path structure
        rel_path = os.path.relpath(flac_path, source_dir)
        wav_filename = os.path.splitext(rel_path)[0] + '.wav'
        wav_path = os.path.join(dest_dir, wav_filename)
        
        print(f"Converting: {os.path.basename(flac_path)}")
        
        # Convert FLAC to WAV with metadata
        if convert_flac_to_wav_with_metadata(flac_path, wav_path):
            print(f"✓ Converted with metadata: {wav_filename}")
            # Add to mapping
            mapping_dict[flac_path] = wav_path
            count += 1
        else:
            print(f"✗ Failed to convert: {os.path.basename(flac_path)}")
    
    return count

def main():
    # Directory mappings
    directories = [
        ("/Volumes/T7 Shield/3000AD/og_separated_v2", "/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
        ("/Volumes/T7 Shield/3000AD/alldj_stem_separated", "/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
        ("/Volumes/T7 Shield/3000AD/flac_liked_songs", "/Volumes/T7 Shield/3000AD/wav_flac_liked_songs")
    ]
    
    # Initialize mapping dictionary
    flac_wav_mapping = {}
    
    # Process all files
    test_limit = None
    total_converted = 0
    
    print("Starting FLAC to WAV conversion for all files...")
    
    for source_dir, dest_dir in directories:
        if os.path.exists(source_dir):
            print(f"\nProcessing: {source_dir}")
            converted = process_directory(source_dir, dest_dir, flac_wav_mapping, limit=test_limit)
            total_converted += converted
        else:
            print(f"Directory not found: {source_dir}")
    
    # Save mapping to JSON
    mapping_file = "flac_to_wav_mapping.json"
    with open(mapping_file, 'w') as f:
        json.dump(flac_wav_mapping, f, indent=2)
    
    print(f"\nConversion complete! Converted {total_converted} files.")
    print(f"Mapping saved to: {mapping_file}")

if __name__ == "__main__":
    main()