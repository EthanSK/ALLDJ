#!/usr/bin/env python3

"""
Baked Playlist Creator for Rekordbox

This script creates regular (baked) playlists in Rekordbox by importing M3U8 files.
It reads the existing M3U8 baked playlist files and creates static playlists
with the tracks already populated, adding "_Baked" suffix to both playlist
names and folder structure.

Requirements:
- pyrekordbox library
- M3U8 playlist files in baked_playlists_m3u8/ directory
- Rekordbox should be closed when running this script

Usage:
    python create_baked_playlists.py [--dry-run] [--backup]
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Set, Dict
import argparse
from datetime import datetime
import re

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    sys.exit(1)


class BakedPlaylistCreator:
    def __init__(self, metadata_file: str, dry_run: bool = False, backup: bool = True):
        self.metadata_file = metadata_file
        self.dry_run = dry_run
        self.backup = backup
        self.db = None
        self.baked_playlists_dir = Path("baked_playlists_m3u8")
        self.metadata = None
        
    def backup_database(self):
        """Create a backup of the Rekordbox database."""
        if not self.backup:
            return
            
        try:
            # Find Rekordbox database directory (try 7 first, then 6, then legacy)
            rekordbox_dir = Path.home() / "Library/Pioneer/rekordbox7"
            if not rekordbox_dir.exists():
                rekordbox_dir = Path.home() / "Library/Pioneer/rekordbox6"
            if not rekordbox_dir.exists():
                rekordbox_dir = Path.home() / "Library/Pioneer/rekordbox"
                
            if not rekordbox_dir.exists():
                print("Warning: Could not find Rekordbox database directory for backup")
                return
                
            # Create backup directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = rekordbox_dir.parent / f"rekordbox_backup_{timestamp}"
            
            print(f"Creating backup: {backup_dir}")
            shutil.copytree(rekordbox_dir, backup_dir)
            print(f"✓ Backup created successfully")
            
        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")
    
    def connect_to_database(self):
        """Connect to the Rekordbox database."""
        try:
            print("Connecting to Rekordbox database...")
            
            # Try to find the database directory (7 first, then 6, then legacy)
            db_paths = [
                Path.home() / "Library/Pioneer/rekordbox7",
                Path.home() / "Library/Pioneer/rekordbox6", 
                Path.home() / "Library/Pioneer/rekordbox"
            ]
            
            db_path = None
            for path in db_paths:
                if path.exists():
                    db_path = path
                    break
            
            if db_path is None:
                raise Exception("No Rekordbox database directory found")
            
            print(f"Found Rekordbox database at: {db_path}")
            
            # Connect to the database with the found path
            self.db = Rekordbox6Database(db_dir=str(db_path))
            print("✓ Connected successfully")
        except Exception as e:
            print(f"Error: Failed to connect to Rekordbox database: {e}")
            print("\nMake sure:")
            print("1. Rekordbox is completely closed")
            print("2. You have Rekordbox 6 or 7 installed")
            print("3. You have used Rekordbox at least once (to create the database)")
            print("4. If using Rekordbox 7, the database format should be compatible")
            
            # Check if it's a key extraction issue
            if "key" in str(e).lower() or "unlock" in str(e).lower():
                print("\nDatabase encryption key issue detected:")
                print("Try running: python -m pyrekordbox download-key")
                print("Or for newer Rekordbox versions, you may need to use the frida method")
            
            sys.exit(1)
    
    def load_metadata(self) -> dict:
        """Load the music metadata from JSON file."""
        if self.metadata is None:
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except FileNotFoundError:
                print(f"Error: Metadata file '{self.metadata_file}' not found.")
                sys.exit(1)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in metadata file: {e}")
                sys.exit(1)
        return self.metadata
    
    def find_tracks_with_tag(self, tag: str) -> List[dict]:
        """Find all tracks that have the specified tag in their assigned_tags."""
        metadata = self.load_metadata()
        tracks_with_tag = []
        
        for track in metadata.get('tracks', []):
            assigned_tags = track.get('assigned_tags', [])
            if tag in assigned_tags:
                tracks_with_tag.append(track)
                
        return tracks_with_tag
    
    def find_track_in_rekordbox_by_filename(self, filename: str):
        """Find a track in the Rekordbox database by filename."""
        try:
            # Try to find by exact filename using FileNameL (Long filename)
            track = self.db.get_content(FileNameL=filename).first()
            if track:
                return track
                
            # If not found, try without the "flac/" prefix if present
            if filename.startswith('flac/'):
                filename_only = filename[5:]  # Remove "flac/" prefix
                track = self.db.get_content(FileNameL=filename_only).first()
                if track:
                    return track
            
            # Try to find by FileNameS (Short filename) as backup
            track = self.db.get_content(FileNameS=filename).first()
            if track:
                return track
                    
            return None
        except Exception:
            return None
    
    def find_m3u8_files(self) -> List[Path]:
        """Find all M3U8 files in the baked playlists directory."""
        if not self.baked_playlists_dir.exists():
            print(f"Error: Baked playlists directory '{self.baked_playlists_dir}' not found")
            sys.exit(1)
        
        m3u8_files = list(self.baked_playlists_dir.glob("*.m3u8"))
        if not m3u8_files:
            print(f"Error: No M3U8 files found in '{self.baked_playlists_dir}'")
            sys.exit(1)
        
        return sorted(m3u8_files)
    
    
    def playlist_exists(self, name: str) -> bool:
        """Check if a playlist with the given name already exists."""
        try:
            result = self.db.get_playlist(Name=name).first()
            return result is not None
        except:
            return False
    
    def get_tag_categories(self) -> dict:
        """Define tag categories based on the taxonomy."""
        return {
            "Dopamine Source": [
                "nostalgic-hit", "euphoric-melody", "emotional-depth", "textural-beauty",
                "rhythmic-hypnosis", "harmonic-surprise", "vocal-magic", "psychedelic-journey",
                "sophisticated-groove"
            ],
            "Mixing Role": [
                "rhythmic-foundation", "melodic-overlay", "bridge-element", "texture-add",
                "anchor-track", "wildcard", "transition-tool", "emotional-crescendo",
                "palate-cleanser"
            ],
            "Vocal Characteristics": [
                "vocal-prominent", "vocal-minimal", "vocal-isolated", "instrumental",
                "vocal-chopped", "harmony-rich", "spoken-word"
            ],
            "Era Bridging": [
                "retro-modern", "genre-crossover", "generational-bridge", "cultural-moment",
                "timeless-classic", "vintage-revival", "contemporary-classic"
            ],
            "Emotional Trajectory": [
                "lifts-mood", "adds-depth", "creates-tension", "provides-release",
                "maintains-vibe", "contrast-element", "reset-button", "emotional-rollercoaster",
                "meditation-inducer"
            ],
            "Energy Dynamics": [
                "slow-burn", "instant-impact", "sustainer", "energy-shifter",
                "peak-moment", "cool-down", "energy-weaver", "hypnotic-builder"
            ],
            "Set Positioning": [
                "set-opener", "warm-up", "peak-time", "emotional-peak",
                "comedown", "sunrise", "interlude", "finale"
            ],
            "Mixing Compatibility": [
                "layer-friendly", "tempo-flexible", "key-adaptable", "breakdown-rich",
                "loop-gold", "mashup-ready", "filter-friendly", "pitch-bendable"
            ],
            "Sonic Character": [
                "warm-analog", "crisp-digital", "gritty-texture", "spacious-mix",
                "dense-production", "minimal-space", "atmospheric-wash", "punchy-dynamics",
                "subtle-nuance"
            ],
            "Psychedelic/Consciousness Elements": [
                "mind-expanding", "reality-bending", "geometric-patterns", "color-synesthesia",
                "time-dilation", "ego-dissolution", "dream-logic"
            ],
            "Cultural/Generational Resonance": [
                "gen-z-nostalgia", "millennial-comfort", "gen-x-wisdom", "boomer-classic",
                "indie-cred", "mainstream-crossover", "cultural-bridge"
            ],
            "Complexity/Texture": [
                "experimental", "psychedelic", "intricate", "stripped-down",
                "lush", "lo-fi", "hi-fi"
            ],
            "Tempo Feel": [
                "steady", "dynamic", "hypnotic", "choppy",
                "flowing", "driving", "shuffle"
            ],
            "Genre Sophistication": [
                "electronic-experimental", "electronic-dance", "electronic-ambient", "rock-psychedelic",
                "rock-indie", "rock-classic", "pop-sophisticated", "pop-experimental",
                "hip-hop-conscious", "hip-hop-experimental", "jazz-influenced", "folk-modern",
                "world-fusion", "genre-fluid"
            ],
            "Danceability & Floor Response": [
                "instant-dancefloor", "needs-layering", "slow-burn-dance", "non-danceable-standalone",
                "crowd-pleaser", "niche-dancer", "body-mover", "head-nodder"
            ],
            "DJ Technical Functionality": [
                "long-intro", "short-intro", "clean-outro", "fade-outro",
                "breakdown-intro", "full-energy-start", "beatmatched-friendly", "tempo-challenging",
                "drop-heavy", "smooth-transitions"
            ],
            "Crowd Energy Management": [
                "energy-injector", "energy-sustainer", "energy-bridge", "mood-shifter",
                "attention-grabber", "background-perfect", "sing-along-potential", "hands-up-moment"
            ],
            "Version Type": [
                "original", "remix", "live", "edit",
                "remaster", "bootleg", "acoustic", "instrumental"
            ],
            "Personal Tags": [
                "funny", "deep", "dopamine", "energetic", "drum-bass-layer"
            ]
        }
    
    def get_category_for_tag(self, tag: str) -> str:
        """Get the category folder name for a given tag."""
        categories = self.get_tag_categories()
        for category, tags in categories.items():
            if tag in tags:
                return f"{category} Baked"
        return "Other Tags Baked"  # Fallback for unrecognized tags
    
    def create_baked_playlist(self, m3u8_path: Path) -> bool:
        """Create a baked playlist from an M3U8 file."""
        # Extract tag name from filename (remove _Baked.m3u8 suffix)
        tag_name = m3u8_path.stem.replace('_Baked', '')
        playlist_name = f"{tag_name} Baked"
        
        print(f"  Processing: {m3u8_path.name} -> '{playlist_name}'")
        
        # Check if playlist already exists and delete it to recreate
        if self.playlist_exists(playlist_name):
            try:
                existing_playlist = self.db.get_playlist(Name=playlist_name).first()
                if existing_playlist:
                    self.db.delete_playlist(existing_playlist)
                    print(f"    ✓ Deleted existing playlist '{playlist_name}'")
            except Exception as e:
                print(f"    Warning: Could not delete existing playlist '{playlist_name}': {e}")
        
        # Find tracks from metadata JSON that have this tag
        tracks_with_tag_metadata = self.find_tracks_with_tag(tag_name)
        print(f"    Found {len(tracks_with_tag_metadata)} tracks in metadata with tag '{tag_name}'")
        
        if len(tracks_with_tag_metadata) == 0:
            print(f"    ⚠️  No tracks found with tag '{tag_name}', skipping playlist creation")
            return False
        
        if self.dry_run:
            print(f"    [DRY RUN] Would create baked playlist: '{playlist_name}' with {len(tracks_with_tag_metadata)} tracks")
            return True
        
        try:
            # Create the playlist
            playlist = self.db.create_playlist(playlist_name)
            
            # Add tracks to the playlist by finding them in Rekordbox database
            added_count = 0
            not_found_count = 0
            for track_metadata in tracks_with_tag_metadata:
                filename = track_metadata.get('filename')
                if filename:
                    rekordbox_track = self.find_track_in_rekordbox_by_filename(filename)
                    if rekordbox_track:
                        try:
                            self.db.add_to_playlist(playlist, rekordbox_track)
                            added_count += 1
                        except Exception as e:
                            print(f"      Warning: Could not add track '{filename}' to playlist: {e}")
                    else:
                        print(f"      Warning: Track not found in Rekordbox: {filename}")
                        not_found_count += 1
            
            print(f"    ✓ Created baked playlist: '{playlist_name}' with {added_count}/{len(tracks_with_tag_metadata)} tracks (ID: {playlist.ID})")
            if not_found_count > 0:
                print(f"      ({not_found_count} tracks not found in Rekordbox)")
            return True
            
        except Exception as e:
            print(f"    ✗ Failed to create playlist '{playlist_name}': {e}")
            return False
    
    def organize_baked_playlists_by_category(self, created_playlists: List[str]):
        """Create category folders and organize baked playlists into them."""
        try:
            # First, create or find the main ALLDJ Baked folder
            alldj_baked_folder_name = "ALLDJ Baked"
            if self.playlist_exists(alldj_baked_folder_name):
                if not self.dry_run:
                    print(f"Using existing folder: '{alldj_baked_folder_name}'")
                    alldj_baked_folder = self.db.get_playlist(Name=alldj_baked_folder_name).first()
                else:
                    print(f"[DRY RUN] Would use existing folder: '{alldj_baked_folder_name}'")
                    alldj_baked_folder = None
            else:
                if self.dry_run:
                    print(f"[DRY RUN] Would create main folder: '{alldj_baked_folder_name}'")
                    alldj_baked_folder = None
                else:
                    # Create the main ALLDJ Baked folder
                    alldj_baked_folder = self.db.create_playlist_folder(alldj_baked_folder_name)
                    print(f"✓ Created main folder: '{alldj_baked_folder_name}'")
            
            # Group playlists by category
            playlist_categories = {}
            for playlist_name in created_playlists:
                # Extract tag from playlist name (remove " Baked" suffix)
                tag = playlist_name.replace(" Baked", "")
                category = self.get_category_for_tag(tag)
                if category not in playlist_categories:
                    playlist_categories[category] = []
                playlist_categories[category].append(playlist_name)
            
            print(f"\nOrganizing baked playlists into {len(playlist_categories)} category folders...")
            
            # Create folders and organize playlists
            for category, playlists in playlist_categories.items():
                if not playlists:
                    continue
                    
                folder_name = category
                
                # Check if folder already exists
                if self.playlist_exists(folder_name):
                    if not self.dry_run:
                        print(f"Using existing folder: '{folder_name}'")
                        folder = self.db.get_playlist(Name=folder_name).first()
                    else:
                        print(f"[DRY RUN] Would use existing folder: '{folder_name}'")
                        folder = None
                else:
                    if self.dry_run:
                        print(f"[DRY RUN] Would create folder: '{folder_name}' ({len(playlists)} playlists)")
                        continue
                        
                    # Create the category folder under ALLDJ Baked
                    folder = self.db.create_playlist_folder(folder_name, parent=alldj_baked_folder)
                    print(f"✓ Created folder: '{folder_name}'")
                
                if self.dry_run:
                    print(f"[DRY RUN] Would move {len(playlists)} playlists into '{folder_name}':")
                    for playlist_name in sorted(playlists):
                        print(f"    - {playlist_name}")
                    continue
                
                # Move playlists into the category folder
                moved_count = 0
                for playlist_name in playlists:
                    try:
                        playlist = self.db.get_playlist(Name=playlist_name).first()
                        if playlist and playlist.ParentID != folder.ID:
                            self.db.move_playlist(playlist, parent=folder)
                            moved_count += 1
                    except Exception as e:
                        print(f"  Warning: Could not move playlist '{playlist_name}': {e}")
                
                if moved_count > 0:
                    print(f"  ✓ Moved {moved_count} playlists into '{folder_name}'")
                    
        except Exception as e:
            print(f"Warning: Could not organize baked playlists by category: {e}")
    
    def run(self):
        """Main execution function."""
        print("🎵 Baked Playlist Creator for Rekordbox")
        print("======================================")
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
        
        # Find M3U8 files
        print(f"\nLooking for M3U8 files in: {self.baked_playlists_dir}")
        m3u8_files = self.find_m3u8_files()
        print(f"✓ Found {len(m3u8_files)} M3U8 files")
        
        # Create backup
        if not self.dry_run:
            self.backup_database()
        
        # Connect to database
        self.connect_to_database()
        
        print(f"\nCreating baked playlists...")
        created_playlists = []
        successful = 0
        failed = 0
        skipped = 0
        
        for i, m3u8_file in enumerate(m3u8_files, 1):
            print(f"[{i}/{len(m3u8_files)}] Processing: {m3u8_file.name}")
            
            result = self.create_baked_playlist(m3u8_file)
            if result is True:
                successful += 1
                tag_name = m3u8_file.stem.replace('_Baked', '')
                playlist_name = f"{tag_name} Baked"
                created_playlists.append(playlist_name)
            elif result is False:
                tag_name = m3u8_file.stem.replace('_Baked', '')
                playlist_name = f"{tag_name} Baked"
                if self.playlist_exists(playlist_name):
                    skipped += 1
                else:
                    failed += 1
        
        # Organize playlists by category
        if not self.dry_run or created_playlists:
            print(f"\nOrganizing baked playlists by category...")
            self.organize_baked_playlists_by_category(created_playlists)
        
        # Commit changes
        if not self.dry_run and (successful > 0 or created_playlists):
            print(f"\nCommitting changes to database...")
            try:
                self.db.commit()
                print("✓ Changes committed successfully")
            except Exception as e:
                print(f"✗ Error committing changes: {e}")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Total M3U8 files: {len(m3u8_files)}")
        print(f"   Created: {successful}")
        print(f"   Skipped (existing): {skipped}")
        print(f"   Failed: {failed}")
        
        if self.dry_run:
            print("\n💡 Run without --dry-run to create the baked playlists")
        elif successful > 0:
            print(f"\n✅ Baked playlist creation complete!")
            print(f"   Open Rekordbox to see your new baked playlists")
        
        # Close database connection
        if self.db:
            self.db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create baked playlists in Rekordbox from metadata tags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_baked_playlists.py --dry-run
  python create_baked_playlists.py --no-backup
  python create_baked_playlists.py --metadata my_metadata.json
        """
    )
    
    parser.add_argument(
        "--metadata",
        default="music_collection_metadata.json",
        help="Path to metadata JSON file (default: music_collection_metadata.json)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making changes"
    )
    
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a backup of the Rekordbox database"
    )
    
    args = parser.parse_args()
    
    # Check if metadata file exists
    if not os.path.exists(args.metadata):
        print(f"Error: Metadata file '{args.metadata}' not found.")
        print("\nMake sure you have:")
        print("1. The metadata file exists")
        print("2. The metadata file contains tracks with assigned_tags")
        sys.exit(1)
    
    # Check if baked playlists directory exists
    baked_dir = Path("baked_playlists_m3u8")
    if not baked_dir.exists():
        print(f"Error: Baked playlists directory '{baked_dir}' not found.")
        print("\nMake sure you have:")
        print("1. The baked_playlists_m3u8/ directory exists")
        print("2. M3U8 playlist files are in that directory")
        sys.exit(1)
    
    # Create and run the baked playlist creator
    creator = BakedPlaylistCreator(
        metadata_file=args.metadata,
        dry_run=args.dry_run,
        backup=not args.no_backup
    )
    
    try:
        creator.run()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        if creator.db:
            creator.db.close()
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        if creator.db:
            creator.db.close()
        sys.exit(1)


if __name__ == "__main__":
    main()