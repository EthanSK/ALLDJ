#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Dict, List
import sys
import re

try:
    from mutagen.flac import FLAC
except Exception as e:
    print("Error: mutagen is required. Install with: pip install mutagen")
    sys.exit(1)


DEFAULT_FIELDS = [
    "TITLE",
    "ARTIST",
    "ALBUM",
    "ALBUMARTIST",
    "TRACKNUMBER",
    "DATE",
    "GENRE",
    "BPM",
    "INITIALKEY",
]


def stem_base_without_suffix(path: Path) -> str:
    base = path.stem
    lowered = base.lower()
    for marker in ["_(vocals)", "_(instrumental)", " (vocals)", " (instrumental)"]:
        if lowered.endswith(marker):
            return base[: -len(marker)]
    return base


def normalize_base(name: str) -> str:
    """Normalize a stem/original base for matching.

    - Lowercase
    - Strip leading numeric indices like "111_" or "01-01 "
    - Collapse spaces/underscores/hyphens
    """
    s = name.lower()
    s = re.sub(r"^[\s\-_]*\d{1,4}([\-_]\d{1,4})?[\s\-_]*", "", s)
    s = re.sub(r"[\s\-_]+", " ", s).strip()
    return s


def build_flac_index(flac_dir: Path) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    for p in flac_dir.glob("*.flac"):
        if not p.is_file() or p.name.startswith("._"):
            continue
        index[p.stem.lower()] = p
    return index


def copy_fields_from_to(orig: FLAC, dest: FLAC, fields: List[str], overwrite: bool) -> int:
    updated = 0
    for key in fields:
        # Mutagen FLAC tags are case-insensitive, but normalize to upper
        src_vals = list(orig.get(key, [])) or list(orig.get(key.lower(), []))
        if not src_vals:
            continue
        if overwrite or not dest.get(key):
            dest[key] = src_vals
            updated += 1
    return updated


def main():
    parser = argparse.ArgumentParser(description="Copy core FLAC metadata (TITLE, ARTIST, etc.) from original flac/ to stem files")
    parser.add_argument("--flac-dir", default=str((Path(__file__).resolve().parent / "flac")), help="Path to directory containing original FLAC files")
    parser.add_argument("--stems-dir", default="/Volumes/T7 Shield/3000AD/alldj_stem_separated", help="Path to stems root directory")
    parser.add_argument("--fields", default=",".join(DEFAULT_FIELDS), help="Comma-separated list of Vorbis fields to copy")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination fields even if present")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N stems (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing changes")
    parser.add_argument("--verbose", action="store_true", help="Print per-file operations")
    args = parser.parse_args()

    flac_dir = Path(args.flac_dir)
    stems_root = Path(args.stems_dir)
    if not flac_dir.exists():
        print(f"Error: flac dir not found: {flac_dir}")
        return
    if not stems_root.exists():
        print(f"Error: stems dir not found: {stems_root}")
        return

    fields = [f.strip().upper() for f in args.fields.split(",") if f.strip()]
    print(f"Fields to copy: {fields}")

    index = build_flac_index(flac_dir)
    stems = [p for p in stems_root.rglob("*.flac") if p.is_file() and not p.name.startswith("._")]
    stems.sort()
    total = len(stems) if args.limit <= 0 else min(args.limit, len(stems))
    updated_files = 0
    skipped = 0
    missing = 0

    for i, stem in enumerate(stems[:total], start=1):
        raw_base = stem_base_without_suffix(stem)
        base = raw_base.lower()
        norm = normalize_base(raw_base)
        orig_path = index.get(base) or index.get(norm)
        # Fallback: try any original where stem startswith original base
        if not orig_path:
            for k, v in index.items():
                if base.startswith(k) or norm.startswith(k) or k.startswith(norm):
                    orig_path = v
                    break
        if not orig_path:
            missing += 1
            if args.verbose:
                print(f"[{i}/{total}] missing original for stem: {stem.name}")
            continue

        try:
            orig = FLAC(str(orig_path))
            dest = FLAC(str(stem))
        except Exception as e:
            skipped += 1
            if args.verbose:
                print(f"[{i}/{total}] read error: {stem.name}: {e}")
            continue

        num = copy_fields_from_to(orig, dest, fields, overwrite=args.overwrite)
        if num > 0:
            updated_files += 1
            if args.verbose:
                print(f"[{i}/{total}] {stem.name}: updated {num} fields from {orig_path.name}")
            if not args.dry_run:
                try:
                    dest.save()
                except Exception as e:
                    if args.verbose:
                        print(f"    save failed: {e}")
        else:
            if args.verbose:
                print(f"[{i}/{total}] {stem.name}: no changes")

        if not args.verbose and i % 50 == 0:
            print(f"Processed {i}/{total}...")

    print("\nSummary:")
    print(f"  Processed: {total}")
    print(f"  Updated files: {updated_files}")
    print(f"  Missing originals: {missing}")
    print(f"  Skipped/errors: {skipped}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)


