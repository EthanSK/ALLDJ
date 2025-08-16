#!/usr/bin/env python3

"""
Simple script to copy the "remaster Baked" playlist to wav structure with WAV files.
Creates: wav/ALLDJ Baked/Version Type Baked/remaster Baked
"""

import json
import sys
from pathlib import Path
from pyrekordbox import Rekordbox6Database, db6

def main():
    print("🎵 Creating wav/ALLDJ Baked/Version Type Baked/remaster Baked playlist")
    
    # Load filesystem mapping (direct filesystem scan)
    mapping_file = "flac_wav_mapping_filesystem.json"
    if not Path(mapping_file).exists():
        print(f"❌ {mapping_file} not found")
        return 1
    
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    # Create mapping dict for fast lookup
    flac_to_wav = {}
    for mapping in mapping_data['mappings']:
        flac_path = mapping['flac_path']
        wav_path = mapping['wav_path']
        if flac_path and wav_path:
            flac_to_wav[flac_path] = wav_path
    
    print(f"✅ Loaded {len(flac_to_wav)} FLAC→WAV mappings")
    
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
    
    # Get all playlists
    playlists = db.get_playlist().all()
    
    # Find original "remaster Baked" playlist
    original_remaster = None
    for playlist in playlists:
        if playlist.Name == "remaster Baked":
            original_remaster = playlist
            break
    
    if not original_remaster:
        print("❌ Original 'remaster Baked' playlist not found")
        return 1
    
    print("✅ Found original 'remaster Baked' playlist")
    
    # Get tracks from original playlist
    SP = db6.tables.DjmdSongPlaylist
    CT = db6.tables.DjmdContent
    
    tracks = (
        db.session.query(SP, CT)
        .join(CT, CT.ID == SP.ContentID)
        .filter(SP.PlaylistID == original_remaster.ID)
        .all()
    )
    
    print(f"📋 Found {len(tracks)} tracks in original playlist")
    
    # Analyze tracks and find WAV mappings
    wav_tracks = []
    missing_wavs = []
    
    for sp, ct in tracks:
        # Get FLAC file path
        folder_path = getattr(ct, 'FolderPath', '') or ''
        file_name = getattr(ct, 'FileNameL', '') or getattr(ct, 'FileNameS', '') or ''
        title = getattr(ct, 'Title', '') or file_name
        
        # Try to construct FLAC path (handle URL encoding)
        from urllib.parse import unquote
        folder_path = unquote(folder_path) if folder_path.startswith('file://') else folder_path
        
        # Remove file:// prefix if present
        if folder_path.startswith('file://'):
            folder_path = folder_path[7:]
        
        # Handle the case where folder_path might already include filename
        if folder_path.endswith(file_name):
            flac_path = folder_path
        else:
            flac_path = str(Path(folder_path) / file_name) if folder_path else file_name
        
        # Look up WAV mapping
        if flac_path in flac_to_wav:
            wav_path = Path(flac_to_wav[flac_path])
            if wav_path.exists():
                wav_tracks.append((title, wav_path, flac_path))
                print(f"   ✅ {title} → {wav_path.name}")
            else:
                missing_wavs.append((title, flac_path, str(wav_path)))
                print(f"   ❌ {title} → WAV not found: {wav_path}")
        else:
            missing_wavs.append((title, flac_path, "No mapping"))
            print(f"   ⚠️  {title} → No mapping for: {flac_path}")
    
    print(f"\n📊 Analysis:")
    print(f"   WAV files found: {len(wav_tracks)}")
    print(f"   Missing/unmapped: {len(missing_wavs)}")
    
    if not wav_tracks:
        print("❌ No WAV files found - cannot create playlist")
        return 1
    
    # Create folder structure
    print(f"\n📁 Creating folder structure...")
    
    # Get or create wav parent
    wav_parent = next((p for p in playlists if p.Name == "wav"), None)
    if not wav_parent:
        wav_parent = db.create_playlist_folder("wav")
        print("   ✓ Created 'wav' folder")
    else:
        print("   ✓ Found 'wav' folder")
    
    # Get or create ALLDJ Baked under wav
    alldj_baked = next((p for p in playlists 
                       if p.Name == "ALLDJ Baked" and getattr(p, 'ParentID', None) == wav_parent.ID), None)
    if not alldj_baked:
        alldj_baked = db.create_playlist_folder("ALLDJ Baked", parent=wav_parent)
        print("   ✓ Created 'wav/ALLDJ Baked' folder")
    else:
        print("   ✓ Found 'wav/ALLDJ Baked' folder")
    
    # Get or create Version Type Baked under ALLDJ Baked
    version_type = next((p for p in playlists 
                        if p.Name == "Version Type Baked" and getattr(p, 'ParentID', None) == alldj_baked.ID), None)
    if not version_type:
        version_type = db.create_playlist_folder("Version Type Baked", parent=alldj_baked)
        print("   ✓ Created 'wav/ALLDJ Baked/Version Type Baked' folder")
    else:
        print("   ✓ Found 'wav/ALLDJ Baked/Version Type Baked' folder")
    
    # Delete existing remaster Baked if present
    existing_remaster = next((p for p in playlists 
                             if p.Name == "remaster Baked" and getattr(p, 'ParentID', None) == version_type.ID), None)
    if existing_remaster:
        db.delete_playlist(existing_remaster)
        print("   ✓ Deleted existing 'remaster Baked' playlist")
    
    # Create remaster Baked playlist
    wav_remaster = db.create_playlist("remaster Baked", parent=version_type)
    print("   ✓ Created 'wav/ALLDJ Baked/Version Type Baked/remaster Baked' playlist")
    
    # Add WAV tracks
    print(f"\n🎵 Adding {len(wav_tracks)} WAV tracks...")
    added_count = 0
    
    for title, wav_path, flac_path in wav_tracks:
        try:
            # Import or get WAV track
            content = db.get_content(FolderPath=str(wav_path)).first()
            if not content:
                content = db.add_content(str(wav_path))
            
            if content:
                # Set title if different from filename
                if title and title != wav_path.stem:
                    try:
                        setattr(content, 'Title', title)
                    except:
                        pass
                
                db.add_to_playlist(wav_remaster, content)
                added_count += 1
                print(f"   ✅ Added: {title}")
            else:
                print(f"   ❌ Failed to import: {title}")
                
        except Exception as e:
            print(f"   ❌ Error adding {title}: {e}")
    
    print(f"\n📊 Results: {added_count}/{len(wav_tracks)} tracks added successfully")
    
    # Commit changes
    if added_count > 0:
        print(f"\n💾 Committing changes...")
        try:
            db.commit()
            print("✅ SUCCESS! WAV remaster Baked playlist created and committed!")
            print(f"\n🎉 Check Rekordbox for:")
            print(f"   📁 wav/ALLDJ Baked/Version Type Baked/remaster Baked")
            print(f"   🎵 {added_count} WAV tracks")
            return 0
        except Exception as e:
            print(f"❌ Commit failed: {e}")
            return 1
    else:
        print("❌ No tracks were successfully added")
        return 1

if __name__ == "__main__":
    sys.exit(main())