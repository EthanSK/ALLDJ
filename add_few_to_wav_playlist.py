#!/usr/bin/env python3

"""
Add 5 tracks to wav/ALLDJ Baked structure using the FLAC-WAV mapping file
"""

import json
import sys
from pathlib import Path
from pyrekordbox import Rekordbox6Database

def main():
    print("🎵 Adding 5 tracks to wav/ALLDJ Baked structure using mapping file")
    
    # Load the mapping file
    mapping_file = "flac_wav_mapping.json"
    if not Path(mapping_file).exists():
        print(f"❌ Mapping file '{mapping_file}' not found")
        print("   Run create_flac_wav_mapping.py first")
        return 1
    
    print(f"📋 Loading mapping from {mapping_file}...")
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    # Find mappings where WAV exists
    valid_mappings = [m for m in mapping_data['mappings'] if m['wav_exists']]
    print(f"✅ Found {len(valid_mappings)} valid FLAC→WAV mappings")
    
    if not valid_mappings:
        print("❌ No valid mappings found")
        return 1
    
    # Take first 5 valid mappings
    test_mappings = valid_mappings[:5]
    print(f"🧪 Using first {len(test_mappings)} mappings for test:")
    for i, mapping in enumerate(test_mappings, 1):
        title = mapping.get('title', 'Untitled')
        wav_name = Path(mapping['wav_path']).name
        print(f"   {i}. {title} → {wav_name}")
    
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
    
    # Find wav/ALLDJ Baked structure
    playlists = db.get_playlist().all()
    wav_parent = next((p for p in playlists if p.Name == "wav"), None)
    
    if not wav_parent:
        print("❌ wav folder not found")
        return 1
    
    wav_baked = next((p for p in playlists if p.Name == "ALLDJ Baked" and getattr(p, 'ParentID', None) == wav_parent.ID), None)
    if not wav_baked:
        print("❌ wav/ALLDJ Baked folder not found")
        return 1
    
    print("✅ Found wav/ALLDJ Baked structure")
    
    # Find first few leaf playlists to add tracks to
    leaf_playlists = []
    
    def find_leaf_playlists(parent_id, depth=0):
        if depth > 3 or len(leaf_playlists) >= 5:  # Stop at depth 3 or when we have 5
            return
        children = [p for p in playlists if getattr(p, 'ParentID', None) == parent_id]
        for child in children:
            grandchildren = [p for p in playlists if getattr(p, 'ParentID', None) == child.ID]
            if not grandchildren:  # This is a leaf playlist
                leaf_playlists.append(child)
                if len(leaf_playlists) >= 5:
                    return
            else:
                find_leaf_playlists(child.ID, depth + 1)
    
    find_leaf_playlists(wav_baked.ID)
    
    if not leaf_playlists:
        print("❌ No leaf playlists found")
        return 1
    
    print(f"📁 Found {len(leaf_playlists)} leaf playlists:")
    for p in leaf_playlists:
        print(f"   - {p.Name}")
    
    # Add tracks to playlists
    total_added = 0
    
    for i, (mapping, playlist) in enumerate(zip(test_mappings, leaf_playlists)):
        wav_path = Path(mapping['wav_path'])
        title = mapping.get('title', wav_path.stem)
        
        print(f"\n{i+1}. Adding '{title}' to '{playlist.Name}'")
        
        try:
            # Import or get WAV track
            content = db.get_content(FolderPath=str(wav_path)).first()
            if not content:
                print(f"      → Importing to Rekordbox...")
                content = db.add_content(str(wav_path))
            else:
                print(f"      → Already in Rekordbox")
            
            if content:
                # Set title from mapping
                if title and title != wav_path.stem:
                    try:
                        setattr(content, 'Title', title)
                        print(f"      → Set title: {title}")
                    except:
                        pass
                
                db.add_to_playlist(playlist, content)
                print(f"      ✅ Added successfully")
                total_added += 1
            else:
                print(f"      ❌ Failed to import")
                
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    print(f"\n📊 Results: Added {total_added} tracks to wav/ALLDJ Baked structure")
    
    if total_added > 0:
        # Commit changes
        print("\n💾 Committing changes...")
        try:
            db.commit()
            print("✅ SUCCESS! WAV tracks added and committed!")
            print(f"\n🎉 Check Rekordbox wav/ALLDJ Baked structure:")
            print(f"   🎵 {total_added} WAV tracks now in nested playlists")
            return 0
        except Exception as e:
            print(f"❌ Commit failed: {e}")
            return 1
    else:
        print("❌ No tracks were successfully added")
        return 1

if __name__ == "__main__":
    sys.exit(main())
