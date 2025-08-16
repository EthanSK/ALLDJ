#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import List, Tuple


def is_vocals(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith("_(vocals).flac") or lowered.endswith(" (vocals).flac") or "_vocals" in lowered


def is_instrumental(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith("_(instrumental).flac") or lowered.endswith(" (instrumental).flac") or "instrumental" in lowered


def scan_og_stems(root: Path) -> Tuple[List[Path], List[Path]]:
    vocals: List[Path] = []
    instrumentals: List[Path] = []
    for p in root.rglob("*.flac"):
        if not p.is_file() or p.name.startswith("._"):
            continue
        if is_vocals(p.name):
            vocals.append(p)
        elif is_instrumental(p.name):
            instrumentals.append(p)
        else:
            # default: if contains 'vocals' anywhere else
            if "vocals" in p.stem.lower():
                vocals.append(p)
            else:
                instrumentals.append(p)
    return vocals, instrumentals


def main():
    parser = argparse.ArgumentParser(description="Create two giant playlists for OG-separated stems (Vocals and Instrumentals)")
    parser.add_argument("--og-dir", default="/Volumes/T7 Shield/3000AD/og_separated", help="Path to OG separated stems directory")
    parser.add_argument("--vocals-name", default="OG Vocals (All)", help="Playlist name for all vocals")
    parser.add_argument("--instrumentals-name", default="OG Instrumentals (All)", help="Playlist name for all instrumentals")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Rekordbox")
    parser.add_argument("--sample", type=int, default=5, help="Print up to N sample file paths per playlist in dry run")
    args = parser.parse_args()

    og_root = Path(args.og_dir)
    if not og_root.exists():
        print(f"Error: OG stems directory not found: {og_root}")
        return

    vocals, instrumentals = scan_og_stems(og_root)
    print(f"Scanned: {og_root}")
    print(f"  Vocals:        {len(vocals)} files")
    print(f"  Instrumentals: {len(instrumentals)} files")

    if args.dry_run:
        print("\n[DRY RUN] Would create/update these playlists:")
        print(f"  - {args.vocals_name}: +{len(vocals)} tracks")
        for p in vocals[: args.sample]:
            print(f"      {p}")
        if len(vocals) > args.sample:
            print(f"      ... ({len(vocals) - args.sample} more)")
        print(f"  - {args.instrumentals_name}: +{len(instrumentals)} tracks")
        for p in instrumentals[: args.sample]:
            print(f"      {p}")
        if len(instrumentals) > args.sample:
            print(f"      ... ({len(instrumentals) - args.sample} more)")
        return

    # Real apply: ensure playlists exist and add tracks by absolute path
    try:
        from pyrekordbox import Rekordbox6Database
    except Exception as e:
        print("Error: pyrekordbox is required. pip install pyrekordbox")
        return

    # Locate Rekordbox db
    db_paths = [
        Path.home() / "Library/Pioneer/rekordbox7",
        Path.home() / "Library/Pioneer/rekordbox6",
        Path.home() / "Library/Pioneer/rekordbox",
    ]
    db_dir = next((p for p in db_paths if p.exists()), None)
    if db_dir is None:
        print("Error: Rekordbox database not found")
        return
    db = Rekordbox6Database(db_dir=str(db_dir))

    def get_or_create_playlist(name: str):
        node = db.get_playlist(Name=name).first()
        if node:
            return node
        return db.create_playlist(name)

    def ensure_content(path: Path):
        # Look up by filename; if not exists, add by absolute path
        track = db.get_content(FileNameL=path.name).first()
        if track:
            return track
        return db.add_content(str(path))

    vocals_pl = get_or_create_playlist(args.vocals_name)
    instr_pl = get_or_create_playlist(args.instrumentals_name)

    added_v = 0
    for p in vocals:
        try:
            c = ensure_content(p)
            if c:
                db.add_to_playlist(vocals_pl, c)
                added_v += 1
        except Exception:
            pass

    added_i = 0
    for p in instrumentals:
        try:
            c = ensure_content(p)
            if c:
                db.add_to_playlist(instr_pl, c)
                added_i += 1
        except Exception:
            pass

    print(f"Done. Added {added_v} vocals and {added_i} instrumentals")


if __name__ == "__main__":
    main()


