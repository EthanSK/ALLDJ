#!/usr/bin/env python3

import json
import os
import re
import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime
import unicodedata
from typing import Dict, List

ROOT = Path(__file__).resolve().parent
METADATA_PATH = ROOT / "music_collection_metadata.json"
FLAC_DIR = ROOT / "flac"


def normalize_text(text: str) -> str:
    if not text:
        return ""
    # NFKD normalize and strip diacritics
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # Lower
    text = text.lower()
    # Remove leading track number patterns (e.g., "01-01 ", "12_", "21-")
    text = re.sub(r"^[\s\-_]*\d{1,3}([\-_]\d{1,3})?[\s\-_]*", "", text)
    # Collapse whitespace and separators
    text = re.sub(r"[\s\-_]+", " ", text)
    # Remove extraneous punctuation except parentheses content which may be part of title
    text = re.sub(r"[\u2018\u2019]", "'", text)  # curly quotes -> straight
    text = text.strip()
    return text


def load_metadata(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_flac_files(flac_dir: Path) -> List[Path]:
    if not flac_dir.exists():
        print(f"Error: FLAC directory not found: {flac_dir}")
        sys.exit(1)
    return sorted([p for p in flac_dir.glob("*.flac") if p.is_file()])


def build_title_index(flac_files: List[Path]) -> Dict[str, List[Path]]:
    index: Dict[str, List[Path]] = {}
    for p in flac_files:
        norm = normalize_text(p.stem)
        index.setdefault(norm, []).append(p)
    return index


def backup_metadata(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(path.stem + f".backup_{ts}" + path.suffix)
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def main():
    parser = argparse.ArgumentParser(description="Update metadata filenames to match current flac/ directory")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N tracks (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write metadata.json; only write reports")
    args = parser.parse_args()

    print("Updating music_collection_metadata.json filenames to match flac/ ...")
    metadata = load_metadata(METADATA_PATH)
    tracks = metadata.get("tracks", [])
    print(f"Loaded {len(tracks)} tracks from metadata")

    flac_files = list_flac_files(FLAC_DIR)
    print(f"Found {len(flac_files)} .flac files in {FLAC_DIR}")

    title_index = build_title_index(flac_files)
    # Precompute normalized stems for fallback matching
    norm_stems = {p: normalize_text(p.stem) for p in flac_files}

    updated = 0
    unchanged = 0
    ambiguous = 0
    missing = 0

    changes_report: List[dict] = []
    ambiguous_report: List[dict] = []
    missing_report: List[dict] = []

    total = len(tracks) if args.limit <= 0 else min(args.limit, len(tracks))
    processed = 0

    for t in tracks:
        if args.limit and processed >= args.limit:
            break
        processed += 1

        title = t.get("title") or t.get("Title") or ""
        old_filename = t.get("filename", "")
        norm = normalize_text(title)
        candidates = title_index.get(norm, [])

        # Fallback 1: startswith/substring match on normalized stems
        if not candidates:
            startswith_matches = [p for p, ns in norm_stems.items() if ns.startswith(norm)]
            contains_matches = [p for p, ns in norm_stems.items() if norm and norm in ns]
            # Prefer startswith if unique, else contains if unique
            if len(startswith_matches) == 1:
                candidates = startswith_matches
            elif len(contains_matches) == 1:
                candidates = contains_matches
            else:
                # Fallback 2: try artist + title combo containment
                artist = (t.get("artist") or t.get("Artist") or "").strip()
                norm_artist = normalize_text(artist)
                combo = f"{norm_artist} {norm}".strip()
                combo_matches = [p for p, ns in norm_stems.items() if combo and combo in ns]
                if len(combo_matches) == 1:
                    candidates = combo_matches

        if not candidates:
            missing += 1
            missing_report.append({
                "title": title,
                "old_filename": old_filename,
            })
            continue

        if len(candidates) > 1:
            ambiguous += 1
            ambiguous_report.append({
                "title": title,
                "old_filename": old_filename,
                "candidates": "; ".join([c.name for c in candidates]),
            })
            continue

        chosen = candidates[0]
        new_filename = chosen.name
        new_relative = f"flac/{new_filename}"

        if old_filename == new_filename and t.get("relative_path") == new_relative:
            unchanged += 1
            continue

        t["filename"] = new_filename
        t["relative_path"] = new_relative
        updated += 1
        changes_report.append({
            "title": title,
            "old_filename": old_filename,
            "new_filename": new_filename,
        })

    # Write reports
    with open(ROOT / "metadata_filename_updates.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "old_filename", "new_filename"])
        writer.writeheader()
        for row in changes_report:
            writer.writerow(row)

    with open(ROOT / "metadata_filename_ambiguous.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "old_filename", "candidates"])
        writer.writeheader()
        for row in ambiguous_report:
            writer.writerow(row)

    with open(ROOT / "metadata_filename_missing.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "old_filename"])
        writer.writeheader()
        for row in missing_report:
            writer.writerow(row)

    # Backup and write metadata unless dry-run
    if args.dry_run:
        print("\nDRY-RUN: Skipping write of music_collection_metadata.json")
    else:
        backup = backup_metadata(METADATA_PATH)
        print(f"Backup written to: {backup}")
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("\nSummary:")
    print(f"  Processed: {processed} (limit={args.limit or 'all'})")
    print(f"  Updated:   {updated}")
    print(f"  Unchanged: {unchanged}")
    print(f"  Ambiguous: {ambiguous}")
    print(f"  Missing:   {missing}")
    if ambiguous:
        print("  See metadata_filename_ambiguous.csv for ambiguous matches")
    if missing:
        print("  See metadata_filename_missing.csv for titles with no file match")
    if updated:
        print("  See metadata_filename_updates.csv for applied changes")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)

