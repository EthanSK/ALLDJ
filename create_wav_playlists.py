#!/usr/bin/env python3

"""
WAV Playlist Creator for Rekordbox

This script creates WAV versions of the existing FLAC playlist structures:
- WAV ALLDJ Baked: Tag-based playlists with WAV files from '/Volumes/T7 Shield/3000AD/wav_liked_songs'
- WAV ALLDJ Stems: Tag-based playlists with Vocals/Instrumentals from '/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated'
- WAV OG Stems: Simple vocals/instrumentals structure from '/Volumes/T7 Shield/3000AD/wav_og_separated_v2'

Requirements:
- pyrekordbox library
- WAV files in specified directories
- music_collection_metadata.json with track tags
- Rekordbox should be closed when running this script

Usage:
    python create_wav_playlists.py [--dry-run] [--backup] [--test-only]
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
import unicodedata
import difflib

try:
    from pyrekordbox import Rekordbox6Database
except ImportError:
    print("Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    sys.exit(1)


class WAVPlaylistCreator:
    def __init__(self, metadata_file: str, dry_run: bool = False, backup: bool = True, test_only: bool = False):
        self.metadata_file = metadata_file
        self.dry_run = dry_run
        self.backup = backup
        self.test_only = test_only
        self.db = None
        self.metadata = None
        self.baked_playlists_dir = Path("baked_playlists_m3u8")
        
        # WAV directories
        self.wav_liked_songs_dir = Path("/Volumes/T7 Shield/3000AD/wav_liked_songs")
        self.wav_alldj_stems_dir = Path("/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated")
        self.wav_og_stems_dir = Path("/Volumes/T7 Shield/3000AD/wav_og_separated_v2")
        
        # File indexes for fast matching
        self.wav_liked_index: Dict[str, Path] = {}
        self.wav_alldj_stems_index: Dict[str, Dict[str, Path]] = {}
        self.wav_og_stems_index: Dict[str, Dict[str, Path]] = {}
        
        # Statistics
        self.missing_files: list[dict] = []
        self.import_failures: list[dict] = []
        
    def backup_database(self):
        """Create a backup of the Rekordbox database."""
        if not self.backup:
            return
            
        try:
            rekordbox_dir = Path.home() / "Library/Pioneer/rekordbox7"
            if not rekordbox_dir.exists():
                rekordbox_dir = Path.home() / "Library/Pioneer/rekordbox6"
            if not rekordbox_dir.exists():
                rekordbox_dir = Path.home() / "Library/Pioneer/rekordbox"
                
            if not rekordbox_dir.exists():
                print("Warning: Could not find Rekordbox database directory for backup")
                return
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = rekordbox_dir.parent / f"rekordbox_wav_backup_{timestamp}"
            
            print(f"Creating backup: {backup_dir}")
            shutil.copytree(rekordbox_dir, backup_dir)
            print(f"✓ Backup created successfully")
            
        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")
    
    def connect_to_database(self):
        """Connect to the Rekordbox database."""
        try:
            print("Connecting to Rekordbox database...")
            
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
            self.db = Rekordbox6Database(db_dir=str(db_path))
            print("✓ Connected successfully")
        except Exception as e:
            print(f"Error: Failed to connect to Rekordbox database: {e}")
            print("\nMake sure:")
            print("1. Rekordbox is completely closed")
            print("2. You have Rekordbox 6 or 7 installed")
            print("3. You have used Rekordbox at least once (to create the database)")
            
            if "key" in str(e).lower() or "unlock" in str(e).lower():
                print("\nDatabase encryption key issue detected:")
                print("Try running: python -m pyrekordbox download-key")
            
            sys.exit(1)
    
    def load_metadata(self) -> dict:
        """Load the music metadata from JSON file."""
        if self.metadata is None:
            try:
                print(f"Loading metadata from {self.metadata_file}...")
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                print(f"✓ Loaded metadata with {len(self.metadata.get('tracks', []))} tracks")
            except FileNotFoundError:
                print(f"Error: Metadata file '{self.metadata_file}' not found.")
                sys.exit(1)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in metadata file: {e}")
                sys.exit(1)
        return self.metadata

    def normalize_title(self, text: str) -> str:
        """Normalize a title/filename for robust matching."""
        if not text:
            return ""

        # Remove extension if present
        text = Path(text).stem

        # Unicode normalize and strip diacritics
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        lowered = text.lower()

        # Drop AppleDouble prefix if present
        if lowered.startswith("._"):
            lowered = lowered[2:]

        # Remove leading numeric index patterns
        lowered = re.sub(r"^[\s\-_.]*\d{1,3}([\-_]\d{1,3})?[\s\-_.]*", "", lowered)

        # Remove stem designation parts
        lowered = re.sub(r"\((?:vocals?|instrumentals?)\)", "", lowered)
        lowered = re.sub(r"\b(?:vocals?|instrumentals?|no_vocals|music|instru)\b", "", lowered)

        # Replace separators with spaces
        lowered = re.sub(r"[\-_]+", " ", lowered)

        # Normalize &/and, remove common noise words and bracketed descriptors
        lowered = lowered.replace("&", " and ")
        lowered = re.sub(r"\[(.*?)\]|\{(.*?)\}", " ", lowered)
        # Remove common release descriptors
        lowered = re.sub(r"\b(remaster(?:ed)?|mono|stereo|version|edit|mix|remix|live|radio|extended)\b", " ", lowered)
        # Remove feat/featuring credits
        lowered = re.sub(r"\b(feat\.?|featuring)\b.*$", " ", lowered)

        # Collapse punctuation to spaces
        lowered = re.sub(r"[\.,:;!\?\"'`/\\]+", " ", lowered)

        # Collapse whitespace
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def build_wav_indexes(self):
        """Build indexes for all WAV directories."""
        print("Building WAV file indexes...")
        
        # Build liked songs index
        print("  Indexing WAV liked songs...")
        for path in self.wav_liked_songs_dir.glob("*.wav"):
            if path.name.startswith("._"):
                continue
            normalized = self.normalize_title(path.stem)
            if normalized:
                self.wav_liked_index[normalized] = path
        print(f"    ✓ Indexed {len(self.wav_liked_index)} liked songs")
        
        # Build ALLDJ stems index
        print("  Indexing WAV ALLDJ stems...")
        for path in self.wav_alldj_stems_dir.glob("*.wav"):
            if path.name.startswith("._"):
                continue
            
            file_name_lc = path.stem.lower()
            stem_type = None
            
            if "(vocals)" in file_name_lc:
                stem_type = "vocals"
            elif "(instrumental)" in file_name_lc or "(instrumentals)" in file_name_lc:
                stem_type = "instrumental"
            
            if stem_type:
                base_title = self.normalize_title(path.stem)
                if base_title:
                    bucket = self.wav_alldj_stems_index.setdefault(base_title, {"vocals": None, "instrumental": None})
                    if bucket[stem_type] is None:
                        bucket[stem_type] = path
        print(f"    ✓ Indexed {len(self.wav_alldj_stems_index)} ALLDJ stems")
        
        # Build OG stems index
        print("  Indexing WAV OG stems...")
        for path in self.wav_og_stems_dir.glob("*.wav"):
            if path.name.startswith("._"):
                continue
            
            file_name_lc = path.stem.lower()
            stem_type = None
            
            if "(vocals)" in file_name_lc:
                stem_type = "vocals"
            elif "(instrumental)" in file_name_lc or "(instrumentals)" in file_name_lc:
                stem_type = "instrumental"
            
            if stem_type:
                base_title = self.normalize_title(path.stem)
                if base_title:
                    bucket = self.wav_og_stems_index.setdefault(base_title, {"vocals": None, "instrumental": None})
                    if bucket[stem_type] is None:
                        bucket[stem_type] = path
        print(f"    ✓ Indexed {len(self.wav_og_stems_index)} OG stems")

    def find_wav_file(self, original_filename: str, title: str, source: str) -> Path:
        """Find corresponding WAV file for a track."""
        # Normalize the search terms
        norm_title = self.normalize_title(title or "")
        norm_filename = self.normalize_title(original_filename or "")
        
        # Choose the appropriate index
        if source == "liked":
            index = self.wav_liked_index
            candidates = [norm_title, norm_filename]
            
            for candidate in candidates:
                if candidate and candidate in index:
                    return index[candidate]
                    
        return None

    def find_wav_stem_files(self, original_filename: str, title: str, source: str) -> Dict[str, Path]:
        """Find vocal and instrumental WAV stem files for a track."""
        result = {"vocals": None, "instrumental": None}
        
        # Normalize the search terms
        norm_title = self.normalize_title(title or "")
        norm_filename = self.normalize_title(original_filename or "")
        
        # Choose the appropriate index
        if source == "alldj_stems":
            index = self.wav_alldj_stems_index
        elif source == "og_stems":
            index = self.wav_og_stems_index
        else:
            return result
        
        candidates = [norm_title, norm_filename]
        
        for candidate in candidates:
            if candidate and candidate in index:
                bucket = index[candidate]
                result["vocals"] = bucket.get("vocals")
                result["instrumental"] = bucket.get("instrumental")
                if result["vocals"] or result["instrumental"]:
                    break
                    
        return result

    def find_matching_flac_metadata(self, wav_filename: str, title: str):
        """Find metadata for the corresponding FLAC file"""
        wav_normalized = self.normalize_title(wav_filename)
        title_normalized = self.normalize_title(title or "")
        
        metadata = self.load_metadata()
        
        # Search through all tracks in metadata
        for track in metadata.get('tracks', []):
            # Try matching by title first
            track_title = track.get('title', '') or track.get('Title', '')
            if track_title:
                track_title_normalized = self.normalize_title(track_title)
                if track_title_normalized and (track_title_normalized == wav_normalized or track_title_normalized == title_normalized):
                    return track
            
            # Try matching by filename
            filename = track.get('filename', '')
            if filename:
                filename_normalized = self.normalize_title(filename)
                if filename_normalized and (filename_normalized == wav_normalized or filename_normalized == title_normalized):
                    return track
        
        return None

    def apply_metadata_to_wav(self, wav_content, flac_metadata):
        """Apply FLAC metadata to WAV content in Rekordbox"""
        if not flac_metadata:
            return False
            
        try:
            # Prepare metadata fields
            updates = {}
            
            # Title
            if flac_metadata.get('title') or flac_metadata.get('Title'):
                updates['Title'] = flac_metadata.get('title') or flac_metadata.get('Title')
            
            # Comments with tags
            comments = []
            if flac_metadata.get('assigned_tags'):
                tags = flac_metadata.get('assigned_tags', [])
                comments.append(f"Tags: {', '.join(tags)}")
            
            if flac_metadata.get('comment') or flac_metadata.get('Comment'):
                original_comment = flac_metadata.get('comment') or flac_metadata.get('Comment')
                comments.append(original_comment)
            
            if comments:
                updates['Comments'] = ' | '.join(comments)
            
            # Apply updates using direct attribute setting (pyrekordbox limitation)
            if updates:
                for field, value in updates.items():
                    try:
                        if field == 'Title':
                            setattr(wav_content, field, value)
                        elif field == 'Comments':
                            setattr(wav_content, field, value)
                    except Exception:
                        pass  # Ignore errors, some fields may not be settable
                
                return True
            
            return False
            
        except Exception:
            return False

    def add_wav_to_rekordbox(self, wav_path: Path, original_filename: str = "", title: str = ""):
        """Add WAV file to Rekordbox with metadata from FLAC if not already present."""
        try:
            absolute_path = wav_path.resolve()
            
            # Check if already exists
            existing = self.db.get_content(FolderPath=str(absolute_path)).first()
            if existing:
                # Try to apply metadata to existing content
                flac_metadata = self.find_matching_flac_metadata(wav_path.stem, title)
                if flac_metadata:
                    self.apply_metadata_to_wav(existing, flac_metadata)
                return existing
            
            # Add new content
            try:
                new_content = self.db.add_content(str(absolute_path))
                if new_content:
                    # Apply metadata from matching FLAC file
                    flac_metadata = self.find_matching_flac_metadata(wav_path.stem, title)
                    if flac_metadata:
                        self.apply_metadata_to_wav(new_content, flac_metadata)
                return new_content
            except Exception as e:
                print(f"          Warning: Failed to import WAV into Rekordbox: {absolute_path}: {e}")
                return None
                
        except Exception as e:
            print(f"    Warning: Could not process WAV file: {wav_path}: {e}")
            return None

    def playlist_exists(self, name: str) -> bool:
        """Check if a playlist with the given name already exists."""
        try:
            result = self.db.get_playlist(Name=name).first()
            return result is not None
        except:
            return False

    def find_tracks_with_tag(self, tag: str) -> List[dict]:
        """Find all tracks that have the specified tag."""
        metadata = self.load_metadata()
        tracks_with_tag = []
        
        for track in metadata.get('tracks', []):
            assigned_tags = track.get('assigned_tags', [])
            if tag in assigned_tags:
                tracks_with_tag.append(track)
                
        return tracks_with_tag

    def find_baked_tags(self) -> Set[str]:
        """Discover the curated set of tags from baked M3U8 filenames."""
        tags: Set[str] = set()
        try:
            if not self.baked_playlists_dir.exists():
                print(f"Error: Baked playlists directory '{self.baked_playlists_dir}' not found")
                return tags
            for m3u8_file in sorted(self.baked_playlists_dir.glob("*.m3u8")):
                name = m3u8_file.stem
                if name.endswith("_Baked"):
                    tag = name[:-6]
                else:
                    tag = name
                if tag:
                    tags.add(tag)
        except Exception as e:
            print(f"Warning: Failed to read baked playlists: {e}")
        return tags

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
        return "Other Tags"

    def find_child_folder(self, parent_folder, name: str):
        """Find a child playlist folder with a given name under a specific parent."""
        try:
            matches = self.db.get_playlist(Name=name).all()
        except Exception:
            matches = []
        for pl in matches:
            try:
                if getattr(pl, 'ParentID', None) == getattr(parent_folder, 'ID', None):
                    return pl
            except Exception:
                continue
        return None

    def create_wav_baked_structure(self, tags: Set[str]):
        """Create WAV ALLDJ Baked folder structure."""
        print("\nCreating WAV ALLDJ Baked structure...")
        
        # Create main folder
        main_folder_name = "WAV ALLDJ Baked"
        if self.playlist_exists(main_folder_name):
            if not self.dry_run:
                main_folder = self.db.get_playlist(Name=main_folder_name).first()
                print(f"Using existing folder: '{main_folder_name}'")
            else:
                print(f"[DRY RUN] Would use existing folder: '{main_folder_name}'")
                main_folder = None
        else:
            if self.dry_run:
                print(f"[DRY RUN] Would create main folder: '{main_folder_name}'")
                main_folder = None
            else:
                main_folder = self.db.create_playlist_folder(main_folder_name)
                print(f"✓ Created main folder: '{main_folder_name}'")

        # Group tags by category
        categories = self.get_tag_categories()
        tag_to_category = {}
        for category, category_tags in categories.items():
            for tag in category_tags:
                if tag in tags:
                    tag_to_category[tag] = category

        category_tags = {}
        for tag in tags:
            category = tag_to_category.get(tag, "Other Tags")
            if category not in category_tags:
                category_tags[category] = []
            category_tags[category].append(tag)

        total_playlists_created = 0
        processed_tags = 0
        
        # Limit to first 5 tags if testing
        if self.test_only:
            limited_tags = list(tags)[:5]
            print(f"[TEST MODE] Processing only first 5 tags: {limited_tags}")
            tags = set(limited_tags)

        for category, cat_tags in category_tags.items():
            if not cat_tags:
                continue
                
            print(f"\nProcessing category: '{category}' ({len(cat_tags)} tags)")
            
            # Create category folder
            if self.dry_run:
                category_folder = None
                print(f"  [DRY RUN] Would create category folder: '{category}'")
            else:
                category_folder = self.find_child_folder(main_folder, category)
                if category_folder:
                    print(f"  Using existing category folder: '{category}'")
                else:
                    category_folder = self.db.create_playlist_folder(category, parent=main_folder)
                    print(f"  ✓ Created category folder: '{category}'")

            # Create playlists for each tag
            for tag in sorted(cat_tags):
                processed_tags += 1
                tracks_with_tag = self.find_tracks_with_tag(tag)
                
                if not tracks_with_tag:
                    print(f"    No tracks found with tag '{tag}', skipping")
                    continue
                
                playlist_name = f"{tag} WAV Baked"
                print(f"    Processing tag '{tag}' ({len(tracks_with_tag)} tracks)")
                
                if self.dry_run:
                    found_wavs = 0
                    for track in tracks_with_tag:
                        wav_file = self.find_wav_file(
                            track.get('filename', ''),
                            track.get('title') or track.get('Title') or '',
                            'liked'
                        )
                        if wav_file:
                            found_wavs += 1
                    print(f"      [DRY RUN] Would create playlist '{playlist_name}' with {found_wavs} WAV files")
                else:
                    created = self.create_wav_playlist(playlist_name, tracks_with_tag, 'liked', category_folder)
                    if created:
                        total_playlists_created += 1

        return total_playlists_created

    def create_wav_stems_structure(self, tags: Set[str], structure_name: str, wav_source: str):
        """Create WAV stems folder structure (ALLDJ or OG)."""
        print(f"\nCreating {structure_name} structure...")
        
        # Create main folder
        main_folder_name = structure_name
        if self.playlist_exists(main_folder_name):
            if not self.dry_run:
                main_folder = self.db.get_playlist(Name=main_folder_name).first()
                print(f"Using existing folder: '{main_folder_name}'")
            else:
                print(f"[DRY RUN] Would use existing folder: '{main_folder_name}'")
                main_folder = None
        else:
            if self.dry_run:
                print(f"[DRY RUN] Would create main folder: '{main_folder_name}'")
                main_folder = None
            else:
                main_folder = self.db.create_playlist_folder(main_folder_name)
                print(f"✓ Created main folder: '{main_folder_name}'")

        total_playlists_created = 0
        
        if wav_source == "og_stems":
            # OG Stems: Simple vocals/instrumentals structure
            vocals_playlist_name = "WAV OG Vocals (All)"
            instrumentals_playlist_name = "WAV OG Instrumentals (All)"
            
            # Get all tracks from metadata
            metadata = self.load_metadata()
            all_tracks = metadata.get('tracks', [])
            
            if self.test_only:
                all_tracks = all_tracks[:50]  # Limit for testing
                print(f"[TEST MODE] Processing only first 50 tracks")
            
            print(f"Processing {len(all_tracks)} tracks for OG stems")
            
            # Create vocals playlist
            if self.dry_run:
                found_vocals = 0
                for track in all_tracks:
                    stems = self.find_wav_stem_files(
                        track.get('filename', ''),
                        track.get('title') or track.get('Title') or '',
                        'og_stems'
                    )
                    if stems.get('vocals'):
                        found_vocals += 1
                print(f"  [DRY RUN] Would create playlist '{vocals_playlist_name}' with {found_vocals} vocals")
            else:
                created = self.create_wav_stem_playlist(vocals_playlist_name, all_tracks, 'vocals', 'og_stems', main_folder)
                if created:
                    total_playlists_created += 1
            
            # Create instrumentals playlist
            if self.dry_run:
                found_instrumentals = 0
                for track in all_tracks:
                    stems = self.find_wav_stem_files(
                        track.get('filename', ''),
                        track.get('title') or track.get('Title') or '',
                        'og_stems'
                    )
                    if stems.get('instrumental'):
                        found_instrumentals += 1
                print(f"  [DRY RUN] Would create playlist '{instrumentals_playlist_name}' with {found_instrumentals} instrumentals")
            else:
                created = self.create_wav_stem_playlist(instrumentals_playlist_name, all_tracks, 'instrumental', 'og_stems', main_folder)
                if created:
                    total_playlists_created += 1
        else:
            # ALLDJ Stems: Tag-based structure with vocals/instrumentals
            # Group tags by category
            categories = self.get_tag_categories()
            tag_to_category = {}
            for category, category_tags in categories.items():
                for tag in category_tags:
                    if tag in tags:
                        tag_to_category[tag] = category

            category_tags = {}
            for tag in tags:
                category = tag_to_category.get(tag, "Other Tags")
                if category not in category_tags:
                    category_tags[category] = []
                category_tags[category].append(tag)

            # Limit to first 5 tags if testing
            if self.test_only:
                limited_tags = list(tags)[:5]
                print(f"[TEST MODE] Processing only first 5 tags: {limited_tags}")
                tags = set(limited_tags)
                # Rebuild category_tags with limited set
                category_tags = {}
                for tag in tags:
                    category = tag_to_category.get(tag, "Other Tags")
                    if category not in category_tags:
                        category_tags[category] = []
                    category_tags[category].append(tag)

            for category, cat_tags in category_tags.items():
                if not cat_tags:
                    continue
                    
                print(f"\nProcessing category: '{category}' ({len(cat_tags)} tags)")
                
                # Create category folder with vocals/instrumentals subfolders
                if self.dry_run:
                    category_folder = None
                    vocals_folder = None
                    instrumentals_folder = None
                    print(f"  [DRY RUN] Would create category '{category}' with 'Vocals' and 'Instrumentals' subfolders")
                else:
                    category_folder = self.find_child_folder(main_folder, category)
                    if category_folder:
                        print(f"  Using existing category folder: '{category}'")
                    else:
                        category_folder = self.db.create_playlist_folder(category, parent=main_folder)
                        print(f"  ✓ Created category folder: '{category}'")
                    
                    # Create Vocals subfolder
                    vocals_folder = self.find_child_folder(category_folder, "Vocals")
                    if vocals_folder:
                        print(f"    Using existing vocals folder")
                    else:
                        vocals_folder = self.db.create_playlist_folder("Vocals", parent=category_folder)
                        print(f"    ✓ Created vocals folder")
                    
                    # Create Instrumentals subfolder
                    instrumentals_folder = self.find_child_folder(category_folder, "Instrumentals")
                    if instrumentals_folder:
                        print(f"    Using existing instrumentals folder")
                    else:
                        instrumentals_folder = self.db.create_playlist_folder("Instrumentals", parent=category_folder)
                        print(f"    ✓ Created instrumentals folder")

                # Create playlists for each tag
                for tag in sorted(cat_tags):
                    tracks_with_tag = self.find_tracks_with_tag(tag)
                    
                    if not tracks_with_tag:
                        print(f"      No tracks found with tag '{tag}', skipping")
                        continue
                    
                    print(f"      Processing tag '{tag}' ({len(tracks_with_tag)} tracks)")
                    
                    vocals_playlist_name = f"{tag} WAV Vocals"
                    instrumentals_playlist_name = f"{tag} WAV Instrumentals"
                    
                    if self.dry_run:
                        found_vocals = 0
                        found_instrumentals = 0
                        for track in tracks_with_tag:
                            stems = self.find_wav_stem_files(
                                track.get('filename', ''),
                                track.get('title') or track.get('Title') or '',
                                wav_source
                            )
                            if stems.get('vocals'):
                                found_vocals += 1
                            if stems.get('instrumental'):
                                found_instrumentals += 1
                        print(f"        [DRY RUN] Would create '{vocals_playlist_name}' with {found_vocals} vocals")
                        print(f"        [DRY RUN] Would create '{instrumentals_playlist_name}' with {found_instrumentals} instrumentals")
                    else:
                        vocals_created = self.create_wav_stem_playlist(vocals_playlist_name, tracks_with_tag, 'vocals', wav_source, vocals_folder)
                        instrumentals_created = self.create_wav_stem_playlist(instrumentals_playlist_name, tracks_with_tag, 'instrumental', wav_source, instrumentals_folder)
                        
                        if vocals_created:
                            total_playlists_created += 1
                        if instrumentals_created:
                            total_playlists_created += 1

        return total_playlists_created

    def create_wav_playlist(self, playlist_name: str, tracks: List[dict], wav_source: str, parent_folder):
        """Create a playlist with WAV files."""
        # Delete existing playlist if it exists
        if self.playlist_exists(playlist_name):
            try:
                if not self.dry_run:
                    existing_playlist = self.db.get_playlist(Name=playlist_name).first()
                    if existing_playlist:
                        self.db.delete_playlist(existing_playlist)
                        print(f"        ✓ Deleted existing playlist '{playlist_name}'")
                else:
                    print(f"        [DRY RUN] Would delete existing playlist '{playlist_name}'")
            except Exception as e:
                print(f"        Warning: Could not delete existing playlist '{playlist_name}': {e}")

        if self.dry_run:
            return True

        try:
            # Create the playlist
            playlist = self.db.create_playlist(playlist_name, parent=parent_folder)
            
            # Add WAV files to the playlist
            added_count = 0
            missing_count = 0
            import_failed = 0
            
            for track in tracks:
                wav_file = self.find_wav_file(
                    track.get('filename', ''),
                    track.get('title') or track.get('Title') or '',
                    wav_source
                )

                if wav_file:
                    # Try to add WAV file to Rekordbox with metadata
                    rekordbox_track = self.add_wav_to_rekordbox(
                        wav_file, 
                        track.get('filename', ''),
                        track.get('title') or track.get('Title') or ''
                    )
                    if rekordbox_track:
                        try:
                            self.db.add_to_playlist(playlist, rekordbox_track)
                            added_count += 1
                        except Exception as e:
                            print(f"          Warning: Could not add WAV to playlist: {wav_file.name}: {e}")
                            import_failed += 1
                    else:
                        import_failed += 1
                else:
                    missing_count += 1

            if added_count > 0:
                print(f"        ✓ Created playlist '{playlist_name}' with {added_count} WAV files")
            else:
                print(f"        ⚠️  Created empty playlist '{playlist_name}' - no WAV files found")

            if missing_count > 0 or import_failed > 0:
                details = []
                if missing_count:
                    details.append(f"missing: {missing_count}")
                if import_failed:
                    details.append(f"import failed: {import_failed}")
                print(f"          ({', '.join(details)})")
            
            return True
            
        except Exception as e:
            print(f"        ✗ Failed to create playlist '{playlist_name}': {e}")
            return False

    def create_wav_stem_playlist(self, playlist_name: str, tracks: List[dict], stem_type: str, wav_source: str, parent_folder):
        """Create a playlist for a specific stem type with WAV files."""
        # Delete existing playlist if it exists
        if self.playlist_exists(playlist_name):
            try:
                if not self.dry_run:
                    existing_playlist = self.db.get_playlist(Name=playlist_name).first()
                    if existing_playlist:
                        self.db.delete_playlist(existing_playlist)
                        print(f"          ✓ Deleted existing playlist '{playlist_name}'")
                else:
                    print(f"          [DRY RUN] Would delete existing playlist '{playlist_name}'")
            except Exception as e:
                print(f"          Warning: Could not delete existing playlist '{playlist_name}': {e}")

        if self.dry_run:
            return True

        try:
            # Create the playlist
            playlist = self.db.create_playlist(playlist_name, parent=parent_folder)
            
            # Add stem files to the playlist
            added_count = 0
            missing_count = 0
            import_failed = 0
            
            for track in tracks:
                stems = self.find_wav_stem_files(
                    track.get('filename', ''),
                    track.get('title') or track.get('Title') or '',
                    wav_source
                )
                
                key = stem_type if stem_type != 'instrumentals' else 'instrumental'
                stem_file = stems.get(key)

                if stem_file:
                    # Try to add stem file to Rekordbox with metadata
                    rekordbox_track = self.add_wav_to_rekordbox(
                        stem_file,
                        track.get('filename', ''),
                        track.get('title') or track.get('Title') or ''
                    )
                    if rekordbox_track:
                        try:
                            self.db.add_to_playlist(playlist, rekordbox_track)
                            added_count += 1
                        except Exception as e:
                            print(f"            Warning: Could not add stem to playlist: {stem_file.name}: {e}")
                            import_failed += 1
                    else:
                        import_failed += 1
                else:
                    missing_count += 1

            if added_count > 0:
                print(f"          ✓ Created playlist '{playlist_name}' with {added_count} stems")
            else:
                print(f"          ⚠️  Created empty playlist '{playlist_name}' - no stems found")

            if missing_count > 0 or import_failed > 0:
                details = []
                if missing_count:
                    details.append(f"missing: {missing_count}")
                if import_failed:
                    details.append(f"import failed: {import_failed}")
                print(f"            ({', '.join(details)})")
            
            return True
            
        except Exception as e:
            print(f"          ✗ Failed to create playlist '{playlist_name}': {e}")
            return False

    def run(self):
        """Main execution function."""
        print("🎵 WAV Playlist Creator for Rekordbox")
        print("====================================")
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
        
        if self.test_only:
            print("🧪 TEST MODE - Only processing first 5 items")
        
        # Check WAV directories
        for name, directory in [
            ("WAV liked songs", self.wav_liked_songs_dir),
            ("WAV ALLDJ stems", self.wav_alldj_stems_dir),
            ("WAV OG stems", self.wav_og_stems_dir)
        ]:
            if not directory.exists():
                print(f"Error: {name} directory '{directory}' not found")
                sys.exit(1)
            print(f"{name} directory: {directory}")

        # Build WAV indexes
        self.build_wav_indexes()
        
        # Create backup unless dry run
        if not self.dry_run:
            self.backup_database()
        
        # Connect to database
        self.connect_to_database()
        
        # Load metadata and find baked tags
        metadata = self.load_metadata()
        print("Collecting baked tags from M3U8 files...")
        baked_tags = self.find_baked_tags()
        if not baked_tags:
            print("Error: No baked tags found. Ensure 'baked_playlists_m3u8/' has M3U8 files.")
            sys.exit(1)
        print(f"Found {len(baked_tags)} baked tags")

        total_playlists_created = 0

        # Create WAV ALLDJ Baked structure
        baked_playlists = self.create_wav_baked_structure(baked_tags)
        total_playlists_created += baked_playlists

        # Create WAV ALLDJ Stems structure
        alldj_stems_playlists = self.create_wav_stems_structure(baked_tags, "WAV ALLDJ Stems", "alldj_stems")
        total_playlists_created += alldj_stems_playlists

        # Create WAV OG Stems structure
        og_stems_playlists = self.create_wav_stems_structure(set(), "WAV OG Stems", "og_stems")
        total_playlists_created += og_stems_playlists

        # Commit changes
        if not self.dry_run and total_playlists_created > 0:
            print(f"\nCommitting changes to database...")
            try:
                self.db.commit()
                print("✓ Changes committed successfully")
            except Exception as e:
                print(f"✗ Error committing changes: {e}")

        # Summary
        print(f"\n📊 Summary:")
        print(f"   Total playlists created: {total_playlists_created}")
        print(f"   WAV Baked: {baked_playlists}")
        print(f"   WAV ALLDJ Stems: {alldj_stems_playlists}")
        print(f"   WAV OG Stems: {og_stems_playlists}")

        if self.dry_run:
            print("\n💡 Run without --dry-run to create the WAV playlists")
        elif total_playlists_created > 0:
            print(f"\n✅ WAV playlist creation complete!")
            print(f"   Open Rekordbox to see your new WAV playlist structures")

        # Close database connection
        if self.db:
            self.db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create WAV playlists in Rekordbox mirroring FLAC structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_wav_playlists.py --dry-run
  python create_wav_playlists.py --test-only
  python create_wav_playlists.py --no-backup
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
    
    parser.add_argument(
        "--test-only",
        action="store_true", 
        help="Only process first 5 items to test the setup"
    )
    
    args = parser.parse_args()
    
    # Check if metadata file exists
    if not os.path.exists(args.metadata):
        print(f"Error: Metadata file '{args.metadata}' not found.")
        sys.exit(1)
    
    # Create and run the WAV playlist creator
    creator = WAVPlaylistCreator(
        metadata_file=args.metadata,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        test_only=args.test_only
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
