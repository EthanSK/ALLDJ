#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import re

try:
    from mutagen.flac import FLAC
except Exception:
    FLAC = None


def parse_taxonomy(taxonomy_path: Path) -> List[Tuple[str, List[str]]]:
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
    return list(categories.items())


def build_stem_tag_index(stems_root: Path) -> Dict[str, Dict[str, List[Path]]]:
    """Return mapping: tag -> { 'vocals': [paths], 'instrumentals': [paths] }.
    Requires ALLDJ_TAGS in FLAC.
    """
    assert FLAC is not None, "mutagen is required"
    index: Dict[str, Dict[str, List[Path]]] = {}
    files = [p for p in stems_root.rglob("*.flac") if p.is_file() and not p.name.startswith("._")]
    for p in files:
        try:
            audio = FLAC(str(p))
        except Exception:
            continue
        tags = [t.strip() for t in list(audio.get("ALLDJ_TAGS", [])) if t and t.strip()]
        if not tags:
            continue
        stem_type = "vocals" if p.stem.endswith("_(Vocals)") or p.stem.endswith(" (Vocals)") else (
            "instrumentals" if p.stem.endswith("_(Instrumental)") or p.stem.endswith(" (Instrumental)") else ""
        )
        if not stem_type:
            # default heuristic: if contains 'vocals' in name
            stem_type = "vocals" if "vocals" in p.stem.lower() else "instrumentals"
        for tag in tags:
            bucket = index.setdefault(tag, {"vocals": [], "instrumentals": []})
            bucket[stem_type].append(p)
    return index


def ensure_content_in_db(db, path: Path):
    """Get or add DjmdContent for path."""
    # Try lookup by filename first
    content = None
    try:
        q = db.get_content(FileNameL=path.name)
        content = q.first()
    except Exception:
        content = None
    if content:
        return content
    # Add new
    return db.add_content(str(path))


def get_node(db, name: str, parent_id):
    """Find a DjmdPlaylist by name and parent. For top-level, parent_id should be 'root'."""
    kwargs = {"Name": name}
    kwargs["ParentID"] = parent_id if parent_id is not None else "root"
    return db.get_playlist(**kwargs).first()


def ensure_playlist(db, name: str, parent_id):
    """Get a playlist by Name+ParentID; create it under the parent if missing."""
    node = get_node(db, name, parent_id)
    if node:
        return node
    return db.create_playlist(name, parent=parent_id)


def ensure_folder(db, name: str, parent):
    """Get a folder by Name+ParentID; create it under parent if missing."""
    node = get_node(db, name, parent_id=parent)
    if node:
        return node
    return db.create_playlist_folder(name, parent=parent)


