#!/usr/bin/env python3

import mutagen
from pathlib import Path
import os

def check_wav_file(wav_path):
    """Check what metadata is available in a WAV file"""
    print(f"\n🔍 Checking: {wav_path.name}")
    print(f"File exists: {wav_path.exists()}")
    print(f"File size: {wav_path.stat().st_size if wav_path.exists() else 'N/A'} bytes")
    
    if not wav_path.exists():
        return
    
    try:
        # Try to read with mutagen
        audio = mutagen.File(str(wav_path))
        print(f"Mutagen file type: {type(audio)}")
        
        if audio is None:
            print("❌ Mutagen returned None - file format not supported or corrupted")
            return
            
        print(f"Audio info: {audio.info}")
        print(f"Tags available: {bool(audio.tags)}")
        
        if audio.tags:
            print(f"Tag type: {type(audio.tags)}")
            print(f"All tags: {dict(audio.tags)}")
        else:
            print("No tags found")
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")

def main():
    # Test a few WAV files from each directory
    wav_dirs = [
        "/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated",
        "/Volumes/T7 Shield/3000AD/wav_og_separated_v2", 
        "/Volumes/T7 Shield/3000AD/wav_liked_songs"
    ]
    
    for wav_dir in wav_dirs:
        print(f"\n📂 Testing files in: {wav_dir}")
        wav_path = Path(wav_dir)
        
        if not wav_path.exists():
            print(f"❌ Directory doesn't exist: {wav_dir}")
            continue
            
        # Get first 2 WAV files
        wav_files = list(wav_path.glob("*.wav"))[:2]
        
        for wav_file in wav_files:
            check_wav_file(wav_file)

if __name__ == "__main__":
    main()
