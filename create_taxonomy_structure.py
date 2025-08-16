#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Dict, List, Tuple


def parse_taxonomy(taxonomy_path: Path) -> Dict[str, List[str]]:
    """Parse `tag taxonomy.txt` into mapping: category -> [tags].

    - Category is any non-empty line that doesn't contain " - " and isn't whitespace only.
    - A tag line matches "<tag> - <description>"; we extract <tag> (trim).
    - Blocks are separated by blank lines or next category.
    """
    categories: Dict[str, List[str]] = {}
    current_cat: str | None = None
    for raw in taxonomy_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if " - " in line:
            tag = line.split(" - ", 1)[0].strip()
            if not tag:
                continue
            if current_cat is None:
                current_cat = "Uncategorized"
            categories.setdefault(current_cat, []).append(tag)
        else:
            current_cat = line
            categories.setdefault(current_cat, [])
    return categories


def main():
    parser = argparse.ArgumentParser(description="Create Rekordbox playlists/folders from tag taxonomy (structure-only, no tracks)")
    parser.add_argument("--taxonomy", default="tag taxonomy.txt", help="Path to tag taxonomy file")
    parser.add_argument("--root-name", default="ALLDJ Stems", help="Root folder name in Rekordbox")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Rekordbox")
    parser.add_argument("--limit-tags", type=int, default=0, help="Create at most N tags per category (0 = all)")
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Error: taxonomy file not found: {taxonomy_path}")
        return

    categories = parse_taxonomy(taxonomy_path)
    print(f"Parsed {len(categories)} categories from taxonomy")

    try:
        from pyrekordbox import Rekordbox6Database
    except Exception as e:
        print("Error: pyrekordbox is required. Install with: pip install pyrekordbox")
        return

    # Locate Rekordbox database dir
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6",
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    db_dir = next((p for p in db_paths if p.exists()), None)
    if db_dir is None:
        print("Error: Could not find Rekordbox database directory under ~/Library/Pioneer/")
        return

    db = Rekordbox6Database(db_dir=str(db_dir))

    def get_or_create_folder(name: str, parent=None):
        if args.dry_run:
            print(f"[DRY] folder: {name} under {getattr(parent, 'Name', 'ROOT')}")
            return None
        existing = db.get_playlist(Name=name).first()
        if existing and getattr(existing, "NodeType", 0) == 0:  # 0 = folder
            return existing
        node = db.create_playlist_folder(name)
        if parent and existing is None:
            try:
                db.move_playlist(node, parent)
            except Exception:
                pass
        return node

    def get_or_create_playlist(name: str, parent):
        if args.dry_run:
            print(f"[DRY] playlist: {name} under {getattr(parent, 'Name', 'ROOT')}")
            return None
        existing = db.get_playlist(Name=name).first()
        if existing and getattr(existing, "NodeType", 1) == 1:  # 1 = playlist
            return existing
        node = db.create_playlist(name)
        if parent and existing is None:
            try:
                db.move_playlist(node, parent)
            except Exception:
                pass
        return node

    # Root
    root = get_or_create_folder(args.root-name if hasattr(args, 'root-name') else args.root_name)
    if args.dry_run:
        print(f"[DRY] Using root: {args.root_name}")

    # Create category folders and vocals/instrumentals subfolders with empty playlists
    for category, tags in categories.items():
        tag_list = tags if args.limit_tags <= 0 else tags[: args.limit_tags]
        if not tag_list:
            continue
        cat_node = get_or_create_folder(category, parent=root)
        vocals_node = get_or_create_folder("Vocals", parent=cat_node)
        instr_node = get_or_create_folder("Instrumentals", parent=cat_node)

        for tag in tag_list:
            get_or_create_playlist(tag, parent=vocals_node)
            get_or_create_playlist(tag, parent=instr_node)

    print("Done creating taxonomy-based structure (no tracks added).")


if __name__ == "__main__":
    main()


