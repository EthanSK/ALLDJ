#!/usr/bin/env python3

"""
Create FLAC-WAV mapping by scanning filesystem directories directly (optimized).
"""

import json
import sys
from pathlib import Path
from urllib.parse import unquote
from pyrekordbox import Rekordbox6Database, db6
from difflib import SequenceMatcher
import re

def clean_filename(filename):
    """Clean filename for better matching"""
    # Remove extension
    name = Path(filename).stem
    # Remove common patterns
    name = re.sub(r'^\d+-\d+\s+', '', name)  # Remove "01-01 " patterns  
    name = re.sub(r'^\d+_', '', name)        # Remove "573_" patterns
    name = re.sub(r'_\(Vocals\)$', '', name)    # Remove "(Vocals)" suffix
    name = re.sub(r'_\(Instrumental\)$', '', name)  # Remove "(Instrumental)" suffix  
    name = re.sub(r'_\(Stems\)$', '', name)     # Remove "(Stems)" suffix
    return name.lower().strip()

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def main():
    print("🗂️  Creating optimized filesystem-based FLAC-WAV mapping")
    
    # First, scan all WAV files and build a lookup dict
    wav_dirs = [
        Path("/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
        Path("/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
        Path("/Volumes/T7 Shield/3000AD/wav_liked_songs")
    ]
    
    print("🔍 Scanning WAV directories...")
    wav_lookup = {}  # clean_name -> [wav_file_paths]
    total_wavs = 0
    
    for wav_dir in wav_dirs:
        if wav_dir.exists():
            print(f"   Scanning {wav_dir.name}...")
            wav_files = list(wav_dir.rglob("*.wav"))
            total_wavs += len(wav_files)
            
            for wav_file in wav_files:
                clean_name = clean_filename(wav_file.name)
                if clean_name not in wav_lookup:
                    wav_lookup[clean_name] = []
                wav_lookup[clean_name].append(wav_file)
            
            print(f"   Found {len(wav_files)} WAV files")
        else:
            print(f"   ❌ {wav_dir} not found")
    
    print(f"✅ Total WAV files: {total_wavs}")
    print(f"✅ Unique clean names: {len(wav_lookup)}")
    
    # Connect to Rekordbox to get playlist tracks  
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
    
    # Get target playlists - only top level, not recursive to speed up
    target_playlists = ["ALLDJ Baked", "ALLDJ Stems", "OG Stems"]
    playlists = db.get_playlist().all()
    
    flac_files = set()
    
    print("📋 Getting FLAC files from target playlists...")
    SP = db6.tables.DjmdSongPlaylist
    CT = db6.tables.DjmdContent
    
    for target_name in target_playlists:
        target_playlist = next((p for p in playlists if p.Name == target_name), None)
        if not target_playlist:
            print(f"⚠️  Playlist '{target_name}' not found")
            continue
        
        print(f"   Processing '{target_name}'...")
        
        # Get all child playlist IDs 
        child_ids = []
        def collect_child_ids(parent_id):
            children = [p for p in playlists if getattr(p, 'ParentID', None) == parent_id]
            for child in children:
                child_ids.append(child.ID)
                collect_child_ids(child.ID)
        
        child_ids.append(target_playlist.ID)
        collect_child_ids(target_playlist.ID)
        
        # Get all tracks from these playlists in one query
        tracks = (
            db.session.query(SP, CT)
            .join(CT, CT.ID == SP.ContentID)
            .filter(SP.PlaylistID.in_(child_ids))
            .all()
        )
        
        playlist_flacs = 0
        for sp, ct in tracks:
            folder_path = getattr(ct, 'FolderPath', '') or ''
            file_name = getattr(ct, 'FileNameL', '') or getattr(ct, 'FileNameS', '') or ''
            
            if file_name.lower().endswith('.flac'):
                # Construct full path
                if folder_path.startswith('file://'):
                    folder_path = unquote(folder_path[7:])
                else:
                    folder_path = unquote(folder_path)
                
                if folder_path.endswith(file_name):
                    flac_path = folder_path
                else:
                    flac_path = str(Path(folder_path) / file_name)
                
                flac_files.add(flac_path)
                playlist_flacs += 1
        
        print(f"   Found {playlist_flacs} FLAC tracks")
    
    print(f"✅ Total unique FLAC files: {len(flac_files)}")
    
    # Create mappings using the lookup
    print("\n🔗 Creating FLAC→WAV mappings...")
    mappings = []
    matched = 0
    
    for flac_path in sorted(flac_files):
        flac_clean = clean_filename(Path(flac_path).name)
        
        # Direct match first
        if flac_clean in wav_lookup:
            # Take the first matching WAV file
            wav_file = wav_lookup[flac_clean][0]
            if wav_file.exists():
                mappings.append({
                    "flac_path": flac_path,
                    "wav_path": str(wav_file)
                })
                matched += 1
                continue
        
        # Fuzzy match if no direct match
        best_match = None
        best_score = 0.8  # threshold
        
        for clean_name, wav_files in wav_lookup.items():
            score = similarity(flac_clean, clean_name)
            if score > best_score:
                best_score = score
                best_match = wav_files[0]
        
        if best_match and best_match.exists():
            mappings.append({
                "flac_path": flac_path,
                "wav_path": str(best_match)
            })
            matched += 1
            print(f"   📋 {Path(flac_path).name} → {best_match.name} (score: {best_score:.3f})")
    
    # Save mapping
    mapping_data = {
        "total_flac_files": len(flac_files),
        "total_wav_files": total_wavs,
        "successful_mappings": matched,
        "mappings": mappings
    }
    
    output_file = "flac_wav_mapping_filesystem.json"
    print(f"\n💾 Saving mapping to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Filesystem mapping created!")
    print(f"📊 Results:")
    print(f"   FLAC files from playlists: {len(flac_files)}")
    print(f"   WAV files found: {total_wavs}")
    print(f"   Successful mappings: {matched}")
    print(f"   Success rate: {matched/len(flac_files)*100:.1f}%")
    print(f"   Output file: {output_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())