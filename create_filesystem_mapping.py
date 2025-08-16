#!/usr/bin/env python3

"""
Create FLAC-WAV mapping by scanning filesystem directories directly.
Get FLAC files from original playlists, scan WAV directories, match by filename.
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

def find_best_wav_match(flac_path, wav_files, threshold=0.8):
    """Find the best matching WAV file for a FLAC file"""
    flac_name = clean_filename(Path(flac_path).name)
    
    best_match = None
    best_score = 0
    
    for wav_file in wav_files:
        wav_name = clean_filename(wav_file.name)
        score = similarity(flac_name, wav_name)
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = wav_file
    
    return best_match, best_score

def main():
    print("🗂️  Creating filesystem-based FLAC-WAV mapping")
    
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
    
    # Get target playlists
    target_playlists = ["ALLDJ Baked", "ALLDJ Stems", "OG Stems"]
    playlists = db.get_playlist().all()
    
    flac_files = set()
    
    print("📋 Getting FLAC files from target playlists...")
    for target_name in target_playlists:
        target_playlist = next((p for p in playlists if p.Name == target_name), None)
        if not target_playlist:
            print(f"⚠️  Playlist '{target_name}' not found")
            continue
            
        print(f"   Processing '{target_name}'...")
        
        # Get all tracks recursively from this playlist structure
        def get_tracks_recursive(playlist_id):
            tracks = set()
            
            # Get direct tracks from this playlist
            SP = db6.tables.DjmdSongPlaylist
            CT = db6.tables.DjmdContent
            
            direct_tracks = (
                db.session.query(SP, CT)
                .join(CT, CT.ID == SP.ContentID)
                .filter(SP.PlaylistID == playlist_id)
                .all()
            )
            
            for sp, ct in direct_tracks:
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
                    
                    tracks.add(flac_path)
            
            # Get tracks from child playlists/folders
            children = [p for p in playlists if getattr(p, 'ParentID', None) == playlist_id]
            for child in children:
                tracks.update(get_tracks_recursive(child.ID))
            
            return tracks
        
        playlist_tracks = get_tracks_recursive(target_playlist.ID)
        flac_files.update(playlist_tracks)
        print(f"   Found {len(playlist_tracks)} FLAC tracks")
    
    print(f"✅ Total unique FLAC files: {len(flac_files)}")
    
    # Scan WAV directories
    wav_dirs = [
        Path("/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
        Path("/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
        Path("/Volumes/T7 Shield/3000AD/wav_liked_songs")
    ]
    
    all_wav_files = []
    print("\n🔍 Scanning WAV directories...")
    
    for wav_dir in wav_dirs:
        if wav_dir.exists():
            wav_files = list(wav_dir.rglob("*.wav"))
            all_wav_files.extend(wav_files)
            print(f"   {wav_dir.name}: {len(wav_files)} WAV files")
        else:
            print(f"   ❌ {wav_dir} not found")
    
    print(f"✅ Total WAV files found: {len(all_wav_files)}")
    
    # Create mappings
    print("\n🔗 Creating FLAC→WAV mappings...")
    mappings = []
    matched = 0
    
    for i, flac_path in enumerate(sorted(flac_files)):
        if (i + 1) % 100 == 0:
            print(f"   Progress: {i+1}/{len(flac_files)}")
        
        wav_match, score = find_best_wav_match(flac_path, all_wav_files)
        
        if wav_match and wav_match.exists():
            mappings.append({
                "flac_path": flac_path,
                "wav_path": str(wav_match)
            })
            matched += 1
            if score < 0.95:  # Show uncertain matches
                print(f"   📋 {Path(flac_path).name} → {wav_match.name} (score: {score:.3f})")
    
    # Save mapping
    mapping_data = {
        "total_flac_files": len(flac_files),
        "total_wav_files": len(all_wav_files),
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
    print(f"   WAV files found: {len(all_wav_files)}")
    print(f"   Successful mappings: {matched}")
    print(f"   Success rate: {matched/len(flac_files)*100:.1f}%")
    print(f"   Output file: {output_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())