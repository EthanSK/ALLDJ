#!/usr/bin/env python3

"""
Final script to create complete WAV playlist structure in Rekordbox.
Populates wav/ALLDJ Baked, wav/ALLDJ Stems, and wav/OG Stems with proper WAV tracks.
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

def clone_and_populate_structure(db, src_folder, dst_parent, playlists, mapping_dict, folder_name):
    """Recursively clone folder structure and populate with WAV files using mapping"""
    total_tracks_added = 0
    total_playlists_created = 0
    
    # Get children of source folder
    children = [p for p in playlists if getattr(p, 'ParentID', None) == src_folder.ID]
    
    if not children:
        # This is a leaf playlist - populate with WAV tracks
        SP = db6.tables.DjmdSongPlaylist
        CT = db6.tables.DjmdContent
        
        # Get all tracks from this playlist
        tracks = (
            db.session.query(SP, CT)
            .join(CT, CT.ID == SP.ContentID)
            .filter(SP.PlaylistID == src_folder.ID)
            .all()
        )
        
        if tracks:
            # Create playlist under dst_parent
            try:
                dst_playlist = db.create_playlist(src_folder.Name, parent=dst_parent)
                print(f"        ✓ Created playlist: {src_folder.Name}")
                total_playlists_created = 1
                
                # Add WAV tracks using mapping
                tracks_added = 0
                for sp, ct in tracks:
                    rekordbox_id = str(ct.ID)
                    
                    # Look up in mapping
                    if rekordbox_id in mapping_dict:
                        mapping = mapping_dict[rekordbox_id]
                        if mapping['wav_exists']:
                            wav_path = Path(mapping['wav_path'])
                            title = mapping.get('title', wav_path.stem)
                            
                            try:
                                # Import or get WAV track
                                content = db.get_content(FolderPath=str(wav_path)).first()
                                if not content:
                                    content = db.add_content(str(wav_path))
                                
                                if content:
                                    # Set proper title
                                    if title and title.strip():
                                        try:
                                            setattr(content, 'Title', title)
                                        except:
                                            pass
                                    
                                    db.add_to_playlist(dst_playlist, content)
                                    tracks_added += 1
                                    
                                    if tracks_added % 10 == 0:
                                        print(f"          → Added {tracks_added} tracks...")
                                        
                            except Exception as e:
                                print(f"          ❌ Error adding {title}: {e}")
                
                total_tracks_added = tracks_added
                if tracks_added > 0:
                    print(f"        ✅ Added {tracks_added} WAV tracks")
                else:
                    print(f"        ⚠️  No matching WAV tracks found")
                
            except Exception as e:
                print(f"        ❌ Error creating playlist {src_folder.Name}: {e}")
    else:
        # This is a folder - create it and recurse
        try:
            dst_folder = db.create_playlist_folder(src_folder.Name, parent=dst_parent)
            print(f"      ✓ Created folder: {src_folder.Name}")
            
            # Recursively clone children
            for child in children:
                child_tracks, child_playlists = clone_and_populate_structure(
                    db, child, dst_folder, playlists, mapping_dict, folder_name
                )
                total_tracks_added += child_tracks
                total_playlists_created += child_playlists
            
        except Exception as e:
            print(f"      ❌ Error creating folder {src_folder.Name}: {e}")
    
    return total_tracks_added, total_playlists_created

def main():
    print("🎵 Creating final complete WAV playlist structure in Rekordbox")
    
    # Load the mapping file
    mapping_file = "flac_wav_mapping.json"
    if not Path(mapping_file).exists():
        print(f"❌ Mapping file '{mapping_file}' not found")
        print("   Run create_flac_wav_mapping.py first")
        return 1
    
    print(f"📋 Loading mapping from {mapping_file}...")
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    # Create mapping dictionary by rekordbox_id for fast lookup
    mapping_dict = {}
    for mapping in mapping_data['mappings']:
        if mapping.get('rekordbox_id'):
            mapping_dict[str(mapping['rekordbox_id'])] = mapping
    
    valid_mappings = len([m for m in mapping_data['mappings'] if m['wav_exists']])
    print(f"✅ Loaded {len(mapping_dict)} mappings, {valid_mappings} with existing WAV files")
    
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
    print(f"📊 Found {len(playlists)} total playlists in Rekordbox")
    
    # Get or create wav parent folder
    wav_parent = next((p for p in playlists if p.Name == "wav"), None)
    if not wav_parent:
        try:
            wav_parent = db.create_playlist_folder("wav")
            print("✓ Created 'wav' root folder")
        except Exception as e:
            print(f"❌ Error creating wav folder: {e}")
            return 1
    else:
        print("✓ Found existing 'wav' root folder")
    
    # Structure to clone
    structures_to_clone = [
        ("ALLDJ Baked", "ALLDJ Baked"),
        ("ALLDJ Stems", "ALLDJ Stems"), 
        ("OG Stems", "OG Stems")
    ]
    
    total_tracks_all = 0
    total_playlists_all = 0
    
    for original_name, wav_name in structures_to_clone:
        print(f"\n🏗️  Processing {original_name}...")
        
        # Find original folder (not under wav)
        original_folder = None
        for p in playlists:
            if p.Name == original_name:
                parent_id = getattr(p, 'ParentID', None)
                if parent_id != wav_parent.ID:  # Not already under wav
                    original_folder = p
                    break
        
        if not original_folder:
            print(f"    ❌ Original '{original_name}' folder not found")
            continue
        
        print(f"    ✓ Found original '{original_name}' folder")
        
        # Delete existing wav version if present
        existing_wav_folder = next((p for p in playlists 
                                  if p.Name == wav_name and getattr(p, 'ParentID', None) == wav_parent.ID), None)
        if existing_wav_folder:
            try:
                def delete_recursive(folder):
                    folder_children = [p for p in playlists if getattr(p, 'ParentID', None) == folder.ID]
                    for child in folder_children:
                        delete_recursive(child)
                    db.delete_playlist(folder)
                
                delete_recursive(existing_wav_folder)
                print(f"    ✓ Deleted existing wav/{wav_name} structure")
            except Exception as e:
                print(f"    ⚠️  Could not delete existing structure: {e}")
        
        # Create wav version
        try:
            wav_folder = db.create_playlist_folder(wav_name, parent=wav_parent)
            print(f"    ✓ Created wav/{wav_name} folder")
        except Exception as e:
            print(f"    ❌ Error creating wav/{wav_name}: {e}")
            continue
        
        # Clone and populate structure
        print(f"    📁 Cloning structure and populating with WAV tracks...")
        tracks_added, playlists_created = clone_and_populate_structure(
            db, original_folder, wav_folder, playlists, mapping_dict, wav_name
        )
        
        total_tracks_all += tracks_added
        total_playlists_all += playlists_created
        
        print(f"    ✅ {original_name} complete: {playlists_created} playlists, {tracks_added} tracks")
    
    print(f"\n📊 Final Results:")
    print(f"   Total playlists created: {total_playlists_all}")
    print(f"   Total WAV tracks added: {total_tracks_all}")
    
    if total_playlists_all > 0:
        # Commit changes
        print(f"\n💾 Committing all changes...")
        try:
            db.commit()
            print("✅ SUCCESS! Complete WAV playlist structure created and committed!")
            print(f"\n🎉 Check Rekordbox for complete structure:")
            print(f"   📁 wav/ALLDJ Baked/ - Complete nested structure with WAV tracks")
            print(f"   📁 wav/ALLDJ Stems/ - Complete stems structure with WAV tracks") 
            print(f"   📁 wav/OG Stems/ - Complete OG stems with WAV tracks")
            print(f"   🎵 {total_tracks_all} total WAV tracks across all structures")
            return 0
        except Exception as e:
            print(f"❌ Commit failed: {e}")
            return 1
    else:
        print("❌ No playlists were successfully created")
        return 1

if __name__ == "__main__":
    sys.exit(main())
