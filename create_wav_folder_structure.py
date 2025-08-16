#!/usr/bin/env python3

"""
Create proper nested WAV folder structure matching ALLDJ Baked structure.
Creates wav/ALLDJ Baked/ with identical nested folders and 5 test tracks.
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
    
    # Rekordbox folder path includes the filename already
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

def clone_folder_structure(db, src_folder, dst_parent, playlists, track_limit=5, current_count=0):
    """Recursively clone folder structure with WAV files"""
    if current_count >= track_limit:
        return current_count
    
    # Get children of source folder
    children = [p for p in playlists if getattr(p, 'ParentID', None) == src_folder.ID]
    
    if not children:
        # This is a leaf playlist - add WAV tracks
        SP = db6.tables.DjmdSongPlaylist
        CT = db6.tables.DjmdContent
        
        tracks = (
            db.session.query(SP, CT)
            .join(CT, CT.ID == SP.ContentID)
            .filter(SP.PlaylistID == src_folder.ID)
            .limit(track_limit - current_count)
            .all()
        )
        
        if tracks:
            # Create playlist under dst_parent
            try:
                dst_playlist = db.create_playlist(src_folder.Name, parent=dst_parent)
                print(f"      ✓ Created playlist: {src_folder.Name}")
                
                # Add WAV tracks
                tracks_added = 0
                for sp, ct in tracks:
                    if current_count + tracks_added >= track_limit:
                        break
                        
                    name = (ct.FileNameL or ct.FileNameS or "").strip()
                    title = ct.Title or name
                    src_path = normalize_rb_path(ct.FolderPath or "", name)
                    wav_path = map_to_wav_path(src_path)
                    
                    if wav_path and wav_path.exists():
                        try:
                            # Import or get WAV track
                            content = db.get_content(FolderPath=str(wav_path)).first()
                            if not content:
                                content = db.add_content(str(wav_path))
                            
                            if content:
                                db.add_to_playlist(dst_playlist, content)
                                tracks_added += 1
                                print(f"        → Added: {title}")
                        except Exception as e:
                            print(f"        ❌ Error adding {title}: {e}")
                
                return current_count + tracks_added
                
            except Exception as e:
                print(f"      ❌ Error creating playlist {src_folder.Name}: {e}")
                return current_count
    else:
        # This is a folder - create it and recurse
        try:
            dst_folder = db.create_playlist_folder(src_folder.Name, parent=dst_parent)
            print(f"    ✓ Created folder: {src_folder.Name}")
            
            # Recursively clone children
            total_added = current_count
            for child in children:
                if total_added >= track_limit:
                    break
                total_added = clone_folder_structure(db, child, dst_folder, playlists, track_limit, total_added)
            
            return total_added
            
        except Exception as e:
            print(f"    ❌ Error creating folder {src_folder.Name}: {e}")
            return current_count

def main():
    print("🎵 Creating nested WAV folder structure matching ALLDJ Baked")
    
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
    
    # Find original ALLDJ Baked folder (not under wav)
    wav_parent = next((p for p in playlists if p.Name == "wav"), None)
    wav_parent_id = wav_parent.ID if wav_parent else None
    
    original_baked = next((p for p in playlists if p.Name == "ALLDJ Baked" and getattr(p, 'ParentID', None) != wav_parent_id), None)
    if not original_baked:
        print("❌ Original ALLDJ Baked folder not found")
        return 1
    
    print(f"✓ Found original ALLDJ Baked folder")
    
    # Show the structure we'll clone
    children = [p for p in playlists if getattr(p, 'ParentID', None) == original_baked.ID]
    print(f"📁 Original structure has {len(children)} top-level folders:")
    for child in children[:5]:
        print(f"   - {child.Name}")
    if len(children) > 5:
        print(f"   ... and {len(children) - 5} more")
    
    # Get or create wav parent folder (reuse the one we already found)
    if not wav_parent:
        try:
            wav_parent = db.create_playlist_folder("wav")
            print("✓ Created 'wav' root folder")
        except Exception as e:
            print(f"❌ Error creating wav folder: {e}")
            return 1
    else:
        print("✓ Found existing 'wav' root folder")
    
    # Delete existing wav/ALLDJ Baked if present
    existing_wav_baked = next((p for p in playlists if p.Name == "ALLDJ Baked" and getattr(p, 'ParentID', None) == wav_parent.ID), None)
    if existing_wav_baked:
        try:
            # Delete recursively
            def delete_recursive(folder):
                folder_children = [p for p in playlists if getattr(p, 'ParentID', None) == folder.ID]
                for child in folder_children:
                    delete_recursive(child)
                db.delete_playlist(folder)
            
            delete_recursive(existing_wav_baked)
            print("✓ Deleted existing wav/ALLDJ Baked structure")
        except Exception as e:
            print(f"⚠️  Could not delete existing structure: {e}")
    
    # Create wav/ALLDJ Baked folder
    try:
        wav_baked = db.create_playlist_folder("ALLDJ Baked", parent=wav_parent)
        print("✓ Created wav/ALLDJ Baked folder")
    except Exception as e:
        print(f"❌ Error creating wav/ALLDJ Baked: {e}")
        return 1
    
    # Clone the structure with 5 total tracks
    print(f"\n📁 Cloning structure with 5 test tracks...")
    total_added = clone_folder_structure(db, original_baked, wav_baked, playlists, track_limit=5)
    
    if total_added > 0:
        # Commit changes
        print(f"\n💾 Committing changes...")
        try:
            db.commit()
            print("✅ SUCCESS! Nested folder structure created and committed!")
            print(f"\n🎉 Check Rekordbox for:")
            print(f"   📁 wav/ALLDJ Baked/ (with identical nested structure)")
            print(f"   🎵 {total_added} WAV tracks added across the structure")
            return 0
        except Exception as e:
            print(f"❌ Commit failed: {e}")
            return 1
    else:
        print("❌ No tracks were successfully added")
        return 1

if __name__ == "__main__":
    sys.exit(main())
