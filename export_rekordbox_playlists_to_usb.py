#!/usr/bin/env python3

"""
Export ALL Rekordbox static playlists (excluding smart playlists) to USB, copying
the exact file paths referenced in the Rekordbox database. Generates M3U8 files
with absolute paths to the copied files. Resumable via a state file on the USB.

Example:
  python export_rekordbox_playlists_to_usb.py --usb-path \
    "/Volumes/DJYING" --resume
"""

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

try:
    from pyrekordbox import Rekordbox6Database, db6
except ImportError:
    print("Error: pyrekordbox is required. Install with: pip install pyrekordbox")
    sys.exit(1)


# ------------------------ Helpers ------------------------

def atomic_write_text(dest: Path, content: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(dest.parent), encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)


def copy_file_atomic(src: Path, dest: Path) -> None:
    import shutil
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(dest.parent)) as tmp:
        with src.open("rb") as fsrc:
            shutil.copyfileobj(fsrc, tmp)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)


def file_same_size(src: Path, dest: Path) -> bool:
    try:
        return src.stat().st_size == dest.stat().st_size
    except FileNotFoundError:
        return False


def map_src_to_usb_tree(music_root: Path, src_abs: Path) -> Path:
    """Mirror the absolute path under ALLDJ_MUSIC by removing the leading '/'.
    Example: '/Volumes/T7/file.flac' -> 'ALLDJ_MUSIC/Volumes/T7/file.flac'
    """
    parts = [p for p in src_abs.parts if p]
    rel = Path(*parts[1:]) if parts and parts[0] == os.sep else Path(*parts)
    return (music_root / rel)


def build_m3u8(playlist_name: str, tracks: List[Tuple[str, Path]]) -> str:
    lines = ["#EXTM3U", f"# {playlist_name} - Exported from Rekordbox"]
    for title, abs_path in tracks:
        # Duration unknown here; use 0 to be safe
        safe_title = title or abs_path.name
        lines.append(f"#EXTINF:0,{safe_title}")
        lines.append(str(abs_path))
    return "\n".join(lines) + "\n"


# ------------------------ Exporter ------------------------

@dataclass
class PlaylistNode:
    id: str
    name: str
    parent_id: Optional[str]


