#!/usr/bin/env python3

"""
Stems Playlist Creator for Rekordbox

This script creates a mirrored structure of the ALLDJ baked playlists but for
stem-separated tracks. It creates folders for each tag category with "Vocals" 
and "Instrumentals" subfolders, then populates playlists in each subfolder
with the corresponding stem files.

Requirements:
- pyrekordbox library
- Stem separated files in specified directory
- music_collection_metadata.json with track tags
- Rekordbox should be closed when running this script

Usage:
    python create_stems_playlists.py [--dry-run] [--backup]
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


class StemsPlaylistCreator:
    def __init__(self, metadata_file: str, stems_dir: str, dry_run: bool = False, backup: bool = True):
        self.metadata_file = metadata_file
        self.stems_dir = Path(stems_dir)
        self.dry_run = dry_run
        self.backup = backup
        self.db = None
        self.metadata = None
        self.baked_playlists_dir = Path("baked_playlists_m3u8")
        # Index: normalized_title -> { 'vocals': Path | None, 'instrumental': Path | None }
        self.stems_index: Dict[str, Dict[str, Path]] = {}
        # Diagnostics
        self.missing_stems: list[dict] = []  # entries missing on disk
        self.import_failures: list[dict] = []  # entries that existed on disk but could not be imported
        
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
            backup_dir = rekordbox_dir.parent / f"rekordbox_stems_backup_{timestamp}"
            
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
        """Normalize a title/filename fragment for robust matching.

        - Lowercase
        - Remove leading index numbers and delimiters (e.g., "12_", "02-06 ")
        - Collapse whitespace and underscores/dashes to single spaces
        - Strip common punctuation; keep semantic words
        """
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

        # Remove leading numeric index patterns like "12_", "02-06 ", "21-", etc.
        lowered = re.sub(r"^[\s\-_.]*\d{1,3}([\-_]\d{1,3})?[\s\-_.]*", "", lowered)

        # Remove stem designation parts in parentheses or after underscore, keep base title only
        # e.g., "song_name_(vocals)" -> "song_name"
        lowered = re.sub(r"\((?:vocals?|instrumentals?)\)", "", lowered)
        lowered = re.sub(r"\b(?:vocals?|instrumentals?|no_vocals|music|instru)\b", "", lowered)

        # Replace separators with spaces
        lowered = re.sub(r"[\-_]+", " ", lowered)

        # Normalize &/and, remove common noise words and bracketed descriptors
        lowered = lowered.replace("&", " and ")
        lowered = re.sub(r"\[(.*?)\]|\{(.*?)\}", " ", lowered)  # strip [] and {}
        # Remove common release descriptors
        lowered = re.sub(r"\b(remaster(?:ed)?|mono|stereo|version|edit|mix|remix|live|radio|extended)\b", " ", lowered)
        # Remove feat/featuring credits
        lowered = re.sub(r"\b(feat\.?|featuring)\b.*$", " ", lowered)

        # Collapse punctuation to spaces
        lowered = re.sub(r"[\.,:;!\?\"'`/\\]+", " ", lowered)

        # Collapse whitespace
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def build_stems_index(self):
        """Scan the stems directory and build an index by normalized title."""
        print("Indexing stems directory for fast matching...")
        count_total = 0
        count_indexed = 0
        for path in self.stems_dir.rglob("*"):
            if not path.is_file():
                continue
            # Skip AppleDouble metadata files
            if path.name.startswith("._"):
                continue
            if path.suffix.lower() not in {".flac", ".wav", ".mp3", ".aiff", ".aif"}:
                continue

            count_total += 1
            file_name_lc = path.stem.lower()

            stem_type: str | None = None
            # Prefer explicit parentheses markers
            if "(vocals)" in file_name_lc:
                stem_type = "vocals"
            elif "(instrumental)" in file_name_lc or "(instrumentals)" in file_name_lc:
                stem_type = "instrumental"
            else:
                # Fallback to keyword matching
                if re.search(r"\bvocals?\b", file_name_lc):
                    stem_type = "vocals"
                elif re.search(r"\binstrumentals?\b|\binstru\b|\bmusic\b|\bno_vocals\b", file_name_lc):
                    stem_type = "instrumental"

            # Derive a normalized base title without the stem tag
            base_title = self.normalize_title(path.stem)
            if not base_title or not stem_type:
                continue

            bucket = self.stems_index.setdefault(base_title, {"vocals": None, "instrumental": None})
            # Do not overwrite if already present; keep first occurrence
            if bucket[stem_type] is None:
                bucket[stem_type] = path
                count_indexed += 1

        print(f"✓ Indexed {count_indexed} stem entries from {count_total} audio files")
        # Cache keys for fuzzy matching
        self._stems_keys = list(self.stems_index.keys())

    def _tokenize(self, text: str) -> set:
        text = self.normalize_title(text)
        if not text:
            return set()
        tokens = set(text.split())
        # Remove common stopwords that add noise
        stop = {
            "the", "a", "an", "and", "to", "of", "in", "on", "for", "with", "at", "by",
            "is", "it", "its", "this", "that", "my", "your", "our", "we", "you", "me"
        }
        return {t for t in tokens if t not in stop}

    def _best_stems_key_match(self, query: str) -> tuple[str | None, float]:
        """Return the best matching stems_index key for query using token overlap and difflib.

        Returns (key, score). Score in [0,1]."""
        if not getattr(self, "_stems_keys", None):
            self._stems_keys = list(self.stems_index.keys())

        q_norm = self.normalize_title(query)
        if not q_norm:
            return None, 0.0

        q_tokens = self._tokenize(q_norm)
        best_key = None
        best_score = 0.0
        for key in self._stems_keys:
            # quick prefix/contains boosts
            prefix_boost = 0.0
            if key.startswith(q_norm) or q_norm.startswith(key):
                prefix_boost += 0.1
            if key in q_norm or q_norm in key:
                prefix_boost += 0.05

            # token overlap (Jaccard)
            k_tokens = self._tokenize(key)
            if not k_tokens and not q_tokens:
                overlap = 1.0
            else:
                inter = len(q_tokens & k_tokens)
                union = len(q_tokens | k_tokens) or 1
                overlap = inter / union

            # character similarity
            char_sim = difflib.SequenceMatcher(None, q_norm, key).ratio()

            score = 0.6 * overlap + 0.4 * char_sim + prefix_boost
            if score > best_score:
                best_key, best_score = key, score

        return best_key, best_score
    
    def find_tracks_with_tag(self, tag: str) -> List[dict]:
        """Find all tracks that have the specified tag in their assigned_tags."""
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
    
    def find_stem_files(self, original_filename: str, title: str) -> Dict[str, Path]:
        """Find vocal and instrumental stem files for a given track.

        Matches by normalized song title against a prebuilt stems index.
        """
        result: Dict[str, Path] = {"vocals": None, "instrumental": None}

        # Prefer matching by title
        norm_title = self.normalize_title(title or "")
        if norm_title and norm_title in self.stems_index:
            bucket = self.stems_index[norm_title]
            result["vocals"] = bucket.get("vocals")
            result["instrumental"] = bucket.get("instrumental")
            return result

        # Fallback to using the filename (less reliable)
        norm_from_filename = self.normalize_title(original_filename or "")
        if norm_from_filename and norm_from_filename in self.stems_index:
            bucket = self.stems_index[norm_from_filename]
            result["vocals"] = bucket.get("vocals")
            result["instrumental"] = bucket.get("instrumental")
            if result["vocals"] or result["instrumental"]:
                return result

        # Intelligent fuzzy matching: try title, then filename, then artist + title
        candidates = []
        if title:
            candidates.append(title)
        if original_filename:
            candidates.append(original_filename)
        # Attempt artist + title context if available via metadata lookup later

        best_bucket = None
        best_score = 0.0
        for cand in candidates:
            key, score = self._best_stems_key_match(cand)
            if key and score > best_score:
                best_bucket = self.stems_index.get(key)
                best_score = score

        # If still nothing, try a more aggressive candidate from combined artist + title
        if not best_bucket:
            # Attempt to pull artist from the metadata file by searching the filename
            # Note: lightweight scan just for the needed fields to avoid heavy costs
            try:
                meta = self.load_metadata()
                for tr in meta.get('tracks', []):
                    if tr.get('filename') == original_filename or tr.get('title') == title:
                        artist = tr.get('artist') or tr.get('albumartist') or ''
                        if artist and title:
                            combo = f"{artist} {title}"
                            key, score = self._best_stems_key_match(combo)
                            if key and score > best_score:
                                best_bucket = self.stems_index.get(key)
                                best_score = score
                        break
            except Exception:
                pass

        # Apply threshold to avoid bad matches
        if best_bucket and best_score >= 0.72:  # tuned threshold
            result["vocals"] = best_bucket.get("vocals")
            result["instrumental"] = best_bucket.get("instrumental")

        return result
    
    def add_stem_to_rekordbox(self, stem_path: Path):
        """Ensure the stem file is in Rekordbox, using the absolute path under stems_dir.

        Returns the DjmdContent if present/created, else None.
        """
        try:
            # Ensure absolute path
            absolute_path = stem_path if stem_path.is_absolute() else (self.stems_dir / stem_path)
            absolute_path = absolute_path.resolve()

            # Verify path is inside configured stems_dir
            try:
                stems_root = self.stems_dir.resolve()
                if stems_root not in absolute_path.parents and absolute_path != stems_root:
                    print(f"          Warning: Stem path outside stems_dir, skipping: {absolute_path}")
                    return None
            except Exception:
                pass

            # Check if exact path already exists in RB DB
            existing_by_path = self.db.get_content(FolderPath=str(absolute_path)).first()
            if existing_by_path:
                return existing_by_path

            # If not present, add/import by absolute path
            try:
                new_content = self.db.add_content(str(absolute_path))
                return new_content
            except Exception as e:
                print(f"          Warning: Failed to import stem into Rekordbox: {absolute_path}: {e}")
                return None

        except Exception as e:
            print(f"    Warning: Could not process stem file for Rekordbox: {stem_path}: {e}")
            return None
    
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

    def create_stems_structure(self):
        """Create root folder 'ALLDJ Stems'.

        Returns the main folder object (or None in dry-run).
        """
        try:
            main_folder_name = "ALLDJ Stems"

            if self.playlist_exists(main_folder_name):
                if not self.dry_run:
                    print(f"Using existing folder: '{main_folder_name}'")
                    main_folder = self.db.get_playlist(Name=main_folder_name).first()
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

            return main_folder

        except Exception as e:
            print(f"Error creating main stems folder: {e}")
            return None

    def create_category_structure(self, category_name: str, main_folder):
        """Create '<Category>' under 'ALLDJ Stems', with 'Vocals' and 'Instrumentals' subfolders.

        Returns a tuple: (category_folder, vocals_folder, instrumentals_folder) or (None, None, None) in dry-run.
        """
        try:
            if self.dry_run:
                print(f"  [DRY RUN] Would create category '{category_name}' with 'Vocals' and 'Instrumentals' under 'ALLDJ Stems'")
                return None, None, None

            # Create or find the category folder under main
            category_folder = self.find_child_folder(main_folder, category_name)
            if category_folder:
                print(f"  Using existing category folder: '{category_name}'")
            else:
                category_folder = self.db.create_playlist_folder(category_name, parent=main_folder)
                print(f"  ✓ Created category folder: '{category_name}'")

            # Under category, create Vocals and Instrumentals
            vocals_folder = self.create_stem_type_folder('vocals', category_folder)
            instrumentals_folder = self.create_stem_type_folder('instrumentals', category_folder)

            return category_folder, vocals_folder, instrumentals_folder

        except Exception as e:
            print(f"  Error creating category structure for '{category_name}': {e}")
            return None, None, None
    
    def create_category_folder(self, category_name: str, parent_folder):
        """Create a category folder under the specified parent (Vocals/Instrumentals)."""
        try:
            folder_name = category_name
            if self.dry_run:
                print(f"  [DRY RUN] Would create or use category folder: '{folder_name}' under '{getattr(parent_folder, 'Name', 'Root')}'")
                return None

            # Find existing child under this parent only
            existing = self.find_child_folder(parent_folder, folder_name)
            if existing:
                print(f"  Using existing category folder: '{folder_name}' under '{getattr(parent_folder, 'Name', 'Root')}'")
                return existing

            folder = self.db.create_playlist_folder(folder_name, parent=parent_folder)
            print(f"  ✓ Created category folder: '{folder_name}' under '{getattr(parent_folder, 'Name', 'Root')}'")
            return folder

        except Exception as e:
            print(f"  Error creating category folder '{category_name}': {e}")
            return None
    
    def create_stem_type_folder(self, stem_type: str, parent_folder):
        """Create vocals or instrumentals folder under a category folder."""
        try:
            folder_name = stem_type.capitalize()

            # Helper: find a child folder with given name under parent
            def find_child_folder(name: str):
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

            if self.dry_run:
                print(f"    [DRY RUN] Would create {stem_type} folder: '{folder_name}' under '{getattr(parent_folder, 'Name', 'Category')}'")
                return None

            # Try to find existing child under this parent
            existing_child = find_child_folder(folder_name)
            if existing_child:
                print(f"    Using existing {stem_type} folder: '{folder_name}'")
                return existing_child

            # Create new folder under parent
            folder = self.db.create_playlist_folder(folder_name, parent=parent_folder)
            print(f"    ✓ Created {stem_type} folder: '{folder_name}'")
            return folder
                    
        except Exception as e:
            print(f"    Error creating {stem_type} folder: {e}")
            return None
    
    def create_stems_playlist_for_tag(self, tag: str, category_folder, vocals_folder, instrumentals_folder):
        """Create vocals and instrumentals playlists for a specific tag."""
        tracks_with_tag = self.find_tracks_with_tag(tag)
        
        if not tracks_with_tag:
            print(f"      No tracks found with tag '{tag}', skipping")
            return False
        
        print(f"      Processing tag '{tag}' ({len(tracks_with_tag)} tracks)")
        
        # Create playlists for vocals and instrumentals
        vocals_playlist_name = f"{tag} Vocals"
        instrumentals_playlist_name = f"{tag} Instrumentals"
        
        vocals_created = self.create_stem_playlist(vocals_playlist_name, tracks_with_tag, 'vocals', vocals_folder)
        instrumentals_created = self.create_stem_playlist(instrumentals_playlist_name, tracks_with_tag, 'instrumentals', instrumentals_folder)
        
        return vocals_created or instrumentals_created
    
    def create_stem_playlist(self, playlist_name: str, tracks: List[dict], stem_type: str, parent_folder):
        """Create a playlist for a specific stem type."""
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
            stem_files_found = 0
            stem_files_missing = 0
            for track in tracks:
                stems = self.find_stem_files(
                    track.get('filename', ''),
                    track.get('title') or track.get('Title') or ''
                )
                key = stem_type if stem_type != 'instrumentals' else 'instrumental'
                if stems.get(key):
                    stem_files_found += 1
                else:
                    stem_files_missing += 1
                    # record diagnostic
                    self.missing_stems.append({
                        'playlist': playlist_name,
                        'stem_type': key,
                        'title': track.get('title') or track.get('Title'),
                        'filename': track.get('filename'),
                    })
            print(f"        [DRY RUN] Would create playlist '{playlist_name}' with {stem_files_found} stems (missing on disk: {stem_files_missing})")
            return True
        
        try:
            # Create the playlist
            playlist = self.db.create_playlist(playlist_name, parent=parent_folder)
            
            # Add stem files to the playlist
            added_count = 0
            missing_on_disk = 0
            import_failed = 0
            
            for track in tracks:
                stems = self.find_stem_files(
                    track.get('filename', ''),
                    track.get('title') or track.get('Title') or ''
                )
                key = stem_type if stem_type != 'instrumentals' else 'instrumental'
                stem_file = stems.get(key)

                if stem_file:
                    # Try to add/import stem file to Rekordbox
                    rekordbox_track = self.add_stem_to_rekordbox(stem_file)
                    if rekordbox_track:
                        try:
                            self.db.add_to_playlist(playlist, rekordbox_track)
                            added_count += 1
                        except Exception as e:
                            print(f"          Warning: Could not add stem to playlist: {stem_file.name}: {e}")
                            self.import_failures.append({
                                'playlist': playlist_name,
                                'stem_type': key,
                                'path': str(stem_file),
                                'error': str(e),
                            })
                            import_failed += 1
                    else:
                        self.import_failures.append({
                            'playlist': playlist_name,
                            'stem_type': key,
                            'path': str(stem_file),
                            'error': 'Import returned None',
                        })
                        import_failed += 1
                else:
                    self.missing_stems.append({
                        'playlist': playlist_name,
                        'stem_type': key,
                        'title': track.get('title') or track.get('Title'),
                        'filename': track.get('filename'),
                    })
                    missing_on_disk += 1
            
            if added_count > 0:
                print(f"        ✓ Created playlist '{playlist_name}' with {added_count} stems")
            else:
                print(f"        ⚠️  Created empty playlist '{playlist_name}' - no stems found")

            if missing_on_disk > 0 or import_failed > 0:
                details = []
                if missing_on_disk:
                    details.append(f"missing on disk: {missing_on_disk}")
                if import_failed:
                    details.append(f"import failures: {import_failed}")
                print(f"          ({', '.join(details)})")
            
            return True
            
        except Exception as e:
            print(f"        ✗ Failed to create playlist '{playlist_name}': {e}")
            return False
    
    def write_reports(self, output_dir: Path | None = None):
        """Write CSV reports for missing stems and import failures."""
        try:
            import csv
            out_dir = output_dir or Path('.')
            if self.missing_stems:
                with open(out_dir / 'stems_missing_report.csv', 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['playlist','stem_type','title','filename'])
                    writer.writeheader()
                    for row in self.missing_stems:
                        writer.writerow(row)
            if self.import_failures:
                with open(out_dir / 'stems_import_failures.csv', 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['playlist','stem_type','path','error'])
                    writer.writeheader()
                    for row in self.import_failures:
                        writer.writerow(row)
        except Exception as e:
            print(f"Warning: Could not write reports: {e}")

    def run(self, report_only: bool = False):
        """Main execution function."""
        print("🎵 Stems Playlist Creator for Rekordbox")
        print("======================================")
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
        
        # Check stems directory
        if not self.stems_dir.exists():
            print(f"Error: Stems directory '{self.stems_dir}' not found")
            sys.exit(1)
        
        print(f"Stems directory: {self.stems_dir}")

        # Build stems index before heavy processing
        self.build_stems_index()
        
        # Create backup unless report-only
        if not self.dry_run and not report_only:
            self.backup_database()
        
        # Connect to database
        self.connect_to_database()
        
        # Load metadata
        metadata = self.load_metadata()
        
        # Use curated baked tags
        print("Collecting baked tags from M3U8 files...")
        baked_tags = self.find_baked_tags()
        if not baked_tags:
            print("Error: No baked tags found. Ensure 'baked_playlists_m3u8/' has M3U8 files.")
            sys.exit(1)
        print(f"Found {len(baked_tags)} baked tags")
        
        # Group tags by category
        categories = self.get_tag_categories()
        tag_to_category = {}
        for category, tags in categories.items():
            for tag in tags:
                if tag in baked_tags:
                    tag_to_category[tag] = category
        
        # Group tags by category
        category_tags = {}
        for tag in baked_tags:
            category = tag_to_category.get(tag, "Other Tags")
            if category not in category_tags:
                category_tags[category] = []
            category_tags[category].append(tag)
        
        print(f"Tags organized into {len(category_tags)} categories")
        
        # Create main folder structure (unless report-only)
        if not report_only:
            print(f"\nCreating stems folder structure...")
            main_folder = self.create_stems_structure()
        else:
            main_folder = None

        # Create category folders and playlists
        total_playlists_created = 0
        
        for category, tags in category_tags.items():
            if not tags:
                continue
                
            print(f"\nProcessing category: '{category}' ({len(tags)} tags)")
            
            # Create category folder under main, then Vocals/Instrumentals inside it
            if self.dry_run or report_only:
                category_folder, vocals_folder, instrumentals_folder = None, None, None
                if self.dry_run:
                    print(f"  [DRY RUN] Would create category '{category}' with 'Vocals' and 'Instrumentals' subfolders")
            else:
                category_folder, vocals_folder, instrumentals_folder = self.create_category_structure(category, main_folder)
            
            # Create playlists for each tag
            category_playlists_created = 0
            for tag in sorted(tags):
                created = self.create_stems_playlist_for_tag(tag, category_folder, vocals_folder, instrumentals_folder)
                if created:
                    category_playlists_created += 2  # vocals + instrumentals
            
            total_playlists_created += category_playlists_created
            print(f"  ✓ Created {category_playlists_created} playlists in '{category}'")
        
        # Commit changes
        if not self.dry_run and not report_only and total_playlists_created > 0:
            print(f"\nCommitting changes to database...")
            try:
                self.db.commit()
                print("✓ Changes committed successfully")
            except Exception as e:
                print(f"✗ Error committing changes: {e}")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Total categories: {len(category_tags)}")
        print(f"   Total tags processed: {len(baked_tags)}")
        print(f"   Total playlists created: {total_playlists_created}")
        
        # Write reports
        self.write_reports(Path('.'))

        if self.dry_run:
            print("\n💡 Run without --dry-run to create the stems playlists")
            print(f"💡 Make sure to import your stem files from '{self.stems_dir}' into Rekordbox first")
        elif not report_only and total_playlists_created > 0:
            print(f"\n✅ Stems playlist creation complete!")
            print(f"   Open Rekordbox to see your new stems playlist structure")
            print(f"   Note: You may need to manually import stem files that weren't found")
        
        # Close database connection
        if self.db:
            self.db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create stems playlists in Rekordbox mirroring ALLDJ structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_stems_playlists.py --dry-run
  python create_stems_playlists.py --stems-dir "/Volumes/T7 Shield/3000AD/alldj_stem_separated"
  python create_stems_playlists.py --no-backup --stems-dir "/path/to/stems"
        """
    )
    
    parser.add_argument(
        "--metadata",
        default="music_collection_metadata.json",
        help="Path to metadata JSON file (default: music_collection_metadata.json)"
    )
    
    parser.add_argument(
        "--stems-dir",
        default="/Volumes/T7 Shield/3000AD/alldj_stem_separated",
        help="Path to directory containing stem files"
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
        "--report-only",
        action="store_true",
        help="Only analyze and generate missing/import-failure reports; don't modify playlists"
    )
    
    args = parser.parse_args()
    
    # Check if metadata file exists
    if not os.path.exists(args.metadata):
        print(f"Error: Metadata file '{args.metadata}' not found.")
        sys.exit(1)
    
    # Check if stems directory exists
    stems_path = Path(args.stems_dir)
    if not stems_path.exists():
        print(f"Error: Stems directory '{stems_path}' not found.")
        print("\nMake sure the stems directory path is correct.")
        sys.exit(1)
    
    # Create and run the stems playlist creator
    creator = StemsPlaylistCreator(
        metadata_file=args.metadata,
        stems_dir=str(stems_path),
        dry_run=args.dry_run,
        backup=not args.no_backup
    )
    
    try:
        creator.run(report_only=args.report_only)
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