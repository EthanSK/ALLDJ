#!/usr/bin/env python3

"""
Create Rekordbox XML files for Baked playlists that can be imported into Rekordbox.
This triggers Rekordbox's own export process rather than manual file copying.
"""

import sys
from pathlib import Path
from copy_rekordbox_playlists_to_usb import RekordboxPlaylistCopier
import xml.etree.ElementTree as ET
from xml.dom import minidom
from urllib.parse import quote
import os

class RekordboxXMLExporter:
    def __init__(self):
        self.copier = RekordboxPlaylistCopier(
            usb_path="/Volumes/DJYING",
            test_mode=False,
            resume=False
        )
        
    def normalize_path_for_xml(self, path: Path) -> str:
        """Convert file path to Rekordbox XML format."""
        # Convert to file:// URL format that Rekordbox expects
        path_str = str(path.resolve())
        return f"file://localhost{quote(path_str)}"
    
    def create_playlist_xml(self, playlists, output_file: str):
        """Create Rekordbox XML file with static playlists."""
        
        # Create root XML structure
        root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
        
        # Product info
        product = ET.SubElement(root, "PRODUCT", 
                               Name="rekordbox", 
                               Version="7.0.0", 
                               Company="AlphaTheta")
        
        # Collection (tracks database)
        collection = ET.SubElement(root, "COLLECTION")
        track_id = 1
        track_map = {}  # Map file paths to track IDs
        
        print("🎵 Building track collection...")
        
        # First pass: collect all unique tracks
        all_tracks = {}
        for playlist in playlists:
            tracks = self.copier.get_playlist_tracks(playlist.id)
            for track in tracks:
                if track.exists:
                    path_key = str(track.original_path)
                    if path_key not in all_tracks:
                        all_tracks[path_key] = track
        
        print(f"📚 Found {len(all_tracks)} unique tracks")
        
        # Add tracks to collection
        for path_key, track in all_tracks.items():
            track_element = ET.SubElement(collection, "TRACK", 
                                        TrackID=str(track_id),
                                        Name=track.title,
                                        Artist=track.artist,
                                        Location=self.normalize_path_for_xml(track.original_path))
            
            # Add file info
            track_element.set("Size", str(track.file_size))
            track_element.set("Kind", "FLAC File")
            
            track_map[path_key] = track_id
            track_id += 1
        
        collection.set("Entries", str(len(all_tracks)))
        
        # Playlists section
        playlists_root = ET.SubElement(root, "PLAYLISTS")
        
        # Create folder structure for Baked playlists
        baked_folder = ET.SubElement(playlists_root, "NODE", 
                                   Type="0", 
                                   Name="ALLDJ Baked Playlists", 
                                   Count="0", 
                                   Expanded="1")
        
        print("🗂️  Creating playlist structure...")
        
        # Group playlists by category
        categories = {}
        for playlist in playlists:
            # Extract category from full path
            path_parts = playlist.full_path.split(" / ")
            if len(path_parts) >= 3:  # "ALLDJ Baked / Category / Playlist"
                category = path_parts[1] if len(path_parts) > 2 else "Other"
            else:
                category = "Other"
            
            if category not in categories:
                categories[category] = []
            categories[category].append(playlist)
        
        # Create category folders and playlists
        for category_name, category_playlists in categories.items():
            print(f"📁 Creating category: {category_name} ({len(category_playlists)} playlists)")
            
            category_folder = ET.SubElement(baked_folder, "NODE",
                                          Type="0",
                                          Name=category_name,
                                          Count="0",
                                          Expanded="1")
            
            for playlist in category_playlists:
                print(f"  🎵 Adding playlist: {playlist.name}")
                
                # Get tracks for this playlist
                tracks = self.copier.get_playlist_tracks(playlist.id)
                existing_tracks = [t for t in tracks if t.exists]
                
                if not existing_tracks:
                    print(f"    ⚠️  Skipping (no existing tracks)")
                    continue
                
                # Create playlist node
                playlist_node = ET.SubElement(category_folder, "NODE",
                                            Type="1",
                                            Name=playlist.name,
                                            KeyType="0",
                                            Entries=str(len(existing_tracks)))
                
                # Add tracks to playlist
                for i, track in enumerate(existing_tracks):
                    path_key = str(track.original_path)
                    if path_key in track_map:
                        track_element = ET.SubElement(playlist_node, "TRACK",
                                                    Key=str(track_map[path_key]))
                
                print(f"    ✅ Added {len(existing_tracks)} tracks")
        
        # Write XML file
        print(f"💾 Writing XML file: {output_file}")
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ", encoding=None)
        
        # Remove empty lines
        pretty_lines = [line for line in pretty_xml.split('\n') if line.strip()]
        final_xml = '\n'.join(pretty_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_xml)
        
        print(f"✅ XML export complete!")
        return output_file

def main():
    print("🎯 Creating Rekordbox XML Export for Baked Playlists")
    print("="*60)
    
    exporter = RekordboxXMLExporter()
    
    try:
        # Connect to database
        print("📡 Connecting to Rekordbox database...")
        exporter.copier.connect_to_database()
        exporter.copier.detect_smart_playlists()
        
        # Get Baked playlists
        print("🔍 Finding Baked playlists...")
        all_playlists = exporter.copier.get_all_playlists()
        
        baked_playlists = []
        for playlist in all_playlists:
            if "baked" in playlist.name.lower() and playlist.track_count > 0:
                baked_playlists.append(playlist)
        
        print(f"📋 Found {len(baked_playlists)} Baked playlists")
        
        if not baked_playlists:
            print("❌ No Baked playlists found!")
            return
        
        # Create XML file
        output_file = "/Volumes/DJYING/ALLDJ_Baked_Playlists.xml"
        xml_file = exporter.create_playlist_xml(baked_playlists, output_file)
        
        print(f"\n🎉 SUCCESS! Created Rekordbox import file:")
        print(f"📄 File: {xml_file}")
        print(f"\n📖 To import in Rekordbox:")
        print(f"   1. File → Library → Import Library")
        print(f"   2. Select: {xml_file}")
        print(f"   3. Choose import options")
        print(f"   4. Rekordbox will handle the rest!")
        
        print(f"\n💡 This will create static playlists in Rekordbox that you can:")
        print(f"   - Export to USB using Rekordbox's built-in export")
        print(f"   - Sync to other devices")
        print(f"   - Share with other Rekordbox users")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if exporter.copier.db:
            exporter.copier.db.close()

if __name__ == "__main__":
    main()

