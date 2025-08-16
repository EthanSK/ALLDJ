#!/usr/bin/env python3

"""
Prune ALLDJ Stems playlists using a source-of-truth playlist.

Removes any tracks from the `ALLDJ Stems` nested folder playlist structure that
are NOT present in the top-level source-of-truth playlist (default: "All Liked Stems").

Safety features:
- Dry-run by default (no DB changes)
- --limit to remove only the first N items initially (default 5)
- Clear summary per playlist

Usage examples:
  # Preview first 5 removals only (dry-run)
  python prune_stems_playlists_by_source.py \
    --source "All Liked Stems" --root-folder "ALLDJ Stems" --limit 5

  # Apply the removals for the first 5
  python prune_stems_playlists_by_source.py \
    --source "All Liked Stems" --root-folder "ALLDJ Stems" --limit 5 --commit

  # Apply all removals
  python prune_stems_playlists_by_source.py \
    --source "All Liked Stems" --root-folder "ALLDJ Stems" --limit 0 --commit

Notes:
- Close Rekordbox before running with --commit to avoid database locks.
- This script removes entries from playlists only. It does not delete any audio files.
"""

import argparse
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

try:
    from pyrekordbox import Rekordbox6Database, db6
except ImportError:
    print("Error: pyrekordbox is required. Install with: pip install pyrekordbox")
    sys.exit(1)


# ----------------------------- Data models -----------------------------

@dataclass
class PlaylistNode:
    id: int
    name: str
    parent_id: Optional[int]


# ----------------------------- DB helpers -----------------------------

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


def load_all_nodes(db: Rekordbox6Database) -> List[PlaylistNode]:
    nodes = []
    for n in db.get_playlist().all():
        try:
            pid = getattr(n, "ParentID", None)
            if isinstance(pid, bytes):
                try:
                    pid = int(pid.decode("utf-8", errors="ignore"))
                except Exception:
                    pid = None
            elif isinstance(pid, str):
                try:
                    pid = int(pid)
                except Exception:
                    pid = None
            nodes.append(PlaylistNode(id=int(n.ID), name=n.Name, parent_id=pid))
        except Exception:
            # Skip any malformed rows
            continue
    return nodes


