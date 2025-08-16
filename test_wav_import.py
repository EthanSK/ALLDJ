#!/usr/bin/env python3

"""
Test WAV file mapping and playlist creation with proper folder structure.
Creates a test playlist with 5 WAV files under wav/ALLDJ Baked/ folder.
"""

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
    
    if folder_path and not folder_path.endswith("/"):
        folder_path += "/"
    
    if folder_path.endswith("/" + name):
        full = folder_path
    else:
        full = folder_path + name
    
    try:
        return Path(full).resolve()
    except Exception:
        return Path(full)

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
    print("🧪 Testing WAV file mapping and playlist creation with proper folder structure")
    
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
    
    print(f"📂 Connecting to: {db_dir}")
    db = Rekordbox6Database(db_dir=str(db_dir))
    
    # Find original ALLDJ Baked playlist with tracks
    print("🔍 Finding ALLDJ Baked tracks to map...")
    playlists = db.get_playlist().all()
    alldj_baked = next((p for p in playlists if p.Name == "ALLDJ Baked"), None)
    
    if not alldj_baked:
        print("❌ ALLDJ Baked folder not found")
        return 1
    
    # Find first child playlist under ALLDJ Baked
    child_playlists = [p for p in playlists if getattr(p, 'ParentID', None) == alldj_baked.ID]
    test_playlist = None
    for child in child_playlists:
        # Check if this playlist has tracks
        SP = db6.tables.DjmdSongPlaylist
        track_count = db.session.query(SP).filter(SP.PlaylistID == child.ID).count()
        if track_count > 0:
            test_playlist = child
            break
    
    if not test_playlist:
        print("❌ No playlists with tracks found under ALLDJ Baked")
        return 1
    
    print(f"📁 Using source playlist: {test_playlist.Name} ({track_count} tracks)")
    
    # Get first 5 tracks and map to WAV
    SP = db6.tables.DjmdSongPlaylist
    CT = db6.tables.DjmdContent
    tracks = (
        db.session.query(SP, CT)
        .join(CT, CT.ID == SP.ContentID)
        .filter(SP.PlaylistID == test_playlist.ID)
        .limit(5)
        .all()
    )
    
    print(f"\n🎵 Mapping {len(tracks)} FLAC tracks to WAV:")
    wav_tracks = []
    
    for i, (sp, ct) in enumerate(tracks, 1):
        name = (ct.FileNameL or ct.FileNameS or "").strip()
        title = ct.Title or name
        src_path = normalize_rb_path(ct.FolderPath or "", name)
        wav_path = map_to_wav_path(src_path)
        
        print(f"  {i}. {title}")
        print(f"     FLAC: {src_path}")
        print(f"     WAV:  {wav_path}")
        
        if wav_path and wav_path.exists():
            print(f"     ✅ WAV file exists")
            wav_tracks.append((title, wav_path))
        else:
            print(f"     ❌ WAV file missing")
    
    if not wav_tracks:
        print("\n❌ No valid WAV files found")
        return 1
    
    print(f"\n✅ Found {len(wav_tracks)} valid WAV mappings")
    
    # Create proper folder structure: wav/ALLDJ Baked/Test Playlist
    print("\n📁 Creating folder structure...")
    
    # Get or create 'wav' root folder
    wav_parent = next((p for p in playlists if p.Name == "wav" and not getattr(p, 'ParentID', None)), None)
    if not wav_parent:
        wav_parent = db.create_playlist_folder("wav")
        print("   ✓ Created 'wav' root folder")
    else:
        print("   ✓ Found existing 'wav' root folder")
    
    # Get or create 'ALLDJ Baked' under wav
    baked_folder = next((p for p in playlists if p.Name == "ALLDJ Baked" and getattr(p, 'ParentID', None) == wav_parent.ID), None)
    if not baked_folder:
        baked_folder = db.create_playlist_folder("ALLDJ Baked", parent=wav_parent)
        print("   ✓ Created 'wav/ALLDJ Baked' folder")
    else:
        print("   ✓ Found existing 'wav/ALLDJ Baked' folder")
    
    # Create test playlist
    test_name = "WAV Test - 5 Tracks"
    existing_test = next((p for p in playlists if p.Name == test_name and getattr(p, 'ParentID', None) == baked_folder.ID), None)
    if existing_test:
        db.delete_playlist(existing_test)
        print("   ✓ Deleted existing test playlist")
    
    test_wav_playlist = db.create_playlist(test_name, parent=baked_folder)
    print(f"   ✓ Created 'wav/ALLDJ Baked/{test_name}' playlist")
    
    # Add WAV tracks
    print(f"\n🎵 Adding {len(wav_tracks)} WAV tracks:")
    successful = 0
    
    for i, (title, wav_path) in enumerate(wav_tracks, 1):
        try:
            print(f"  {i}. Adding: {title}")
            
            # Import or get track
            content = db.get_content(FolderPath=str(wav_path)).first()
            if not content:
                content = db.add_content(str(wav_path))
            
            if content:
                db.add_to_playlist(test_wav_playlist, content)
                print(f"     ✅ Added successfully")
                successful += 1
            else:
                print(f"     ❌ Failed to import")
        except Exception as e:
            print(f"     ❌ Error: {e}")
    
    print(f"\n📊 Results: {successful}/{len(wav_tracks)} tracks added successfully")
    
    # Commit changes
    print("\n💾 Committing changes...")
    try:
        db.commit()
        print("✅ Changes committed to Rekordbox database!")
        print(f"\n🎉 Check Rekordbox for: wav/ALLDJ Baked/{test_name}")
        print(f"   Should contain {successful} WAV tracks")
    except Exception as e:
        print(f"❌ Commit failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
