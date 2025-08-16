#!/usr/bin/env python3

"""
Comprehensive Rekordbox Playlist to USB Copier
Handles deeply nested playlists, non-uniform structures, and files scattered across computer.
Designed for Rekordbox 7 with full edge case handling.

Usage:
  python copy_rekordbox_playlists_to_usb.py --test  # Test on 5 playlists first
  python copy_rekordbox_playlists_to_usb.py --full  # Copy all playlists
  python copy_rekordbox_playlists_to_usb.py --resume  # Resume interrupted copy
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import unquote, urlparse

try:
    from pyrekordbox import Rekordbox6Database, db6
except ImportError:
    print("❌ Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    sys.exit(1)


# ========================= DATA STRUCTURES =========================

@dataclass
class PlaylistInfo:
    id: str
    name: str
    parent_id: Optional[str]
    full_path: str
    track_count: int
    is_smart: bool = False
    is_folder: bool = False

@dataclass
class TrackInfo:
    title: str
    artist: str
    original_path: Path
    relative_path: str
    file_size: int
    exists: bool

@dataclass
class CopyStats:
    playlists_total: int = 0
    playlists_completed: int = 0
    playlists_skipped: int = 0
    playlists_failed: int = 0
    tracks_total: int = 0
    tracks_copied: int = 0
    tracks_skipped: int = 0
    tracks_failed: int = 0
    bytes_copied: int = 0


# ========================= UTILITY FUNCTIONS =========================

def atomic_write_text(dest: Path, content: str) -> None:
    """Atomically write text to file to prevent corruption."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(dest.parent), encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)

def atomic_copy_file(src: Path, dest: Path) -> bool:
    """Atomically copy file to prevent corruption. Returns True if copied, False if skipped."""
    if not src.exists():
        return False
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Skip if destination exists and has same size
    if dest.exists() and src.stat().st_size == dest.stat().st_size:
        return False
    
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(dest.parent)) as tmp:
        with src.open("rb") as fsrc:
            shutil.copyfileobj(fsrc, tmp)
        tmp_path = Path(tmp.name)
    
    tmp_path.replace(dest)
    return True

def normalize_rekordbox_path(folder: str, filename: str) -> Optional[Path]:
    """
    Convert Rekordbox paths to absolute paths, handling all edge cases:
    - file:// URLs
    - Percent-encoding (%20, etc.)
    - Windows-style paths on macOS
    - Relative paths
    - Unicode characters
    """
    folder = (folder or "").strip()
    filename = (filename or "").strip()
    
    if not filename:
        return None
    
    try:
        # Decode URL-encodings in filename
        filename = unquote(filename)
        
        # Handle file:// URL in folder
        if folder.startswith("file://"):
            parsed = urlparse(folder)
            path_str = parsed.path or folder[len("file://"):]
            folder_path = unquote(path_str)
        else:
            folder_path = unquote(folder) if folder else ""
        
        # Construct full path
        if folder_path:
            # Ensure proper path separator
            if folder_path and not folder_path.endswith("/"):
                folder_path += "/"
            
            # Handle various Rekordbox path construction issues
            if folder_path.endswith("/" + filename):
                # Folder already includes filename at end
                full_path = folder_path.rstrip("/")
            elif folder_path.endswith(filename + "/" + filename):
                # Double filename bug: "path/file.mp3/file.mp3" -> "path/file.mp3"
                full_path = folder_path.replace("/" + filename, "").rstrip("/")
            elif "/" + filename + "/" in folder_path:
                # Filename appears in middle of path, extract up to that point
                parts = folder_path.split("/" + filename + "/")
                full_path = parts[0] + "/" + filename
            else:
                # Normal construction
                full_path = folder_path + filename
        else:
            # If no folder path, filename might be absolute
            full_path = filename
        
        # Convert to Path and resolve
        path = Path(full_path)
        
        # Handle Windows-style paths on macOS
        if not path.exists() and "\\" in full_path:
            full_path = full_path.replace("\\", "/")
            path = Path(full_path)
        
        return path.resolve() if path.exists() else path
        
    except Exception as e:
        print(f"Warning: Could not normalize path '{folder}' + '{filename}': {e}")
        return None

