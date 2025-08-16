#!/usr/bin/env python3

"""
Clone selected Rekordbox playlist folders under a new parent folder 'wav',
repointing all tracks to corresponding WAV files on disk.

Sources:
- 'ALLDJ Baked'
- 'ALLDJ Stems'
- 'OG Stems'

For each source playlist track, attempts to map the source file path to a WAV
path using known directory mirrors created earlier:
- /Volumes/T7 Shield/3000AD/alldj_stem_separated -> /Volumes/T7 Shield/3000AD/wav_alldj_stem_separated
- /Volumes/T7 Shield/3000AD/og_separated_v2 -> /Volumes/T7 Shield/3000AD/wav_og_separated_v2
- /Volumes/T7 Shield/3000AD/flac_liked_songs -> /Volumes/T7 Shield/3000AD/wav_liked_songs

If a mapped WAV file exists, it is imported (if needed) and added to the cloned
playlist. Tracks without a resolvable WAV counterpart are skipped.

Run with --first-5 to validate on a small sample before full cloning.

Requirements:
- Rekordbox closed
- pyrekordbox installed (pip install pyrekordbox)
"""

from __future__ import annotations

import argparse
import os
import sys
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

def normalize_rb_path(folder: str, name: str) -> Path:
    """Convert Rekordbox DjmdContent folder/name into a local absolute Path.
    Handles file:// URLs and percent-encoding.
    """
    folder = (folder or "").strip()
    name = (name or "").strip()

    name = unquote(name)

    if folder.startswith("file://"):
        parsed = urlparse(folder)
        path_str = parsed.path or folder[len("file://"):]
        folder_path = unquote(path_str)
    else:
        folder_path = unquote(folder)

    if folder_path and not folder_path.endswith("/"):
        folder_path += "/"

    if folder_path.endswith("/" + name):
        full = folder_path
    else:
        full = folder_path + name

    try:
        return Path(full).resolve()
    except Exception:
        return Path(full)