class RekordboxUSBExporter:
    def __init__(self, usb_root: Path, resume: bool = True) -> None:
        self.usb_root = usb_root
        self.music_dest_root = usb_root / "ALLDJ_MUSIC"
        self.playlists_root = usb_root / "PLAYLISTS"
        self.state_path = usb_root / ".alldj_export_state.json"
        self.resume = resume
        self.state: Dict = {
            "version": 1,
            "playlists": {},  # playlist_id -> status dict
        }
        self.db: Optional[Rekordbox6Database] = None
        self.id_to_node: Dict[str, PlaylistNode] = {}
        self.smart_playlist_ids: set[str] = set()

    # ----- State -----
    def load_state(self) -> None:
        if self.resume and self.state_path.exists():
            try:
                self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def save_state(self) -> None:
        if not self.resume:
            return
        atomic_write_text(self.state_path, json.dumps(self.state, indent=2))

    # ----- DB -----
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

    def fetch_playlists(self) -> List[PlaylistNode]:
        assert self.db is not None
        nodes = self.db.get_playlist().all()
        result: List[PlaylistNode] = []
        for n in nodes:
            pid = getattr(n, "ParentID", None)
            if isinstance(pid, bytes):
                try:
                    pid = pid.decode("utf-8", errors="ignore")
                except Exception:
                    pid = None
            result.append(PlaylistNode(id=str(n.ID), name=n.Name, parent_id=pid))
        # Detect smart playlists via DjmdSmartList
        try:
            Smart = db6.tables.DjmdSmartList
            smart_rows = self.db.session.query(Smart).all()  # type: ignore
            self.smart_playlist_ids = {str(r.PlaylistID) for r in smart_rows}
        except Exception:
            self.smart_playlist_ids = set()
        self.id_to_node = {p.id: p for p in result}
        return result

    def is_folder(self, playlist_id: str) -> bool:
        # Heuristic: a folder has children in djmdPlaylist where ParentID == this id
        try:
            children = self.db.get_playlist(ParentID=self.id_to_node[playlist_id].id).all()  # type: ignore
            return len(children) > 0 and playlist_id not in self.smart_playlist_ids
        except Exception:
            return False

    def _normalize_rb_path(self, folder: str, name: str) -> Path:
        """Convert Rekordbox DjmdContent folder/name into a local absolute Path.
        Handles file:// URLs and percent-encoding.
        """
        folder = (folder or "").strip()
        name = (name or "").strip()

        # Decode URL-encodings in name as well
        name = unquote(name)

        # Handle file:// URL in folder
        if folder.startswith("file://"):
            parsed = urlparse(folder)
            path_str = parsed.path or folder[len("file://"):]
            folder_path = unquote(path_str)
        else:
            folder_path = unquote(folder)

        if folder_path and not folder_path.endswith("/"):
            folder_path += "/"

        # Some RB folders may already include the filename; guard against double join
        if folder_path.endswith("/" + name):
            full = folder_path
        else:
            full = folder_path + name

        try:
            return Path(full).resolve()
        except Exception:
            return Path(full)

    def playlist_path(self, playlist_id: str) -> Path:
        # Build folder path from root to this node using names
        parts: List[str] = []
        cur = self.id_to_node.get(playlist_id)
        visited = set()
        while cur and cur.id not in visited:
            visited.add(cur.id)
            parts.append(cur.name)
            if not cur.parent_id or str(cur.parent_id) == "root":
                break
            cur = self.id_to_node.get(str(cur.parent_id))
        parts.reverse()
        # The last element is the playlist name; directories are preceding parts
        if parts:
            return Path(*parts[:-1]), parts[-1]
        return Path("."), playlist_id

    def playlist_tracks(self, playlist_id: str) -> List[Tuple[str, Path]]:
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
        for sp, ct in rows:
            name = (ct.FileNameL or ct.FileNameS or "").strip()
            title = (ct.Title or name)
            src = self._normalize_rb_path(ct.FolderPath or "", name)
            tracks.append((title, src))
        return tracks

    # ----- Export -----
    def export(self, limit: Optional[int] = None, include_path_contains: Optional[List[str]] = None) -> None:
        print("🎚️  Exporting Rekordbox static playlists → USB")
        print("===========================================")
        if not self.usb_root.exists():
            print(f"Error: USB path not found: {self.usb_root}")
            sys.exit(1)
        self.music_dest_root.mkdir(parents=True, exist_ok=True)
        self.playlists_root.mkdir(parents=True, exist_ok=True)
        self.load_state()
        self.connect()
        playlists = self.fetch_playlists()

        # Filter eligible playlists: non-smart and not folders (i.e., have songs)
        eligible: List[PlaylistNode] = []
        for p in playlists:
            if p.id in self.smart_playlist_ids:
                continue
            # We will check contents later; include all nodes tentatively
            eligible.append(p)

        processed = 0
        total = len(eligible)
        for p in eligible:
            if limit and processed >= limit:
                break
            # Skip folders by checking if they have any songs
            tr = self.playlist_tracks(p.id)
            if not tr:
                continue
            processed += 1

            status = self.state.get("playlists", {}).get(p.id, {})
            if status.get("completed"):
                print(f"[{processed}/{total}] {p.name} — already completed, skipping")
                continue

            rel_dir, display = self.playlist_path(p.id)
            pl_dir = (self.playlists_root / rel_dir).resolve()
            m3u8_path = pl_dir / (display + ".m3u8")

            # Optional path filter: only include playlists whose hierarchical path contains any of the filters
            if include_path_contains:
                full_rel = (rel_dir / display).as_posix().lower()
                filters = [f.lower() for f in include_path_contains]
                if not any(f in full_rel for f in filters):
                    continue

            print(f"[{processed}/{total}] Exporting: {rel_dir}/{display}")

            exported: List[Tuple[str, Path]] = []
            copied = 0
            for title, src_abs in tr:
                try:
                    src_abs = src_abs.resolve()
                except Exception:
                    pass
                dest_abs = map_src_to_usb_tree(self.music_dest_root, src_abs)
                if src_abs.exists():
                    if not dest_abs.exists() or not file_same_size(src_abs, dest_abs):
                        copy_file_atomic(src_abs, dest_abs)
                    exported.append((title, dest_abs))
                    copied += 1
                else:
                    # Missing source: skip but still include nothing
                    pass

                if copied % 50 == 0:
                    self.state.setdefault("playlists", {})[p.id] = {
                        "completed": False,
                        "tracks_total": len(tr),
                        "tracks_exported": copied,
                        "name": p.name,
                    }
                    self.save_state()

            # Write M3U8 referencing copied files
            if exported:
                content = build_m3u8(display, exported)
                atomic_write_text(m3u8_path, content)

            # Mark completed
            self.state.setdefault("playlists", {})[p.id] = {
                "completed": True,
                "tracks_total": len(tr),
                "tracks_exported": copied,
                "m3u8_path": str(m3u8_path),
                "name": p.name,
            }
            self.save_state()

        print("\n✅ Export complete (or up-to-date).")
        print(f"Playlists at: {self.playlists_root}")
        print(f"Music at: {self.music_dest_root}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export Rekordbox playlists (non-smart) to USB with exact file paths")
    ap.add_argument("--usb-path", required=True, help="Mounted USB path, e.g., /Volumes/DJYING")
    ap.add_argument("--limit", type=int, default=0, help="Process only first N eligible playlists (0 = all)")
    ap.add_argument("--no-resume", action="store_true", help="Do not read/write state file")
    ap.add_argument(
        "--include-path-contains",
        action="append",
        default=[],
        help="Only export playlists whose hierarchical path contains this substring (can repeat)",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    exporter = RekordboxUSBExporter(usb_root=Path(args.usb_path).resolve(), resume=not args.no_resume)
    try:
        exporter.export(
            limit=(args.limit if args.limit and args.limit > 0 else None),
            include_path_contains=(args.include_path_contains or None),
        )
    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved (if resume enabled). Re-run to continue.")
        sys.exit(1)


if __name__ == "__main__":
    main()


