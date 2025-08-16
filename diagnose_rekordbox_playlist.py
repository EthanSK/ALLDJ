#!/usr/bin/env python3

"""
Diagnose a Rekordbox playlist for problematic tracks that could cause crashes
when exporting from Rekordbox. Uses pyrekordbox to enumerate a playlist's
tracks in order and performs a series of file/path integrity checks:

- Missing or non-existent source files
- Unresolvable/invalid FolderPath+FileName combinations (including file:// URLs)
- Non-UTF-8 encodings / surrogate characters in paths
- Extremely long paths
- Zero-byte or suspiciously small files
- Header sniffing for common containers (FLAC/MP3/WAV/AIFF/M4A)
- I/O errors when opening/reading first bytes

Usage examples:
  python diagnose_rekordbox_playlist.py --name "All Liked Stems" --first 5
  python diagnose_rekordbox_playlist.py --name "All Liked Stems"

If you're unsure of the exact name, omit --name to list playlists that contain
the word "stems".
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import unquote, urlparse

try:
    from pyrekordbox import Rekordbox6Database, db6
except ImportError:
    print("Error: pyrekordbox is required. Install with: pip install pyrekordbox")
    sys.exit(1)


# ------------------------ Helpers ------------------------

def normalize_rekordbox_path(folder: str, name: str) -> Path:
    folder = (folder or "").strip()
    name = (name or "").strip()

    # Decode URL-encodings
    name = unquote(name)

    if folder.startswith("file://"):
        parsed = urlparse(folder)
        path_str = parsed.path or folder[len("file://"):]
        folder_path = unquote(path_str)
    else:
        folder_path = unquote(folder)

    if folder_path and not folder_path.endswith("/"):
        folder_path += "/"

    # Guard against double join if FolderPath already includes filename
    if folder_path.endswith("/" + name):
        full = folder_path
    else:
        full = folder_path + name

    try:
        return Path(full).resolve()
    except Exception:
        return Path(full)


def safe_utf8(s: str) -> Tuple[bool, Optional[str]]:
    try:
        s.encode("utf-8", errors="strict")
        return True, None
    except UnicodeError as e:
        return False, str(e)


def sniff_header(first_bytes: bytes) -> str:
    if not first_bytes:
        return "empty"
    if first_bytes.startswith(b"fLaC"):
        return "FLAC"
    if first_bytes.startswith(b"ID3"):
        return "MP3 (ID3)"
    # WAV/AIFF RIFF forms
    if first_bytes[:4] == b"RIFF":
        # Could be WAV or AIFF-like
        return "RIFF (WAV/AIFF)"
    # MP4/M4A often has 'ftyp' within first 12 bytes
    if b"ftyp" in first_bytes[:12]:
        return "MP4/M4A (ftyp)"
    # OGG/Opus
    if first_bytes.startswith(b"OggS"):
        return "OGG/Opus"
    # AAC ADTS frame sync 0xFFF?
    if len(first_bytes) >= 2 and (first_bytes[0] == 0xFF and (first_bytes[1] & 0xF0) == 0xF0):
        return "AAC (ADTS)"
    return "Unknown"


# ------------------------ Diagnosis ------------------------

@dataclass
class TrackDiag:
    index: int
    title: str
    path: Path
    issues: List[str]
    header: Optional[str] = None
    size_bytes: Optional[int] = None


class PlaylistDiagnoser:
    def __init__(self) -> None:
        self.db: Optional[Rekordbox6Database] = None

    def connect(self) -> None:
        db_paths = [
            Path.home() / "Library/Pioneer/rekordbox7",
            Path.home() / "Library/Pioneer/rekordbox6",
            Path.home() / "Library/Pioneer/rekordbox",
        ]
        db_dir = next((p for p in db_paths if p.exists()), None)
        if db_dir is None:
            print("Error: Rekordbox database not found under ~/Library/Pioneer")
            sys.exit(1)
        self.db = Rekordbox6Database(db_dir=str(db_dir))

    def fetch_playlists(self) -> List[Tuple[int, str, Optional[int]]]:
        assert self.db is not None
        nodes = self.db.get_playlist().all()
        result: List[Tuple[int, str, Optional[int]]] = []
        for n in nodes:
            pid = getattr(n, "ParentID", None)
            try:
                pid = int(pid) if pid is not None else None
            except Exception:
                pid = None
            result.append((int(n.ID), n.Name, pid))
        return result

    def find_playlist_ids_by_name(self, name_substring: str) -> List[int]:
        name_lc = name_substring.lower()
        return [pid for pid, nm, _ in self.fetch_playlists() if name_lc in (nm or "").lower()]

    def playlist_tracks(self, playlist_id: int) -> List[Tuple[str, Path]]:
        assert self.db is not None
        SP = db6.tables.DjmdSongPlaylist
        CT = db6.tables.DjmdContent
        rows = (
            self.db.session.query(SP, CT)  # type: ignore
            .join(CT, CT.ID == SP.ContentID)
            .filter(SP.PlaylistID == int(playlist_id))
            .order_by(SP.TrackNo)
            .all()
        )
        tracks: List[Tuple[str, Path]] = []
        for _, ct in rows:
            title = (ct.Title or ct.FileNameL or ct.FileNameS or "Unknown").strip()
            full_path = normalize_rekordbox_path(ct.FolderPath or "", (ct.FileNameL or ct.FileNameS or ""))
            tracks.append((title, full_path))
        return tracks

    def diagnose(self, playlist_id: int, first: Optional[int] = None) -> List[TrackDiag]:
        diags: List[TrackDiag] = []
        tracks = self.playlist_tracks(playlist_id)
        if first is not None and first > 0:
            tracks = tracks[: first]

        for idx, (title, path) in enumerate(tracks, 1):
            issues: List[str] = []

            # Path-level checks
            path_str = str(path)
            if "\x00" in path_str:
                issues.append("NULL byte in path string")
            ok_utf8, err = safe_utf8(path_str)
            if not ok_utf8:
                issues.append(f"Non-UTF8 path: {err}")
            if len(path_str) > 240:
                issues.append(f"Very long path ({len(path_str)} chars)")
            if path_str.strip() != path_str:
                issues.append("Leading/trailing whitespace in path")

            size_bytes: Optional[int] = None
            header: Optional[str] = None

            if not path.exists():
                issues.append("Source file missing")
            else:
                try:
                    st = path.stat()
                    size_bytes = int(st.st_size)
                    if size_bytes == 0:
                        issues.append("Zero-byte file")
                    elif size_bytes < 100 * 1024:  # <100KB is suspicious for full tracks
                        issues.append(f"Very small file ({size_bytes} bytes)")
                except Exception as e:
                    issues.append(f"stat() error: {e}")

                # Try to open and read first bytes
                try:
                    with path.open("rb") as f:
                        fb = f.read(16)
                    header = sniff_header(fb)
                    if header == "Unknown":
                        issues.append("Unrecognized file header")
                except Exception as e:
                    issues.append(f"read error: {e}")

            diags.append(TrackDiag(index=idx, title=title, path=path, issues=issues, header=header, size_bytes=size_bytes))

        return diags


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnose Rekordbox playlist for problematic tracks")
    ap.add_argument("--name", default="All Liked Stems", help="Playlist name (substring match, case-insensitive)")
    ap.add_argument("--first", type=int, default=5, help="Only check first N tracks initially (0 = all)")
    args = ap.parse_args()

    diag = PlaylistDiagnoser()
    diag.connect()

    ids = diag.find_playlist_ids_by_name(args.name)
    if not ids:
        print(f"No playlists found matching: {args.name}")
        # Help user discover stems-related playlists
        candidates = diag.find_playlist_ids_by_name("stems")
        if candidates:
            print("\nPlaylists containing 'stems':")
            all_pl = {pid: nm for pid, nm, _ in diag.fetch_playlists()}
            for pid in candidates:
                print(f"  - [{pid}] {all_pl.get(pid, '')}")
        sys.exit(1)

    # Prefer the first match and print all matches
    all_pl = {pid: nm for pid, nm, _ in diag.fetch_playlists()}
    print("Matched playlists:")
    for pid in ids:
        print(f"  - [{pid}] {all_pl.get(pid, '')}")

    target_id = ids[0]
    print(f"\nDiagnosing playlist [{target_id}] {all_pl.get(target_id, '')}")

    first_n = None if args.first == 0 else args.first
    diags = diag.diagnose(target_id, first=first_n)

    print("\nResults:")
    problems = 0
    for d in diags:
        status = "OK" if not d.issues else "ISSUES"
        size_str = f", {d.size_bytes} bytes" if d.size_bytes is not None else ""
        header_str = f", header={d.header}" if d.header else ""
        print(f"[{d.index:03}] {status} — {d.title}")
        print(f"      {d.path}{size_str}{header_str}")
        for issue in d.issues:
            problems += 1
            print(f"      - {issue}")

    print("\nSummary:")
    print(f"  Checked tracks: {len(diags)}")
    print(f"  Tracks with issues: {len([d for d in diags if d.issues])}")
    print(f"  Total issues flagged: {problems}")

    if args.first and args.first > 0:
        print("\nTip: Re-run with --first 0 to scan the entire playlist once this spot-check looks good.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)