def map_to_wav_path(src_abs: Path) -> Optional[Path]:
    """Map a source absolute path to the corresponding WAV absolute path.

    Known mirrors:
      - /Volumes/T7 Shield/3000AD/alldj_stem_separated -> /Volumes/T7 Shield/3000AD/wav_alldj_stem_separated
      - /Volumes/T7 Shield/3000AD/og_separated_v2 -> /Volumes/T7 Shield/3000AD/wav_og_separated_v2
      - /Volumes/T7 Shield/3000AD/flac_liked_songs -> /Volumes/T7 Shield/3000AD/wav_liked_songs
    """
    s = str(src_abs)
    mappings = [
        ("/Volumes/T7 Shield/3000AD/alldj_stem_separated", "/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
        ("/Volumes/T7 Shield/3000AD/og_separated_v2", "/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
        ("/Volumes/T7 Shield/3000AD/flac_liked_songs", "/Volumes/T7 Shield/3000AD/wav_liked_songs"),
    ]

    for src_base, dst_base in mappings:
        if s.startswith(src_base):
            tail = s[len(src_base):]
            candidate = Path(dst_base + tail)
            # Force .wav extension
            if candidate.suffix.lower() != ".wav":
                candidate = candidate.with_suffix(".wav")
            return candidate

    # Generic extension swap for typical audio files, keep directory
    if src_abs.suffix.lower() in {".flac", ".mp3", ".aif", ".aiff", ".m4a"}:
        return src_abs.with_suffix(".wav")

    return None


@dataclass
class PlaylistNode:
    id: str
    name: str
    parent_id: Optional[str]


class RekordboxWavCloner:
    def __init__(self, first5: bool = False) -> None:
        self.first5 = first5
        self.db: Optional[Rekordbox6Database] = None
        self.id_to_node: Dict[str, PlaylistNode] = {}
        self.smart_playlist_ids: set[str] = set()

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

    def children_of(self, playlist_id: str) -> List[PlaylistNode]:
        return [p for p in self.id_to_node.values() if str(p.parent_id) == str(playlist_id)]

    def is_folder(self, playlist_id: str) -> bool:
        # Heuristic: a folder has children and is not a smart playlist
        return len(self.children_of(playlist_id)) > 0 and playlist_id not in self.smart_playlist_ids

    def find_node_by_name(self, name: str) -> Optional[PlaylistNode]:
        # Prefer nodes that are folders
        matches = [p for p in self.id_to_node.values() if p.name == name]
        if not matches:
            return None
        for m in matches:
            if self.is_folder(m.id):
                return m
        return matches[0]

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
            src = normalize_rb_path(ct.FolderPath or "", name)
            tracks.append((title, src))
        return tracks

    # ----- Clone -----
    def ensure_folder(self, name: str, parent=None):
        assert self.db is not None
        # Prefer reusing existing child under this parent by name
        try:
            matches = self.db.get_playlist(Name=name).all()
        except Exception:
            matches = []
        for pl in matches:
            try:
                if getattr(pl, 'ParentID', None) == getattr(parent, 'ID', None):
                    return pl
            except Exception:
                continue
        # Otherwise create
        return self.db.create_playlist_folder(name, parent=parent)

    def ensure_playlist(self, name: str, parent=None):
        assert self.db is not None
        # Reuse existing playlist under this parent by name; if none, create
        try:
            matches = self.db.get_playlist(Name=name).all()
        except Exception:
            matches = []
        for pl in matches:
            try:
                if getattr(pl, 'ParentID', None) == getattr(parent, 'ID', None):
                    return pl
            except Exception:
                continue
        return self.db.create_playlist(name, parent=parent)

    def import_or_get_track(self, wav_path: Path):
        assert self.db is not None
        existing = self.db.get_content(FolderPath=str(wav_path)).first()
        if existing:
            return existing
        try:
            return self.db.add_content(str(wav_path))
        except Exception:
            return None

    def clone_playlist_recursive(self, src_node: PlaylistNode, dst_parent, playlist_limit: Optional[int] = None) -> int:
        """Clone src_node (folder or playlist) under dst_parent. Returns count of cloned playlists."""
        assert self.db is not None
        cloned_playlists = 0
        children = self.children_of(src_node.id)
        if children:
            # Folder
            dst_folder = self.ensure_folder(src_node.name, parent=dst_parent)
            for child in children:
                if playlist_limit is not None and cloned_playlists >= playlist_limit:
                    break
                cloned_playlists += self.clone_playlist_recursive(child, dst_folder, playlist_limit=playlist_limit - cloned_playlists if playlist_limit is not None else None)
            return cloned_playlists
        else:
            # Playlist (non-smart assumed)
            tracks = self.playlist_tracks(src_node.id)
            if not tracks:
                return cloned_playlists
            dst_playlist = self.ensure_playlist(src_node.name, parent=dst_parent)
            added = 0
            for title, src_abs in tracks:
                wav_abs = map_to_wav_path(src_abs)
                if not wav_abs:
                    continue
                try:
                    if wav_abs.exists():
                        ct = self.import_or_get_track(wav_abs)
                        if ct:
                            try:
                                self.db.add_to_playlist(dst_playlist, ct)
                                added += 1
                            except Exception:
                                pass
                except Exception:
                    pass
            # Count as one cloned playlist
            return cloned_playlists + 1

    def run(self) -> None:
        print("🎵 Cloning Rekordbox folders to WAV under parent 'wav'")
        self.connect()
        self.fetch_playlists()

        # Ensure parent 'wav' folder exists (reuse if present)
        try:
            wav_parent = self.ensure_folder("wav", parent=None)
        except Exception:
            # As a fallback, try to locate existing by name
            try:
                wav_parent = self.db.get_playlist(Name="wav").first()
            except Exception:
                wav_parent = None

        # Find source roots
        roots = [
            ("ALLDJ Baked", None),
            ("ALLDJ Stems", None),
            ("OG Stems", None),
        ]

        # Validate existence
        sources: List[PlaylistNode] = []
        for name, _ in roots:
            node = self.find_node_by_name(name)
            if not node:
                print(f"Warning: Source folder not found in Rekordbox: {name}")
            else:
                sources.append(node)

        if not sources:
            print("No source folders found. Nothing to do.")
            return

        # First-5 mode: clone up to 5 playlists per root
        playlist_limit = 5 if self.first5 else None

        total_cloned = 0
        for src in sources:
            print(f"→ Cloning '{src.name}' ...")
            # Create target root under wav parent matching the name
            dst_root = self.ensure_folder(src.name, parent=wav_parent)
            cloned = self.clone_playlist_recursive(src, dst_root, playlist_limit=playlist_limit)
            total_cloned += cloned
            print(f"  Done: cloned {cloned} playlist(s) from '{src.name}'.")

        # Commit changes
        try:
            assert self.db is not None
            self.db.commit()
            print("\n✓ Changes committed to Rekordbox database.")
        except Exception as e:
            print(f"✗ Error committing changes: {e}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Clone Rekordbox folders to WAV-based copies under parent 'wav'")
    ap.add_argument("--first-5", action="store_true", help="Clone only first 5 playlists per root for validation")
    ap.add_argument("--add-5-sample", action="store_true", help="After cloning, add 5 mapped WAV tracks to the first cloned WAV playlist for verification")
    ap.add_argument("--add-5-any", action="store_true", help="Add 5 existing WAV files from the wav_* folders to a WAV playlist for verification")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    cloner = RekordboxWavCloner(first5=args.first_5)
    cloner.run()

    if args.add_5_sample:
        # Reconnect and fetch current state to add 5 tracks to the first WAV playlist
        try:
            # Local helpers within main to avoid expanding class
            def build_parent_chain(node_map: Dict[str, PlaylistNode], node_id: str) -> List[str]:
                names: List[str] = []
                seen: set[str] = set()
                cur = node_map.get(node_id)
                while cur and cur.id not in seen:
                    seen.add(cur.id)
                    names.append(cur.name)
                    if not cur.parent_id or str(cur.parent_id) == "root":
                        break
                    cur = node_map.get(str(cur.parent_id))
                names.reverse()
                return names

            def find_node_by_path(names: List[str], nodes: Dict[str, PlaylistNode]) -> Optional[PlaylistNode]:
                # Find node whose parent chain names exactly equals names
                for node in nodes.values():
                    chain = build_parent_chain(nodes, node.id)
                    if chain == names:
                        return node
                return None

            cloner = RekordboxWavCloner(first5=False)
            cloner.connect()
            all_nodes = cloner.fetch_playlists()
            id_to_node = cloner.id_to_node
            # Find 'wav' parent and its 'ALLDJ Baked' child folder
            wav_parent = next((n for n in id_to_node.values() if n.name == "wav"), None)
            if not wav_parent:
                print("No 'wav' parent found; skipping add-5.")
                return
            wav_baked = next((n for n in id_to_node.values() if n.name == "ALLDJ Baked" and str(n.parent_id) == str(wav_parent.id)), None)
            if not wav_baked:
                print("No 'ALLDJ Baked' under 'wav'. Will try 'ALLDJ Stems'/'OG Stems'.")

            # Find original 'ALLDJ Baked' (not under 'wav')
            original_baked = next((n for n in id_to_node.values() if n.name == "ALLDJ Baked" and str(n.parent_id) != str(wav_parent.id)), None)
            if not original_baked:
                print("Original 'ALLDJ Baked' not found; skipping add-5.")
                return

            # Choose first child playlist under original baked
            orig_children = [n for n in id_to_node.values() if str(n.parent_id) == str(original_baked.id)]
            # Pick a leaf (no further children)
            def has_children(n: PlaylistNode) -> bool:
                return any(str(c.parent_id) == n.id for c in id_to_node.values())

            orig_leaf = next((n for n in orig_children if not has_children(n)), None)
            if not orig_leaf:
                print("No original leaf playlist found under 'ALLDJ Baked'. Trying 'ALLDJ Stems'...")
                # Try ALLDJ Stems instead
                original_stems = next((n for n in id_to_node.values() if n.name == "ALLDJ Stems" and str(n.parent_id) != str(wav_parent.id)), None)
                wav_stems = next((n for n in id_to_node.values() if n.name == "ALLDJ Stems" and str(n.parent_id) == str(wav_parent.id)), None)
                if original_stems and wav_stems:
                    orig_children = [n for n in id_to_node.values() if str(n.parent_id) == str(original_stems.id)]
                    orig_leaf = next((n for n in orig_children if not has_children(n)), None)
                    if not orig_leaf:
                        print("No original leaf found under 'ALLDJ Stems'. Trying 'OG Stems'...")
                        original_og = next((n for n in id_to_node.values() if n.name == "OG Stems" and str(n.parent_id) != str(wav_parent.id)), None)
                        wav_og = next((n for n in id_to_node.values() if n.name == "OG Stems" and str(n.parent_id) == str(wav_parent.id)), None)
                        if original_og and wav_og:
                            orig_children = [n for n in id_to_node.values() if str(n.parent_id) == str(original_og.id)]
                            orig_leaf = next((n for n in orig_children if not has_children(n)), None)
                            if orig_leaf:
                                dst_parent = wav_og
                            else:
                                print("No original leaf found under 'OG Stems'; skipping add-5.")
                                return
                        else:
                            print("Missing 'OG Stems' pair; skipping add-5.")
                            return
                    else:
                        dst_parent = wav_stems
                else:
                    print("Missing 'ALLDJ Stems' pair; skipping add-5.")
                    return
            else:
                dst_parent = wav_baked

            # Find matching WAV playlist by name under dst_parent; if not found, fall back to any wav leaf
            def has_children(n: PlaylistNode) -> bool:
                return any(str(c.parent_id) == n.id for c in id_to_node.values())
            dst_leaf = next((n for n in id_to_node.values() if n.name == orig_leaf.name and str(n.parent_id) == str(dst_parent.id) and not has_children(n)), None)
            if not dst_leaf:
                # fallback: pick any wav leaf under dst_parent
                candidates = [n for n in id_to_node.values() if str(n.parent_id) == str(dst_parent.id) and not has_children(n)]
                if candidates:
                    dst_leaf = candidates[0]
                else:
                    # last resort: any leaf under wav parent
                    any_wav_leaf = next((n for n in id_to_node.values() if not has_children(n) and str(n.parent_id) == str(wav_parent.id)), None)
                    if any_wav_leaf:
                        dst_leaf = any_wav_leaf
                    else:
                        print("No matching WAV playlist found; skipping add-5.")
                        return

            # Fetch source tracks from the original leaf
            src_tracks = cloner.playlist_tracks(orig_leaf.id)
            if not src_tracks:
                print("Original playlist has no tracks; skipping add-5.")
                return

            # Create or get destination playlist object in DB
            assert cloner.db is not None
            # Find the actual playlist object by name under its parent
            # Reconstruct parent object by traversing chain
            # Resolve actual dst playlist object by ID
            dst_playlist = cloner.db.get_playlist(ID=int(dst_leaf.id)).first()
            if not dst_playlist:
                # fallback: recreate
                parent_obj = cloner.db.get_playlist(Name=dst_parent.name).first()
                dst_playlist = cloner.ensure_playlist(dst_leaf.name, parent=parent_obj)

            added = 0
            for title, src_abs in src_tracks:
                wav_abs = map_to_wav_path(src_abs)
                if not wav_abs:
                    continue
                try:
                    if wav_abs.exists():
                        ct = cloner.import_or_get_track(wav_abs)
                        if ct:
                            try:
                                cloner.db.add_to_playlist(dst_playlist, ct)
                                added += 1
                            except Exception:
                                pass
                except Exception:
                    pass
                if added >= 5:
                    break

            try:
                cloner.db.commit()
            except Exception:
                pass
            print(f"Added {added} WAV tracks to '{dst_leaf.name}' under 'wav/{dst_parent.name}'.")
        except Exception as e:
            print(f"add-5-sample error: {e}")

    if args.add_5_any:
        try:
            cloner = RekordboxWavCloner(first5=False)
            cloner.connect()
            cloner.fetch_playlists()
            assert cloner.db is not None

            # Collect up to 5 WAV files from known destination folders
            candidates: List[Path] = []
            search_roots = [
                Path("/Volumes/T7 Shield/3000AD/wav_liked_songs"),
                Path("/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
                Path("/Volumes/T7 Shield/3000AD/wav_og_separated_v2"),
            ]
            for root in search_roots:
                try:
                    if root.exists():
                        for p in root.rglob("*.wav"):
                            if p.is_file():
                                candidates.append(p)
                                if len(candidates) >= 5:
                                    break
                except Exception:
                    pass
                if len(candidates) >= 5:
                    break

            if not candidates:
                print("No WAV files found under wav_* directories; skipping add-5-any.")
                return

            # Find 'wav' parent
            wav_parent = next((n for n in cloner.id_to_node.values() if n.name == "wav"), None)
            # Find a leaf playlist under wav; if none, create 'Sample Check'
            def has_children(n: PlaylistNode) -> bool:
                return any(str(c.parent_id) == n.id for c in cloner.id_to_node.values())

            target_leaf = next((n for n in cloner.id_to_node.values() if str(n.parent_id) == (wav_parent.id if wav_parent else None) and not has_children(n)), None)

            if wav_parent and not target_leaf:
                parent_obj = cloner.db.get_playlist(Name=wav_parent.name).first()
                target_leaf = PlaylistNode(id="-1", name="Sample Check", parent_id=str(wav_parent.id))
                dst_playlist = cloner.ensure_playlist(target_leaf.name, parent=parent_obj)
            else:
                dst_playlist = cloner.db.get_playlist(ID=int(target_leaf.id)).first() if target_leaf else None
                if not dst_playlist and wav_parent:
                    parent_obj = cloner.db.get_playlist(Name=wav_parent.name).first()
                    dst_playlist = cloner.ensure_playlist("Sample Check", parent=parent_obj)

            if not dst_playlist:
                print("Could not resolve destination WAV playlist; skipping add-5-any.")
                return

            added = 0
            for wavp in candidates:
                ct = cloner.import_or_get_track(wavp)
                if ct:
                    try:
                        cloner.db.add_to_playlist(dst_playlist, ct)
                        added += 1
                    except Exception:
                        pass
                if added >= 5:
                    break

            try:
                cloner.db.commit()
            except Exception:
                pass
            print(f"Added {added} WAV tracks to playlist '{getattr(dst_playlist, 'Name', 'Sample Check')}'.")
        except Exception as e:
            print(f"add-5-any error: {e}")


if __name__ == "__main__":
    main()


