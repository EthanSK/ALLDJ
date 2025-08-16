#!/usr/bin/env python3

"""
Create a mapping file between FLAC files and corresponding WAV files.
This will help with future playlist creation by providing a lookup table.
"""

import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from pyrekordbox import Rekordbox6Database, db6

def normalize_rb_path(folder: str, name: str) -> Path:
    """Convert Rekordbox DjmdContent folder/name into a local absolute Path."""
    folder = (folder or "").strip()
    name = (name or "").strip()
    name = unquote(name)
    
    if folder.startswith("file://"):
        parsed = urlparse(folder)
        path_str = parsed.path or folder[len("file://"):]
        folder_path = unquote(path_str)
    else:
        folder_path = unquote(folder)
    
    try:
        return Path(folder_path).resolve()
    except Exception:
        return Path(folder_path)

def map_to_wav_path(src_abs: Path) -> Path | None:
    """Map a source absolute path to the corresponding WAV absolute path."""
    s = str(src_abs)
    mappings = [
        ("/Volumes/T7 Shield/3000AD/alldj_stem_separated", "/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
        ("/Volumes/T7 Shield/3000AD/og_separated_v2", "/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
        ("/Volumes/T7 Shield/3000AD/flac_liked_songs", "/Volumes/T7 Shield/3000AD/wav_liked_songs"),
    ]
    
    for src_base, dst_base in mappings:
        if s.startswith(src_base):
            tail = s[len(src_base):]
            candidate = Path(dst_base + tail)
            if candidate.suffix.lower() != ".wav":
                candidate = candidate.with_suffix(".wav")
            return candidate
    
    return None

def main():
    print("🗂️  Creating FLAC to WAV mapping file")
    
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
    
    # Get all content from Rekordbox
    print("📋 Getting all tracks from Rekordbox...")
    SP = db6.tables.DjmdSongPlaylist
    CT = db6.tables.DjmdContent
    
    all_content = db.get_content().all()
    print(f"✅ Found {len(all_content)} total tracks")
    
    # Filter for FLAC files from our target directories
    target_dirs = [
        "/Volumes/T7 Shield/3000AD/alldj_stem_separated",
        "/Volumes/T7 Shield/3000AD/og_separated_v2", 
        "/Volumes/T7 Shield/3000AD/flac_liked_songs"
    ]
    
    flac_tracks = []
    for content in all_content:
        folder_path = getattr(content, 'FolderPath', '') or ''
        file_name = getattr(content, 'FileNameL', '') or getattr(content, 'FileNameS', '') or ''
        
        # Check if this is a FLAC file from our target directories
        for target_dir in target_dirs:
            if target_dir in folder_path and file_name.lower().endswith(('.flac', '.mp3', '.aiff', '.m4a')):
                flac_tracks.append(content)
                break
    
    print(f"📁 Found {len(flac_tracks)} FLAC/audio tracks from target directories")
    
    # Create mapping
    mapping = {
        "created_at": str(Path().resolve()),
        "total_flac_tracks": len(flac_tracks),
        "mappings": []
    }
    
    successful_mappings = 0
    missing_wavs = 0
    
    print("🔗 Creating FLAC to WAV mappings...")
    
    for i, content in enumerate(flac_tracks):
        if (i + 1) % 100 == 0:
            print(f"   Progress: {i+1}/{len(flac_tracks)}")
        
        folder_path = getattr(content, 'FolderPath', '') or ''
        file_name = getattr(content, 'FileNameL', '') or getattr(content, 'FileNameS', '') or ''
        title = getattr(content, 'Title', '') or ''
        
        # Create source path
        src_path = normalize_rb_path(folder_path, file_name)
        
        # Map to WAV path
        wav_path = map_to_wav_path(src_path)
        
        wav_exists = wav_path.exists() if wav_path else False
        
        if wav_exists:
            successful_mappings += 1
        else:
            missing_wavs += 1
        
        # Add to mapping
        mapping["mappings"].append({
            "flac_path": str(src_path),
            "wav_path": str(wav_path) if wav_path else None,
            "wav_exists": wav_exists,
            "title": title,
            "file_name": file_name,
            "folder_path": folder_path,
            "rekordbox_id": getattr(content, 'ID', None)
        })
    
    # Add statistics
    mapping["statistics"] = {
        "successful_mappings": successful_mappings,
        "missing_wavs": missing_wavs,
        "mapping_success_rate": f"{successful_mappings/len(flac_tracks)*100:.1f}%" if flac_tracks else "0%"
    }
    
    # Save mapping to file
    output_file = "flac_wav_mapping.json"
    print(f"\n💾 Saving mapping to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Mapping file created successfully!")
    print(f"\n📊 Mapping Statistics:")
    print(f"   Total FLAC tracks: {len(flac_tracks)}")
    print(f"   Successful mappings: {successful_mappings}")
    print(f"   Missing WAV files: {missing_wavs}")
    print(f"   Success rate: {successful_mappings/len(flac_tracks)*100:.1f}%")
    
    print(f"\n🎉 Mapping file saved as '{output_file}'")
    print("   You can now use this file to quickly find WAV equivalents of FLAC tracks!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())