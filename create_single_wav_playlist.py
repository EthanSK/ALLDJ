#!/usr/bin/env python3

"""
Create a single test WAV playlist with proper folder structure.
Uses existing WAV files from the wav_* directories.
"""

import sys
from pathlib import Path
from pyrekordbox import Rekordbox6Database

def main():
    print("🎵 Creating single WAV test playlist with 5 tracks")
    
    # Get 5 WAV files from our directories
    wav_dirs = [
        Path("/Volumes/T7 Shield/3000AD/wav_liked_songs"),
        Path("/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"), 
        Path("/Volumes/T7 Shield/3000AD/wav_og_separated_v2")
    ]
    
    wav_files = []
    for wav_dir in wav_dirs:
        if wav_dir.exists():
            files = [f for f in wav_dir.glob("*.wav") if not f.name.startswith("._")][:2]
            wav_files.extend(files)
            print(f"📂 Found {len(files)} files in {wav_dir.name}")
            if len(wav_files) >= 5:
                break
    
    wav_files = wav_files[:5]  # Limit to 5
    
    if not wav_files:
        print("❌ No WAV files found")
        return 1
    
    print(f"✅ Selected {len(wav_files)} WAV files:")
    for i, f in enumerate(wav_files, 1):
        print(f"   {i}. {f.name}")
    
    # Connect to Rekordbox
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6", 
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    db_dir = next((p for p in db_paths if p.exists()), None)
    if db_dir is None:
        print("❌ Rekordbox database not found")
        return 1
    
    print(f"📂 Connected to: {db_dir}")
    db = Rekordbox6Database(db_dir=str(db_dir))
    
    # Create folder structure
    print("\n📁 Creating folder structure...")
    
    # Create 'wav' root folder
    playlists = db.get_playlist().all()
    wav_parent = next((p for p in playlists if p.Name == "wav" and not getattr(p, 'ParentID', None)), None)
    
    if not wav_parent:
        try:
            wav_parent = db.create_playlist_folder("wav")
            print("   ✓ Created 'wav' root folder")
        except Exception as e:
            print(f"   ❌ Error creating wav folder: {e}")
            return 1
    else:
        print("   ✓ Found existing 'wav' root folder")
    
    # Create test playlist directly under wav
    test_name = "WAV Test - 5 Files"
    
    # Delete existing if present
    existing = next((p for p in playlists if p.Name == test_name and getattr(p, 'ParentID', None) == wav_parent.ID), None)
    if existing:
        try:
            db.delete_playlist(existing)
            print("   ✓ Deleted existing test playlist")
        except Exception as e:
            print(f"   ⚠️  Could not delete existing playlist: {e}")
    
    try:
        test_playlist = db.create_playlist(test_name, parent=wav_parent)
        print(f"   ✓ Created 'wav/{test_name}' playlist")
    except Exception as e:
        print(f"   ❌ Error creating playlist: {e}")
        return 1
    
    # Add WAV files to playlist
    print(f"\n🎵 Adding {len(wav_files)} WAV files:")
    successful = 0
    
    for i, wav_file in enumerate(wav_files, 1):
        try:
            print(f"  {i}. Adding: {wav_file.name}")
            
            # Check if already in Rekordbox
            content = db.get_content(FolderPath=str(wav_file)).first()
            if not content:
                print(f"      → Importing to Rekordbox...")
                content = db.add_content(str(wav_file))
            else:
                print(f"      → Already in Rekordbox")
            
            if content:
                db.add_to_playlist(test_playlist, content)
                print(f"      ✅ Added successfully")
                successful += 1
            else:
                print(f"      ❌ Failed to import")
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    print(f"\n📊 Results: {successful}/{len(wav_files)} tracks added successfully")
    
    if successful > 0:
        # Commit changes
        print("\n💾 Committing changes...")
        try:
            db.commit()
            print("✅ SUCCESS! Changes committed to Rekordbox database!")
            print(f"\n🎉 Check Rekordbox for playlist: wav/{test_name}")
            print(f"   Should contain {successful} WAV tracks")
            return 0
        except Exception as e:
            print(f"❌ Commit failed: {e}")
            return 1
    else:
        print("❌ No tracks were successfully added")
        return 1

if __name__ == "__main__":
    sys.exit(main())
