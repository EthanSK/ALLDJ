#!/usr/bin/env python3

"""
Remove tracks with missing source files from a Rekordbox playlist.

Default target: playlist name contains "All Liked Stems" (case-insensitive).

Usage:
  # Dry-run first 5
  python clean_rekordbox_playlist_missing.py --name "All Liked Stems" --limit 5

  # Actually remove the first 5 missing tracks
  python clean_rekordbox_playlist_missing.py --name "All Liked Stems" --limit 5 --commit

  # Remove all missing tracks
  python clean_rekordbox_playlist_missing.py --name "All Liked Stems" --limit 0 --commit

Notes:
  - Rekordbox should be closed before running with --commit to avoid DB locks.
  - This only removes entries from the playlist; it does not delete files.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import unquote, urlparse

try:
    from pyrekordbox import Rekordbox6Database, db6
except ImportError:
    print("Error: pyrekordbox is required. Install with: pip install pyrekordbox")
    sys.exit(1)


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


def connect_db() -> Rekordbox6Database:
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6",
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    db_dir = next((p for p in db_paths if p.exists()), None)
    if db_dir is None:
        print("Error: Rekordbox database not found under ~/Library/Pioneer")
        sys.exit(1)
    return Rekordbox6Database(db_dir=str(db_dir))


def find_playlists(db: Rekordbox6Database, name_substring: str) -> List[Tuple[int, str]]:
    name_lc = (name_substring or "").lower()
    result: List[Tuple[int, str]] = []
    for n in db.get_playlist().all():
        nm = getattr(n, "Name", "") or ""
        if name_lc in nm.lower():
            result.append((int(n.ID), nm))
    return result


def fetch_playlist_rows(db: Rekordbox6Database, playlist_id: int):
    SP = db6.tables.DjmdSongPlaylist
    CT = db6.tables.DjmdContent
    rows = (
        db.session.query(SP, CT)  # type: ignore
        .join(CT, CT.ID == SP.ContentID)
        .filter(SP.PlaylistID == int(playlist_id))
        .order_by(SP.TrackNo)
        .all()
    )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Remove missing-file tracks from a Rekordbox playlist")
    ap.add_argument("--name", default="All Liked Stems", help="Playlist name (substring match)")
    ap.add_argument("--limit", type=int, default=5, help="Check only first N tracks (0 = all)")
    ap.add_argument("--commit", action="store_true", help="Apply deletions (otherwise dry-run)")
    args = ap.parse_args()

    db = connect_db()
    try:
        matches = find_playlists(db, args.name)
        if not matches:
            print(f"No playlists found matching: {args.name}")
            sys.exit(1)

        print("Matched playlists:")
        for pid, nm in matches:
            print(f"  - [{pid}] {nm}")

        target_id, target_name = matches[0]
        print(f"\nCleaning playlist [{target_id}] {target_name}")

        rows = fetch_playlist_rows(db, target_id)
        total = len(rows)
        if args.limit and args.limit > 0:
            rows = rows[: args.limit]

        missing = []
        checked = 0
        for idx, (sp, ct) in enumerate(rows, 1):
            title = (ct.Title or ct.FileNameL or ct.FileNameS or "Unknown").strip()
            full_path = normalize_rekordbox_path(ct.FolderPath or "", (ct.FileNameL or ct.FileNameS or ""))
            exists = full_path.exists()
            status = "OK" if exists else "MISSING"
            print(f"[{idx:03}] {status} — {title}")
            print(f"      {full_path}")
            if not exists:
                missing.append((sp, ct, full_path))
            checked += 1

        print(f"\nChecked {checked}/{total} tracks. Missing: {len(missing)}")

        if not missing:
            print("Nothing to remove.")
            return

        if not args.commit:
            print("\nDRY RUN — no changes made. Re-run with --commit to remove missing entries.")
            return

        # Delete selected DjmdSongPlaylist rows
        removed = 0
        for sp, ct, p in missing:
            try:
                db.session.delete(sp)  # type: ignore
                removed += 1
            except Exception as e:
                print(f"  ✗ Failed to mark for deletion: {p} — {e}")

        try:
            db.commit()
            print(f"\n✓ Removed {removed} entries from playlist '{target_name}'")
        except Exception as e:
            print(f"\n✗ Commit failed: {e}")
            print("If Rekordbox is open, close it and re-run with --commit.")
            sys.exit(1)

    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)