def normalize_cat(text: str) -> str:
    if not text:
        return ""
    s = text.lower().strip()
    # strip trailing colon
    s = s[:-1] if s.endswith(":") else s
    # remove explicit " (stems)" suffix
    s = re.sub(r"\s*\(stems\)\s*$", "", s)
    # remove parenthetical descriptors anywhere
    s = re.sub(r"\s*\([^\)]*\)", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    parser = argparse.ArgumentParser(description="Fill taxonomy playlists with stem files based on ALLDJ_TAGS")
    parser.add_argument("--taxonomy", default="tag taxonomy.txt", help="Path to tag taxonomy file")
    parser.add_argument("--root-name", default="ALLDJ Stems", help="Root folder name in Rekordbox")
    parser.add_argument("--stems-dir", default="/Volumes/T7 Shield/3000AD/alldj_stem_separated", help="Path to stems root")
    parser.add_argument("--limit-tags", type=int, default=5, help="Process at most N tags total (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not modify Rekordbox")
    parser.add_argument("--reset", action="store_true", help="Before adding, clear existing tracks from target playlists")
    args = parser.parse_args()

    if FLAC is None:
        print("Error: mutagen is required. pip install mutagen")
        return

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Error: taxonomy not found: {taxonomy_path}")
        return
    categories = parse_taxonomy(taxonomy_path)

    stems_root = Path(args.stems_dir)
    if not stems_root.exists():
        print(f"Error: stems dir not found: {stems_root}")
        return
    print("Indexing stems by tags ...")
    tag_index = build_stem_tag_index(stems_root)
    print(f"Indexed {len(tag_index)} tags from stems")

    from pyrekordbox import Rekordbox6Database, db6
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6",
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    db_dir = next((p for p in db_paths if p.exists()), None)
    if db_dir is None:
        print("Error: Rekordbox database not found under ~/Library/Pioneer")
        return
    db = Rekordbox6Database(db_dir=str(db_dir))

    # Resolve or create root folder
    candidates = db.get_playlist(Name=args.root_name).all()
    root = None
    if candidates:
        # Prefer one directly under top-level 'root'
        root = next((c for c in candidates if c.ParentID == 'root'), candidates[0])
    if not root and not args.dry_run:
        # Create at top-level; pyrekordbox doesn't accept 'root' as a parent for creation
        root = db.create_playlist_folder(args.root_name)
    if not root:
        print(f"Error: root folder '{args.root_name}' not found; create structure first")
        return

    # Build category lookup map under root (create on demand if missing)
    children = db.get_playlist(ParentID=root.ID).all()
    cat_map: Dict[str, object] = {normalize_cat(c.Name): c for c in children}

    processed_tags = 0
    available_tags = set(tag_index.keys())
    for category, tags in categories:
        # Only process tags that actually exist in stems
        present = [t for t in tags if t in available_tags]
        for tag in present:
            if args.limit_tags and processed_tags >= args.limit_tags:
                break
            entries = tag_index.get(tag)
            if not entries:
                continue

            # Resolve category allowing variations like "(Stems)", colons, parentheses
            norm_cat = normalize_cat(category)
            # Alias mapping for taxonomy -> rekordbox naming
            if norm_cat == normalize_cat("My Own:"):
                norm_cat = normalize_cat("Personal Tags")
            cat_node = cat_map.get(norm_cat)
            if not cat_node:
                # create missing category folder under root
                if args.dry_run:
                    continue
                display_name = category
                # If taxonomy had colon in name, keep original display
                cat_node = ensure_folder(db, display_name, parent=root.ID)
                cat_map[norm_cat] = cat_node
            vocals_folder = get_node(db, "Vocals", parent_id=cat_node.ID) or ensure_folder(db, "Vocals", parent=cat_node.ID)
            instr_folder = get_node(db, "Instrumentals", parent_id=cat_node.ID) or ensure_folder(db, "Instrumentals", parent=cat_node.ID)
            # Ensure playlists exist under the folders
            vocals_pl = ensure_playlist(db, tag, parent_id=vocals_folder.ID)
            instr_pl = ensure_playlist(db, tag, parent_id=instr_folder.ID)

            # Optionally clear existing songs
            if args.reset and not args.dry_run:
                try:
                    sp = db6.tables.DjmdSongPlaylist
                    db.session.query(sp).filter(sp.PlaylistID == vocals_pl.ID).delete(synchronize_session=False)
                    db.session.query(sp).filter(sp.PlaylistID == instr_pl.ID).delete(synchronize_session=False)
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            def add_many(file_list: List[Path], playlist_node):
                added = 0
                for sp in file_list:
                    try:
                        content = ensure_content_in_db(db, sp)
                        if not args.dry_run and content:
                            db.add_to_playlist(playlist_node, content)
                            added += 1
                    except Exception:
                        pass
                return added

            v_added = add_many(entries.get("vocals", []), vocals_pl)
            i_added = add_many(entries.get("instrumentals", []), instr_pl)
            processed_tags += 1
            print(f"{category} / {tag}: +{v_added} vocals, +{i_added} instrumentals")

        if args.limit_tags and processed_tags >= args.limit_tags:
            break

    print(f"Done. Processed tags: {processed_tags}")


if __name__ == "__main__":
    main()


