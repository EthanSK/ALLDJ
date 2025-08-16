#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
METADATA_PATH = ROOT / "music_collection_metadata.json"
FLAC_DIR = ROOT / "flac"


def normalize_title(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[\s\-_]+", " ", s)
    return s


def build_known_titles() -> Dict[str, None]:
    known: Dict[str, None] = {}
    # From metadata
    if METADATA_PATH.exists():
        try:
            data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
            for t in data.get("tracks", []):
                title = t.get("title") or t.get("Title")
                if title:
                    known[normalize_title(title)] = None
        except Exception:
            pass
    # From flac filenames
    if FLAC_DIR.exists():
        for p in FLAC_DIR.glob("*.flac"):
            known[normalize_title(p.stem)] = None
    return known


def strip_leading_index(name: str) -> Tuple[str, bool]:
    """Strip leading numeric prefix like '111_' or '01-02 '"""
    new = re.sub(r"^[\s\-_]*\d{1,4}([\-_]\d{1,4})?[\s\-_]*", "", name)
    return new, new != name


def propose_renames(og_dir: Path, limit: int, force: bool) -> List[Tuple[Path, Path]]:
    known_titles = build_known_titles()
    stems = [p for p in og_dir.rglob("*.flac") if p.is_file() and not p.name.startswith("._")]
    stems.sort()
    proposals: List[Tuple[Path, Path]] = []
    count = 0
    for p in stems:
        base = p.stem
        # Remove stem suffix markers for title comparison
        base_clean = base
        for suf in ["_(Vocals)", "_(Instrumental)", " (Vocals)", " (Instrumental)"]:
            if base_clean.endswith(suf):
                base_clean = base_clean[: -len(suf)]
                break
        stripped, changed = strip_leading_index(base_clean)
        if not changed:
            continue
        # Only propose if stripped matches a known title unless forcing
        if force or (normalize_title(stripped) in known_titles):
            # Re-attach stem suffix
            suffix = base[len(base_clean):]
            new_name = stripped + suffix + p.suffix
            proposals.append((p, p.with_name(new_name)))
            count += 1
            if limit and count >= limit:
                break
    return proposals


def main():
    parser = argparse.ArgumentParser(description="Propose renaming OG stems: remove leading numeric prefixes when they are not part of title")
    parser.add_argument("--og-dir", default="/Volumes/T7 Shield/3000AD/og_separated", help="Path to OG stems directory")
    parser.add_argument("--limit", type=int, default=5, help="Only propose first N renames (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without performing renames")
    parser.add_argument("--force", action="store_true", help="Strip numeric prefixes even if title isn't recognized")
    args = parser.parse_args()

    og_dir = Path(args.og_dir)
    if not og_dir.exists():
        print(f"Error: OG stems dir not found: {og_dir}")
        return

    proposals = propose_renames(og_dir, args.limit, force=args.force)
    if not proposals:
        print("No renames proposed (either no numeric prefixes or not confidently matched to known titles)")
        return

    print(f"Proposed {len(proposals)} rename(s):")
    for src, dst in proposals:
        print(f"  {src.name} -> {dst.name}")

    if args.dry_run:
        print("\n[DRY RUN] No files renamed.")
        return

    # Apply renames
    for src, dst in proposals:
        try:
            src.rename(dst)
        except Exception as e:
            print(f"  Failed to rename {src.name}: {e}")
    print("Done renaming proposed files.")


if __name__ == "__main__":
    main()