def build_children_index(nodes: Iterable[PlaylistNode]) -> Dict[Optional[int], List[PlaylistNode]]:
    children: Dict[Optional[int], List[PlaylistNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)
    return children


def find_node_by_name(nodes: Iterable[PlaylistNode], name: str) -> Optional[PlaylistNode]:
    name_lc = (name or "").strip().lower()
    exact = [n for n in nodes if (n.name or "").lower() == name_lc]
    if exact:
        return exact[0]
    contains = [n for n in nodes if name_lc in (n.name or "").lower()]
    return contains[0] if contains else None


def traverse_subtree(root: PlaylistNode, children_idx: Dict[Optional[int], List[PlaylistNode]]) -> List[PlaylistNode]:
    result: List[PlaylistNode] = []
    q: deque[PlaylistNode] = deque([root])
    visited: Set[int] = set()
    while q:
        cur = q.popleft()
        if cur.id in visited:
            continue
        visited.add(cur.id)
        result.append(cur)
        for ch in children_idx.get(cur.id, []):
            q.append(ch)
    return result


def get_smart_playlist_ids(db: Rekordbox6Database) -> Set[int]:
    smart_ids: Set[int] = set()
    # DjmdSmartList might not exist depending on pyrekordbox version
    try:
        Smart = db6.tables.DjmdSmartList  # type: ignore[attr-defined]
        rows = db.session.query(Smart).all()  # type: ignore
        for r in rows:
            try:
                smart_ids.add(int(r.PlaylistID))
            except Exception:
                pass
    except Exception:
        pass
    return smart_ids


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


def get_playlist_content_ids(db: Rekordbox6Database, playlist_id: int) -> Set[int]:
    rows = fetch_playlist_rows(db, playlist_id)
    ids: Set[int] = set()
    for sp, ct in rows:
        try:
            ids.add(int(ct.ID))
        except Exception:
            continue
    return ids


# ----------------------------- Pruning logic -----------------------------

def prune_playlists(
    db: Rekordbox6Database,
    source_playlist_name: str,
    root_folder_name: str,
    limit: int,
    commit: bool,
) -> None:
    nodes = load_all_nodes(db)
    if not nodes:
        print("No playlists found in database.")
        return

    source_node = find_node_by_name(nodes, source_playlist_name)
    if not source_node:
        print(f"Source-of-truth playlist not found: {source_playlist_name}")
        print("Available playlists (first 30):")
        for n in nodes[:30]:
            print(f"  - {n.name}")
        sys.exit(1)

    root_node = find_node_by_name(nodes, root_folder_name)
    if not root_node:
        print(f"Root folder not found: {root_folder_name}")
        sys.exit(1)

    children_idx = build_children_index(nodes)
    subtree_nodes = traverse_subtree(root_node, children_idx)
    smart_ids = get_smart_playlist_ids(db)

    print(f"Source-of-truth: [{source_node.id}] {source_node.name}")
    print(f"Root folder:     [{root_node.id}] {root_node.name}")
    print(f"Subtree nodes:   {len(subtree_nodes)} (including folders)")

    allowed_ids = get_playlist_content_ids(db, source_node.id)
    print(f"Allowed tracks (by ContentID) in source: {len(allowed_ids)}")

    # Determine actual playlists (leafs with tracks)
    to_process: List[PlaylistNode] = []
    for node in subtree_nodes:
        if node.id in smart_ids:
            continue
        # If it has any tracks, consider it a playlist
        try:
            rows = fetch_playlist_rows(db, node.id)
        except Exception:
            rows = []
        if rows:
            to_process.append(node)

    print(f"Playable playlists under root: {len(to_process)}")

    total_examined = 0
    total_candidates = 0
    total_removed = 0  # actually deleted (only when commit=True)
    planned_total = 0  # planned for removal (respects limit even in dry-run)

    # Iterate playlists
    for node in to_process:
        rows = fetch_playlist_rows(db, node.id)
        candidates: List[Tuple[object, object]] = []  # (SP, CT)
        for sp, ct in rows:
            total_examined += 1
            try:
                cid = int(ct.ID)
            except Exception:
                continue
            if cid not in allowed_ids:
                candidates.append((sp, ct))

        if not candidates:
            print(f"[OK]    {node.name} — no removals needed")
            continue

        total_candidates += len(candidates)
        print(f"[PRUNE] {node.name} — {len(candidates)} to remove")

        # Apply limit across all playlists if specified
        remaining_budget = max(0, limit - planned_total) if limit and limit > 0 else None
        planned = candidates if remaining_budget is None else candidates[:remaining_budget]

        for idx, (sp, ct) in enumerate(planned, 1):
            title = (ct.Title or ct.FileNameL or ct.FileNameS or "Unknown").strip()
            print(f"   - REMOVE: {title}")
            planned_total += 1
            if commit:
                try:
                    db.session.delete(sp)  # type: ignore
                    total_removed += 1
                except Exception as e:
                    print(f"     ✗ Failed: {e}")

        # Stop if limit reached
        if limit and limit > 0 and planned_total >= limit:
            break

    print("\nSUMMARY")
    print("======")
    print(f"Tracks examined:   {total_examined}")
    print(f"Candidates found:  {total_candidates}")
    print(f"To remove (planned): {planned_total}")
    print(f"Removed (applied): {total_removed if commit else 0}")

    if commit:
        try:
            db.commit()
            print("\n✓ Changes committed to database")
        except Exception as e:
            print(f"\n✗ Commit failed: {e}")
            print("If Rekordbox is open, close it and re-run with --commit.")
            sys.exit(1)
    else:
        print("\nDRY RUN — no changes made. Re-run with --commit to apply removals.")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Prune ALLDJ Stems playlists by removing tracks not in the source-of-truth playlist"
    )
    ap.add_argument("--source", default="All Liked Stems", help="Source-of-truth playlist name")
    ap.add_argument("--root-folder", default="ALLDJ Stems", help="Root folder name containing target playlists")
    ap.add_argument("--limit", type=int, default=5, help="Max removals to apply (0 = no limit)")
    ap.add_argument("--commit", action="store_true", help="Apply changes (otherwise dry-run)")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    db = connect_db()
    try:
        prune_playlists(
            db=db,
            source_playlist_name=args.source,
            root_folder_name=args.root_folder,
            limit=args.limit,
            commit=args.commit,
        )
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