def safe_filename(name: str) -> str:
    """Convert playlist/folder name to safe filename."""
    # Replace problematic characters
    safe = name.replace("/", "_").replace("\\", "_").replace(":", "-")
    safe = safe.replace("<", "(").replace(">", ")").replace("|", "-")
    safe = safe.replace("?", "").replace("*", "").replace('"', "'")
    
    # Limit length and strip whitespace
    return safe.strip()[:100]

def calculate_relative_path(source_path: Path, base_paths: List[Path]) -> str:
    """
    Calculate the most appropriate relative path for organizing files on USB.
    Tries to find the best base path that contains the source.
    """
    source_resolved = source_path.resolve()
    
    # Try each base path to find the best match
    for base in base_paths:
        try:
            base_resolved = base.resolve()
            if source_resolved.is_relative_to(base_resolved):
                rel_path = source_resolved.relative_to(base_resolved)
                return str(rel_path)
        except (ValueError, OSError):
            continue
    
    # If no base path contains the file, use a flattened structure
    # Group by drive/volume for organization
    parts = source_resolved.parts
    if len(parts) > 1:
        # Use volume name + filename
        volume = parts[0] if parts[0].startswith('/') else parts[1]
        volume_safe = safe_filename(volume.replace('/', ''))
        return f"{volume_safe}/{source_resolved.name}"
    else:
        return source_resolved.name


# ========================= MAIN COPIER CLASS =========================

