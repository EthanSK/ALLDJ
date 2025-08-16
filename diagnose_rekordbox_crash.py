#!/usr/bin/env python3

"""
Rekordbox Crash Diagnostic Tool

This script systematically tests playlist exports to identify the exact track
causing Rekordbox to crash during USB export. It uses a binary search approach
to efficiently isolate the problematic track.

Usage:
  python diagnose_rekordbox_crash.py --playlist "Your Playlist Name"
  python diagnose_rekordbox_crash.py --playlist-id 12345
  python diagnose_rekordbox_crash.py --auto-detect
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

try:
    from pyrekordbox import Rekordbox6Database, db6
except ImportError:
    print("❌ Error: pyrekordbox library is required. Install it with:")
    print("pip install pyrekordbox")
    sys.exit(1)


class RekordboxCrashDiagnostic:
    def __init__(self, test_usb_path: str = "/tmp/rekordbox_test"):
        self.test_root = Path(test_usb_path)
        self.test_music = self.test_root / "ALLDJ_MUSIC"
        self.test_playlists = self.test_root / "PLAYLISTS"
        self.log_file = self.test_root / "crash_diagnostic.log"
        self.results_file = self.test_root / "diagnostic_results.json"
        
        self.db: Optional[Rekordbox6Database] = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "problematic_tracks": [],
            "safe_tracks": [],
            "summary": {}
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Log message to both console and file."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {level}: {message}"
        print(log_msg)
        
        self.test_root.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
        except Exception:
            pass
    
    def connect_to_database(self):
        """Connect to Rekordbox database."""
        self.log("Connecting to Rekordbox database...")
        
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
            raise Exception("No Rekordbox database found")
        
        self.log(f"Found database at: {db_path}")
        
        try:
            self.db = Rekordbox6Database(db_dir=str(db_path))
            self.log("✓ Connected successfully")
        except Exception as e:
            self.log(f"Failed to connect: {e}", "ERROR")
            self.log("Make sure Rekordbox is completely closed", "ERROR")
            raise
    
    def normalize_rekordbox_path(self, folder: str, filename: str) -> Optional[Path]:
        """Convert Rekordbox paths to absolute paths."""
        folder = (folder or "").strip()
        filename = (filename or "").strip()
        
        if not filename:
            return None
        
        try:
            filename = unquote(filename)
            
            if folder.startswith("file://"):
                parsed = urlparse(folder)
                path_str = parsed.path or folder[len("file://"):]
                folder_path = unquote(path_str)
            else:
                folder_path = unquote(folder) if folder else ""
            
            if folder_path:
                if not folder_path.endswith("/"):
                    folder_path += "/"
                
                if folder_path.endswith("/" + filename):
                    full_path = folder_path.rstrip("/")
                else:
                    full_path = folder_path + filename
            else:
                full_path = filename
            
            path = Path(full_path)
            return path.resolve() if path.exists() else path
            
        except Exception as e:
            self.log(f"Warning: Could not normalize path '{folder}' + '{filename}': {e}", "WARN")
            return None
    
    def find_playlist_by_name(self, name: str) -> Optional[str]:
        """Find playlist ID by name."""
        playlists = self.db.get_playlist().all()
        for playlist in playlists:
            if playlist.Name.lower() == name.lower():
                return str(playlist.ID)
        return None
    
    def get_all_playlists(self) -> List[Tuple[str, str]]:
        """Get all playlist IDs and names."""
        playlists = []
        all_nodes = self.db.get_playlist().all()
        
        # Detect smart playlists
        smart_playlist_ids = set()
        try:
            Smart = db6.tables.DjmdSmartList
            smart_rows = self.db.session.query(Smart).all()
            smart_playlist_ids = {str(r.PlaylistID) for r in smart_rows}
        except Exception:
            pass
        
        for node in all_nodes:
            node_id = str(node.ID)
            
            # Skip smart playlists
            if node_id in smart_playlist_ids:
                continue
            
            # Check if it has tracks (not just a folder)
            try:
                track_count = len(self.get_playlist_tracks(node_id))
                if track_count > 0:
                    playlists.append((node_id, node.Name))
            except Exception:
                continue
        
        return playlists
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Get all tracks in a playlist with metadata."""
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
                
                # Handle artist field
                try:
                    if hasattr(ct.Artist, 'Name'):
                        artist = (ct.Artist.Name or "Unknown").strip()
                    else:
                        artist = (str(ct.Artist) if ct.Artist else "Unknown").strip()
                except Exception:
                    artist = "Unknown"
                
                # Get file path
                filename = (ct.FileNameL or ct.FileNameS or "").strip()
                folder = (ct.FolderPath or "").strip()
                
                original_path = self.normalize_rekordbox_path(folder, filename)
                if not original_path:
                    continue
                
                track_info = {
                    "track_no": sp.TrackNo,
                    "content_id": str(ct.ID),
                    "title": title,
                    "artist": artist,
                    "filename": filename,
                    "folder": folder,
                    "original_path": str(original_path),
                    "exists": original_path.exists() if original_path else False,
                    "file_size": original_path.stat().st_size if original_path and original_path.exists() else 0
                }
                
                tracks.append(track_info)
                
        except Exception as e:
            self.log(f"Error getting tracks for playlist {playlist_id}: {e}", "ERROR")
        
        return tracks
    
    def create_test_playlist(self, tracks: List[Dict], test_name: str) -> Path:
        """Create a test M3U8 playlist with given tracks."""
        playlist_file = self.test_playlists / f"{test_name}.m3u8"
        playlist_file.parent.mkdir(parents=True, exist_ok=True)
        
        lines = [
            "#EXTM3U",
            f"# {test_name} - Crash Diagnostic Test",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        for track in tracks:
            if track["exists"]:
                lines.append(f"#EXTINF:-1,{track['artist']} - {track['title']}")
                lines.append(track["original_path"])
        
        content = "\n".join(lines) + "\n"
        
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        return playlist_file
    
    def test_track_batch(self, tracks: List[Dict], batch_name: str) -> Dict:
        """Test a batch of tracks and return results."""
        self.log(f"Testing batch '{batch_name}' with {len(tracks)} tracks")
        
        # Create test playlist
        test_file = self.create_test_playlist(tracks, batch_name)
        
        test_result = {
            "batch_name": batch_name,
            "track_count": len(tracks),
            "tracks": [
                {
                    "track_no": t["track_no"],
                    "title": t["title"],
                    "artist": t["artist"],
                    "content_id": t["content_id"],
                    "exists": t["exists"]
                } for t in tracks
            ],
            "playlist_file": str(test_file),
            "status": "pending",
            "notes": []
        }
        
        self.log(f"Created test playlist: {test_file}")
        self.log("🛑 MANUAL TEST REQUIRED:")
        self.log("1. Import this playlist into Rekordbox:")
        self.log(f"   File → Import → Import Playlist → {test_file}")
        self.log("2. Try to export this playlist to your USB")
        self.log("3. Report the result:")
        
        while True:
            result = input("   Did Rekordbox crash? (y/n/skip): ").lower().strip()
            if result in ['y', 'yes']:
                test_result["status"] = "crashed"
                self.log("❌ Crash confirmed for this batch")
                break
            elif result in ['n', 'no']:
                test_result["status"] = "success"
                self.log("✅ This batch exported successfully")
                break
            elif result in ['s', 'skip']:
                test_result["status"] = "skipped"
                self.log("⏭️ Batch skipped")
                break
            else:
                print("Please enter 'y' for yes, 'n' for no, or 'skip' to skip this test")
        
        # Ask for additional notes
        notes = input("   Any additional notes? (optional): ").strip()
        if notes:
            test_result["notes"].append(notes)
        
        self.results["tests"].append(test_result)
        self.save_results()
        
        return test_result
    
    def binary_search_problematic_track(self, tracks: List[Dict]) -> Optional[Dict]:
        """Use binary search to find the exact problematic track."""
        self.log(f"🔍 Starting binary search on {len(tracks)} tracks")
        
        if len(tracks) <= 1:
            if tracks:
                return tracks[0]
            return None
        
        # Test first 5 tracks (following user preference)
        self.log("Testing first 5 tracks...")
        test_batch = tracks[:5]
        result = self.test_track_batch(test_batch, f"binary_first_5")
        
        if result["status"] == "crashed":
            self.log("Crash found in first 5 tracks, narrowing down...")
            return self.binary_search_problematic_track(test_batch)
        elif result["status"] == "success":
            self.log("First 5 tracks are safe, testing more...")
            # If successful, continue with all tracks using binary search
            return self.binary_search_full(tracks)
        else:  # skipped
            self.log("Test skipped, trying different approach...")
            return self.binary_search_full(tracks)
    
    def binary_search_full(self, tracks: List[Dict]) -> Optional[Dict]:
        """Full binary search implementation."""
        left, right = 0, len(tracks)
        problematic_track = None
        
        test_count = 0
        while left < right and test_count < 10:  # Limit iterations to prevent endless testing
            test_count += 1
            mid = (left + right) // 2
            
            if mid == left:  # We're down to single track
                break
            
            test_batch = tracks[left:mid]
            result = self.test_track_batch(test_batch, f"binary_search_{test_count}")
            
            if result["status"] == "crashed":
                # Problem is in left half
                right = mid
                self.log(f"Problem is in tracks {left}-{mid}")
            elif result["status"] == "success":
                # Problem is in right half
                left = mid
                self.log(f"Tracks {left}-{mid} are safe, checking {mid}-{right}")
            else:  # skipped
                self.log("Test was skipped, stopping binary search")
                break
        
        # Final check on remaining tracks
        if left < len(tracks):
            remaining = tracks[left:left+1] if left < len(tracks) else []
            if remaining:
                result = self.test_track_batch(remaining, f"final_suspect")
                if result["status"] == "crashed":
                    problematic_track = remaining[0]
        
        return problematic_track
    
    def diagnose_playlist(self, playlist_id: str, playlist_name: str):
        """Main diagnostic routine for a playlist."""
        self.log(f"🔬 Starting diagnostic for playlist: {playlist_name}")
        
        tracks = self.get_playlist_tracks(playlist_id)
        if not tracks:
            self.log("No tracks found in playlist", "ERROR")
            return
        
        self.log(f"Found {len(tracks)} tracks in playlist")
        
        # Filter to existing tracks only
        existing_tracks = [t for t in tracks if t["exists"]]
        missing_tracks = [t for t in tracks if not t["exists"]]
        
        if missing_tracks:
            self.log(f"Warning: {len(missing_tracks)} tracks are missing files")
        
        if not existing_tracks:
            self.log("No tracks with existing files found", "ERROR")
            return
        
        self.log(f"Testing {len(existing_tracks)} tracks with existing files")
        
        # Start binary search
        problematic_track = self.binary_search_problematic_track(existing_tracks)
        
        if problematic_track:
            self.log("🎯 FOUND PROBLEMATIC TRACK!")
            self.log(f"Track: {problematic_track['artist']} - {problematic_track['title']}")
            self.log(f"File: {problematic_track['original_path']}")
            self.log(f"Content ID: {problematic_track['content_id']}")
            self.log(f"Track Number: {problematic_track['track_no']}")
            
            self.results["problematic_tracks"].append(problematic_track)
        else:
            self.log("Could not isolate a specific problematic track")
        
        # Store all safe tracks
        for test in self.results["tests"]:
            if test["status"] == "success":
                self.results["safe_tracks"].extend(test["tracks"])
        
        # Generate summary
        self.results["summary"] = {
            "playlist_name": playlist_name,
            "playlist_id": playlist_id,
            "total_tracks": len(tracks),
            "existing_tracks": len(existing_tracks),
            "missing_tracks": len(missing_tracks),
            "tests_performed": len(self.results["tests"]),
            "problematic_tracks_found": len(self.results["problematic_tracks"])
        }
        
        self.save_results()
        self.print_final_report()
    
    def save_results(self):
        """Save diagnostic results to file."""
        try:
            with open(self.results_file, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2)
        except Exception as e:
            self.log(f"Warning: Could not save results: {e}", "WARN")
    
    def print_final_report(self):
        """Print final diagnostic report."""
        print("\n" + "="*60)
        print("🔬 REKORDBOX CRASH DIAGNOSTIC REPORT")
        print("="*60)
        
        summary = self.results["summary"]
        print(f"Playlist: {summary['playlist_name']}")
        print(f"Total tracks: {summary['total_tracks']}")
        print(f"Tracks with files: {summary['existing_tracks']}")
        print(f"Missing files: {summary['missing_tracks']}")
        print(f"Tests performed: {summary['tests_performed']}")
        
        if self.results["problematic_tracks"]:
            print(f"\n🎯 PROBLEMATIC TRACKS FOUND: {len(self.results['problematic_tracks'])}")
            for track in self.results["problematic_tracks"]:
                print(f"  • {track['artist']} - {track['title']}")
                print(f"    File: {track['original_path']}")
                print(f"    Content ID: {track['content_id']}")
                print(f"    Track #: {track['track_no']}")
        else:
            print("\n❓ No specific problematic tracks identified")
        
        print(f"\n📁 Full results saved to: {self.results_file}")
        print(f"📋 Diagnostic log: {self.log_file}")
        print("="*60)
    
    def auto_detect_large_playlists(self) -> List[Tuple[str, str, int]]:
        """Auto-detect playlists likely to cause export issues."""
        self.log("🔍 Auto-detecting playlists likely to cause issues...")
        
        all_playlists = self.get_all_playlists()
        large_playlists = []
        
        for playlist_id, name in all_playlists:
            tracks = self.get_playlist_tracks(playlist_id)
            track_count = len(tracks)
            
            # Consider playlists with many tracks or large file sizes
            if track_count > 50:  # Arbitrary threshold
                total_size = sum(t.get("file_size", 0) for t in tracks)
                large_playlists.append((playlist_id, name, track_count))
                self.log(f"Found large playlist: {name} ({track_count} tracks, {total_size/1024**3:.1f} GB)")
        
        # Sort by track count (descending)
        large_playlists.sort(key=lambda x: x[2], reverse=True)
        
        return large_playlists


def main():
    parser = argparse.ArgumentParser(description="Diagnose Rekordbox crash during playlist export")
    parser.add_argument("--playlist", help="Playlist name to diagnose")
    parser.add_argument("--playlist-id", help="Playlist ID to diagnose")
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect likely problematic playlists")
    parser.add_argument("--test-path", default="/tmp/rekordbox_test", help="Path for test files")
    
    args = parser.parse_args()
    
    if not any([args.playlist, args.playlist_id, args.auto_detect]):
        print("Please specify --playlist, --playlist-id, or --auto-detect")
        sys.exit(1)
    
    diagnostic = RekordboxCrashDiagnostic(args.test_path)
    
    try:
        diagnostic.connect_to_database()
        
        if args.auto_detect:
            large_playlists = diagnostic.auto_detect_large_playlists()
            if large_playlists:
                print("\n🎯 Large playlists that might cause issues:")
                for i, (pid, name, count) in enumerate(large_playlists[:10], 1):
                    print(f"{i:2d}. {name} ({count} tracks)")
                
                choice = input("\nEnter playlist number to diagnose (or 'q' to quit): ").strip()
                if choice.lower() == 'q':
                    return
                
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(large_playlists):
                        playlist_id, playlist_name, _ = large_playlists[idx]
                        diagnostic.diagnose_playlist(playlist_id, playlist_name)
                    else:
                        print("Invalid selection")
                except ValueError:
                    print("Invalid input")
            else:
                print("No large playlists found")
        
        elif args.playlist_id:
            # Get playlist name
            playlists = diagnostic.get_all_playlists()
            playlist_name = next((name for pid, name in playlists if pid == args.playlist_id), f"Playlist {args.playlist_id}")
            diagnostic.diagnose_playlist(args.playlist_id, playlist_name)
        
        elif args.playlist:
            playlist_id = diagnostic.find_playlist_by_name(args.playlist)
            if playlist_id:
                diagnostic.diagnose_playlist(playlist_id, args.playlist)
            else:
                print(f"Playlist '{args.playlist}' not found")
                
                # Show available playlists
                playlists = diagnostic.get_all_playlists()
                print("\nAvailable playlists:")
                for pid, name in playlists[:20]:  # Show first 20
                    print(f"  {name}")
                if len(playlists) > 20:
                    print(f"  ... and {len(playlists) - 20} more")
    
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if diagnostic.db:
            diagnostic.db.close()


if __name__ == "__main__":
    main()

