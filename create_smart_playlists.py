#!/usr/bin/env python3

"""
Smart Playlist Creator for Rekordbox

This script creates smart playlists in Rekordbox by directly modifying its database.
It reads your music metadata and creates one smart playlist for each unique tag
found in the COMMENT fields of your tracks.

Requirements:
- pyrekordbox library
- Your music files should have tags in their COMMENT fields
- Rekordbox should be closed when running this script

Usage:
    python create_smart_playlists.py [--dry-run] [--backup]
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Set
import argparse
from datetime import datetime

try:
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6.smartlist import SmartList, Property, Operator, LogicalOperator
except ImportError:
    print("Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    sys.exit(1)


class SmartPlaylistCreator:
    def __init__(self, metadata_file: str, dry_run: bool = False, backup: bool = True):
        self.metadata_file = metadata_file
        self.dry_run = dry_run
        self.backup = backup
        self.db = None
        
    def load_metadata(self) -> dict:
        """Load the music metadata from JSON file."""
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Metadata file '{self.metadata_file}' not found.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in metadata file: {e}")
            sys.exit(1)
    
    def extract_unique_tags(self, metadata: dict) -> Set[str]:
        """Extract all unique tags from the metadata."""
        tags = set()
        
        for track in metadata.get('tracks', []):
            track_tags = track.get('assigned_tags', [])
            if track_tags:
                tags.update(track_tags)
        
        return tags
    
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
    
    def playlist_exists(self, name: str) -> bool:
        """Check if a playlist with the given name already exists."""
        try:
            result = self.db.get_playlist(Name=name).first()
            return result is not None
        except:
            return False
    
    def delete_existing_smart_playlists(self, tags: Set[str]):
        """Delete existing smart playlists and old folder structure."""
        if self.dry_run:
            print("[DRY RUN] Would delete existing playlists and old folder structure")
            return
            
        print("Cleaning up existing playlists and folders...")
        
        # Delete individual tag playlists (both with and without "Tag: " prefix)
        deleted_count = 0
        for tag in tags:
            # Try both naming conventions
            for playlist_name in [tag, f"Tag: {tag}"]:
                try:
                    playlist = self.db.get_playlist(Name=playlist_name).first()
                    if playlist:
                        self.db.delete_playlist(playlist)
                        deleted_count += 1
                        print(f"  ✓ Deleted playlist: '{playlist_name}'")
                except Exception as e:
                    # Ignore errors for non-existent playlists
                    pass
        
        # Delete old category folders that might exist outside ALLDJ
        old_categories = [
            "Dopamine Source", "Mixing Role", "Vocal Characteristics", "Era Bridging",
            "Emotional Trajectory", "Energy Dynamics", "Set Positioning", 
            "Mixing Compatibility", "Sonic Character", "Psychedelic/Consciousness Elements",
            "Cultural/Generational Resonance", "Complexity/Texture", "Tempo Feel",
            "Genre Sophistication", "Danceability & Floor Response", "DJ Technical Functionality",
            "Crowd Energy Management", "Version Type", "Personal Tags"
        ]
        
        for category in old_categories:
            try:
                folder = self.db.get_playlist(Name=category).first()
                if folder:
                    self.db.delete_playlist(folder)
                    print(f"  ✓ Deleted old folder: '{category}'")
            except Exception as e:
                # Ignore errors for non-existent folders
                pass
        
        if deleted_count > 0:
            print(f"✓ Cleaned up {deleted_count} existing playlists and old folders")
    
    def create_smart_playlist_for_tag(self, tag: str) -> bool:
        """Create a smart playlist for a specific tag."""
        playlist_name = tag
        
        # Check if playlist already exists
        if self.playlist_exists(playlist_name):
            print(f"  ⚠️  Playlist '{playlist_name}' already exists, skipping")
            return False
        
        try:
            # Create smart list with condition: Comments contains tag
            smart_list = SmartList(logical_operator=LogicalOperator.ALL)
            smart_list.add_condition(
                prop=Property.COMMENTS,
                operator=Operator.CONTAINS,
                value_left=tag
            )
            
            if self.dry_run:
                print(f"  [DRY RUN] Would create smart playlist: '{playlist_name}'")
                print(f"            Condition: Comments contains '{tag}'")
                return True
            
            # Create the smart playlist
            playlist = self.db.create_smart_playlist(playlist_name, smart_list)
            print(f"  ✓ Created smart playlist: '{playlist_name}' (ID: {playlist.ID})")
            return True
            
        except Exception as e:
            print(f"  ✗ Failed to create playlist '{playlist_name}': {e}")
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
                return category
        return "Other Tags"  # Fallback for unrecognized tags
    
    def organize_playlists_by_category(self, all_tags: Set[str]):
        """Create category folders and organize tag playlists into them."""
        try:
            # First, create or find the main ALLDJ folder
            alldj_folder_name = "ALLDJ"
            if self.playlist_exists(alldj_folder_name):
                if not self.dry_run:
                    print(f"Using existing folder: '{alldj_folder_name}'")
                    alldj_folder = self.db.get_playlist(Name=alldj_folder_name).first()
                else:
                    print(f"[DRY RUN] Would use existing folder: '{alldj_folder_name}'")
                    alldj_folder = None
            else:
                if self.dry_run:
                    print(f"[DRY RUN] Would create main folder: '{alldj_folder_name}'")
                    alldj_folder = None
                else:
                    # Create the main ALLDJ folder
                    alldj_folder = self.db.create_playlist_folder(alldj_folder_name)
                    print(f"✓ Created main folder: '{alldj_folder_name}'")
            
            # Group tags by category
            tag_categories = {}
            for tag in all_tags:
                category = self.get_category_for_tag(tag)
                if category not in tag_categories:
                    tag_categories[category] = []
                tag_categories[category].append(tag)
            
            print(f"\nOrganizing playlists into {len(tag_categories)} category folders under ALLDJ...")
            
            # Create folders and organize playlists
            for category, tags in tag_categories.items():
                if not tags:
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
                        print(f"[DRY RUN] Would create folder: '{folder_name}' ({len(tags)} playlists)")
                        continue
                        
                    # Create the category folder under ALLDJ
                    folder = self.db.create_playlist_folder(folder_name, parent=alldj_folder)
                    print(f"✓ Created folder: '{folder_name}'")
                
                if self.dry_run:
                    print(f"[DRY RUN] Would move {len(tags)} playlists into '{folder_name}':")
                    for tag in sorted(tags):
                        print(f"    - {tag}")
                    continue
                
                # Move playlists into the category folder
                moved_count = 0
                for tag in tags:
                    playlist_name = tag
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
            print(f"Warning: Could not organize playlists by category: {e}")
    
    def run(self):
        """Main execution function."""
        print("🎵 Smart Playlist Creator for Rekordbox")
        print("=====================================")
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
        
        # Load metadata
        print(f"\nLoading metadata from: {self.metadata_file}")
        metadata = self.load_metadata()
        print(f"✓ Loaded metadata for {len(metadata.get('tracks', []))} tracks")
        
        # Extract unique tags
        print("\nExtracting unique tags...")
        unique_tags = self.extract_unique_tags(metadata)
        print(f"✓ Found {len(unique_tags)} unique tags")
        
        if len(unique_tags) == 0:
            print("No tags found in metadata. Make sure your tracks have assigned_tags.")
            return
        
        # Show first few tags as preview
        sorted_tags = sorted(unique_tags)
        preview_tags = sorted_tags[:5]
        print(f"Preview tags: {', '.join(preview_tags)}")
        if len(unique_tags) > 5:
            print(f"... and {len(unique_tags) - 5} more")
        
        # Create backup
        if not self.dry_run:
            self.backup_database()
        
        # Connect to database
        self.connect_to_database()
        
        # Clean up existing playlists first
        print(f"\nCleaning up existing playlists...")
        self.delete_existing_smart_playlists(unique_tags)
        
        print(f"\nCreating smart playlists...")
        created_playlists = []
        successful = 0
        failed = 0
        skipped = 0
        
        for i, tag in enumerate(sorted_tags, 1):
            print(f"[{i}/{len(unique_tags)}] Processing tag: '{tag}'")
            
            result = self.create_smart_playlist_for_tag(tag)
            if result is True:
                successful += 1
                created_playlists.append(tag)
            elif result is False and not self.playlist_exists(tag):
                failed += 1
            else:
                skipped += 1
        
        # Organize playlists by category
        if not self.dry_run or created_playlists:
            print(f"\nOrganizing playlists by category...")
            self.organize_playlists_by_category(unique_tags)
        
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
        print(f"   Total tags: {len(unique_tags)}")
        print(f"   Created: {successful}")
        print(f"   Skipped (existing): {skipped}")
        print(f"   Failed: {failed}")
        
        if self.dry_run:
            print("\n💡 Run without --dry-run to create the playlists")
        elif successful > 0:
            print(f"\n✅ Smart playlist creation complete!")
            print(f"   Open Rekordbox to see your new smart playlists")
        
        # Close database connection
        if self.db:
            self.db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create smart playlists in Rekordbox based on track tags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_smart_playlists.py --dry-run
  python create_smart_playlists.py --no-backup
  python create_smart_playlists.py --metadata my_metadata.json
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
        print("1. Run your FLAC tagger to create the metadata file")
        print("2. The metadata file contains tracks with assigned_tags")
        sys.exit(1)
    
    # Create and run the smart playlist creator
    creator = SmartPlaylistCreator(
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