class RekordboxPlaylistCopier:
    def __init__(self, usb_path: str, test_mode: bool = False, resume: bool = True):
        self.usb_root = Path(usb_path).resolve()
        self.music_root = self.usb_root / "ALLDJ_MUSIC"
        self.playlists_root = self.usb_root / "PLAYLISTS"
        self.state_file = self.usb_root / ".rekordbox_copy_state.json"
        self.log_file = self.usb_root / "copy_log.txt"
        
        self.test_mode = test_mode
        self.resume = resume
        self.db: Optional[Rekordbox6Database] = None
        
        # State and progress tracking
        self.state: Dict = {"version": 1, "playlists": {}, "stats": {}}
        self.stats = CopyStats()
        self.start_time = time.time()
        
        # Base paths for organizing files (in order of preference)
        self.base_paths = [
            Path("/Users/ethansarif-kattan/Music/ALLDJ"),
            Path("/Users/ethansarif-kattan/Music"),
            Path("/Volumes/T7"),
            Path("/Volumes/T7 Shield"),
            Path.home() / "Music",
            Path.home() / "Desktop",
            Path("/Users/ethansarif-kattan"),
        ]
        
        # Smart playlist detection
        self.smart_playlist_ids: Set[str] = set()
    
    def log(self, message: str, level: str = "INFO"):
        """Log message to both console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {level}: {message}"
        print(log_msg)
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
        except Exception:
            pass  # Don't fail if logging fails
    
    def load_state(self):
        """Load previous state if resuming."""
        if self.resume and self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
                stored_stats = self.state.get("stats", {})
                for key, value in stored_stats.items():
                    if hasattr(self.stats, key):
                        setattr(self.stats, key, value)
                self.log("Loaded previous state for resuming")
            except Exception as e:
                self.log(f"Warning: Could not load state file: {e}", "WARN")
    
    def save_state(self):
        """Save current state."""
        if not self.resume:
            return
        
        self.state["stats"] = asdict(self.stats)
        self.state["timestamp"] = datetime.now().isoformat()
        
        try:
            atomic_write_text(self.state_file, json.dumps(self.state, indent=2))
        except Exception as e:
            self.log(f"Warning: Could not save state: {e}", "WARN")
    
    def connect_to_database(self):
        """Connect to Rekordbox database with comprehensive path detection."""
        self.log("Connecting to Rekordbox database...")
        
        # Try multiple database locations (7 first, then 6, then legacy)
        db_paths = [
            Path.home() / "Library/Pioneer/rekordbox7",
            Path.home() / "Library/Pioneer/rekordbox6",
            Path.home() / "Library/Pioneer/rekordbox",
        ]
        
        db_path = None
        for path in db_paths:
            if path.exists():
                db_path = path
                break
        
        if db_path is None:
            self.log("No Rekordbox database directory found", "ERROR")
            self.log("Checked: " + ", ".join(str(p) for p in db_paths), "ERROR")
            raise Exception("No Rekordbox database found")
        
        self.log(f"Found Rekordbox database at: {db_path}")
        
        try:
            self.db = Rekordbox6Database(db_dir=str(db_path))
            self.log("✓ Connected successfully")
        except Exception as e:
            self.log(f"Failed to connect to database: {e}", "ERROR")
            self.log("Make sure Rekordbox is completely closed", "ERROR")
            if "key" in str(e).lower():
                self.log("Try running: python -m pyrekordbox download-key", "ERROR")
            raise
    
    def detect_smart_playlists(self):
        """Detect smart playlists to exclude them."""
        try:
            Smart = db6.tables.DjmdSmartList
            smart_rows = self.db.session.query(Smart).all()
            self.smart_playlist_ids = {str(r.PlaylistID) for r in smart_rows}
            self.log(f"Detected {len(self.smart_playlist_ids)} smart playlists")
        except Exception as e:
            self.log(f"Warning: Could not detect smart playlists: {e}", "WARN")
            self.smart_playlist_ids = set()
    
    def get_all_playlists(self) -> List[PlaylistInfo]:
        """Get all playlists with comprehensive metadata."""
        self.log("Scanning all playlists...")
        
        playlists = []
        all_nodes = self.db.get_playlist().all()
        
        # Build parent-child relationships
        id_to_node = {str(node.ID): node for node in all_nodes}
        
        for node in all_nodes:
            node_id = str(node.ID)
            
            # Skip smart playlists
            if node_id in self.smart_playlist_ids:
                continue
            
            # Build full path
            path_parts = []
            current_id = node_id
            visited = set()
            
            while current_id and current_id != "root" and current_id not in visited:
                visited.add(current_id)
                if current_id in id_to_node:
                    current_node = id_to_node[current_id]
                    path_parts.append(current_node.Name)
                    parent_id = getattr(current_node, 'ParentID', None)
                    current_id = str(parent_id) if parent_id else None
                else:
                    break
            
            path_parts.reverse()
            full_path = " / ".join(path_parts) if path_parts else node.Name
            
            # Check if this is a folder (has children) or actual playlist
            try:
                track_count = len(self.get_playlist_tracks(node_id))
                is_folder = track_count == 0
            except Exception:
                # If we can't get tracks, assume it's a folder
                is_folder = True
                track_count = 0
            
            playlist_info = PlaylistInfo(
                id=node_id,
                name=node.Name,
                parent_id=str(getattr(node, 'ParentID', None)),
                full_path=full_path,
                track_count=track_count,
                is_smart=False,  # Already filtered out
                is_folder=is_folder
            )
            
            playlists.append(playlist_info)
        
        # Filter out folders (no tracks)
        actual_playlists = [p for p in playlists if not p.is_folder and p.track_count > 0]
        
        self.log(f"Found {len(actual_playlists)} actual playlists (out of {len(playlists)} total nodes)")
        return actual_playlists
    
    def get_playlist_tracks(self, playlist_id: str) -> List[TrackInfo]:
        """Get all tracks in a playlist with full metadata."""
        tracks = []
        
        try:
            SP = db6.tables.DjmdSongPlaylist  
            CT = db6.tables.DjmdContent
            
            rows = (
                self.db.session.query(SP, CT)
                .join(CT, CT.ID == SP.ContentID)
                .filter(SP.PlaylistID == int(playlist_id))
                .order_by(SP.TrackNo)
                .all()
            )
            
            for sp, ct in rows:
                title = (ct.Title or "Unknown").strip()
                # Handle artist field which might be an object
                try:
                    if hasattr(ct.Artist, 'Name'):
                        artist = (ct.Artist.Name or "Unknown").strip()
                    else:
                        artist = (str(ct.Artist) if ct.Artist else "Unknown").strip()
                except Exception:
                    artist = "Unknown"
                
                # Get file path using our robust path normalizer
                filename = (ct.FileNameL or ct.FileNameS or "").strip()
                folder = (ct.FolderPath or "").strip()
                
                original_path = normalize_rekordbox_path(folder, filename)
                if not original_path:
                    continue
                
                # Calculate relative path for USB organization
                rel_path = calculate_relative_path(original_path, self.base_paths)
                
                # Get file size and existence
                file_size = 0
                exists = False
                if original_path.exists():
                    try:
                        file_size = original_path.stat().st_size
                        exists = True
                    except OSError:
                        pass
                
                track_info = TrackInfo(
                    title=title,
                    artist=artist,
                    original_path=original_path,
                    relative_path=rel_path,
                    file_size=file_size,
                    exists=exists
                )
                
                tracks.append(track_info)
                
        except Exception as e:
            self.log(f"Error getting tracks for playlist {playlist_id}: {e}", "ERROR")
        
        return tracks
    
    def copy_playlist(self, playlist: PlaylistInfo) -> bool:
        """Copy a single playlist and all its tracks."""
        self.log(f"Processing playlist: {playlist.full_path} ({playlist.track_count} tracks)")
        
        # Check if already completed
        playlist_state = self.state.get("playlists", {}).get(playlist.id, {})
        if playlist_state.get("completed"):
            self.log("Already completed, skipping")
            self.stats.playlists_skipped += 1
            return True
        
        # Get tracks
        tracks = self.get_playlist_tracks(playlist.id)
        if not tracks:
            self.log("No tracks found, skipping", "WARN")
            self.stats.playlists_skipped += 1
            return False
        
        # Create playlist directory structure
        safe_path = Path(*[safe_filename(part) for part in playlist.full_path.split(" / ")])
        playlist_dir = self.playlists_root / safe_path.parent if safe_path.parent != Path('.') else self.playlists_root
        playlist_file = playlist_dir / f"{safe_filename(playlist.name)}.m3u8"
        
        # Copy tracks
        copied_tracks = []
        tracks_copied_count = 0
        tracks_failed_count = 0
        
        for track in tracks:
            self.stats.tracks_total += 1
            
            if not track.exists:
                self.log(f"Missing file: {track.original_path}", "WARN")
                self.stats.tracks_failed += 1
                tracks_failed_count += 1
                continue
            
            # Destination path
            dest_path = self.music_root / track.relative_path
            
            try:
                # Copy file atomically
                was_copied = atomic_copy_file(track.original_path, dest_path)
                
                if was_copied:
                    self.log(f"Copied: {track.title}")
                    self.stats.tracks_copied += 1
                    self.stats.bytes_copied += track.file_size
                    tracks_copied_count += 1
                else:
                    self.log(f"Exists: {track.title}")
                    self.stats.tracks_skipped += 1
                
                copied_tracks.append((track, dest_path))
                
            except Exception as e:
                self.log(f"Failed to copy {track.title}: {e}", "ERROR")
                self.stats.tracks_failed += 1
                tracks_failed_count += 1
        
        # Create M3U8 playlist file
        if copied_tracks:
            try:
                self.create_m3u8_playlist(playlist, copied_tracks, playlist_file)
                self.log(f"Created playlist: {playlist_file.name}")
            except Exception as e:
                self.log(f"Failed to create playlist file: {e}", "ERROR")
                return False
        
        # Update state
        self.state.setdefault("playlists", {})[playlist.id] = {
            "completed": True,
            "name": playlist.name,
            "tracks_total": len(tracks),
            "tracks_copied": tracks_copied_count,
            "tracks_failed": tracks_failed_count,
            "playlist_file": str(playlist_file)
        }
        
        self.stats.playlists_completed += 1
        self.save_state()
        
        return True
    
    def create_m3u8_playlist(self, playlist: PlaylistInfo, tracks: List[Tuple[TrackInfo, Path]], playlist_file: Path):
        """Create M3U8 playlist file with relative paths."""
        lines = [
            "#EXTM3U",
            f"# {playlist.name}",
            f"# Exported from Rekordbox on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Original path: {playlist.full_path}",
            ""
        ]
        
        for track, dest_path in tracks:
            # Calculate relative path from playlist to music file
            try:
                rel_path = os.path.relpath(dest_path, playlist_file.parent)
                lines.append(f"#EXTINF:-1,{track.artist} - {track.title}")
                lines.append(rel_path)
            except Exception as e:
                self.log(f"Warning: Could not create relative path for {track.title}: {e}", "WARN")
        
        content = "\n".join(lines) + "\n"
        atomic_write_text(playlist_file, content)
    
    def print_stats(self):
        """Print current statistics."""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("COPY STATISTICS")
        print("="*60)
        print(f"Time elapsed: {elapsed:.1f} seconds")
        print(f"Playlists: {self.stats.playlists_completed} completed, {self.stats.playlists_skipped} skipped, {self.stats.playlists_failed} failed")
        print(f"Tracks: {self.stats.tracks_copied} copied, {self.stats.tracks_skipped} skipped, {self.stats.tracks_failed} failed")
        print(f"Data copied: {self.stats.bytes_copied / (1024**3):.2f} GB")
        print(f"Music location: {self.music_root}")
        print(f"Playlists location: {self.playlists_root}")
        print("="*60)
    
    def run(self):
        """Main execution method."""
        try:
            # Validate USB path
            if not self.usb_root.exists():
                raise Exception(f"USB path not found: {self.usb_root}")
            
            # Create directories
            self.music_root.mkdir(parents=True, exist_ok=True)
            self.playlists_root.mkdir(parents=True, exist_ok=True)
            
            # Load state and connect
            self.load_state()
            self.connect_to_database()
            self.detect_smart_playlists()
            
            # Get playlists
            playlists = self.get_all_playlists()
            self.stats.playlists_total = len(playlists)
            
            if self.test_mode:
                playlists = playlists[:5]  # Test with first 5 playlists
                self.log(f"TEST MODE: Processing first {len(playlists)} playlists")
            
            self.log(f"Processing {len(playlists)} playlists...")
            
            # Process each playlist
            for i, playlist in enumerate(playlists, 1):
                self.log(f"[{i}/{len(playlists)}] Starting: {playlist.name}")
                
                try:
                    success = self.copy_playlist(playlist)
                    if not success:
                        self.stats.playlists_failed += 1
                except Exception as e:
                    self.log(f"Failed to process playlist {playlist.name}: {e}", "ERROR")
                    self.stats.playlists_failed += 1
                
                # Print progress every 10 playlists
                if i % 10 == 0:
                    self.print_stats()
            
            # Final statistics
            self.print_stats()
            self.log("✅ Copy operation completed!")
            
        except Exception as e:
            self.log(f"Fatal error: {e}", "ERROR")
            raise
        finally:
            if self.db:
                self.db.close()


# ========================= MAIN EXECUTION =========================

def main():
    parser = argparse.ArgumentParser(
        description="Copy Rekordbox playlists to USB with comprehensive edge case handling"
    )
    parser.add_argument(
        "--usb-path", 
        default="/Volumes/DJYING",
        help="USB drive path (default: /Volumes/DJYING)"
    )
    parser.add_argument(
        "--test", 
        action="store_true",
        help="Test mode: only process first 5 playlists"
    )
    parser.add_argument(
        "--full", 
        action="store_true", 
        help="Full mode: process all playlists"
    )
    parser.add_argument(
        "--resume", 
        action="store_true",
        default=True,
        help="Resume from previous state (default: True)"
    )
    parser.add_argument(
        "--no-resume", 
        action="store_true",
        help="Start fresh (ignore previous state)"
    )
    
    args = parser.parse_args()
    
    if not args.test and not args.full:
        print("Please specify either --test or --full mode")
        sys.exit(1)
    
    resume = args.resume and not args.no_resume
    
    print("🎚️  Rekordbox Playlist → USB Copier")
    print("="*50)
    print(f"USB Path: {args.usb_path}")
    print(f"Mode: {'TEST (5 playlists)' if args.test else 'FULL (all playlists)'}")
    print(f"Resume: {'Yes' if resume else 'No'}")
    print("="*50)
    
    copier = RekordboxPlaylistCopier(
        usb_path=args.usb_path,
        test_mode=args.test,
        resume=resume
    )
    
    try:
        copier.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Progress saved. Re-run to continue.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
