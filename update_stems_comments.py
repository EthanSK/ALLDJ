#!/usr/bin/env python3

import argparse
import csv
import difflib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from mutagen.flac import FLAC
except Exception as e:
    print("Error: mutagen is required. Install with: pip install mutagen")
    sys.exit(1)


def flush_print(msg: str):
    print(msg)
    sys.stdout.flush()


def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Remove extension
    text = Path(text).stem
    # NFKD normalize and strip diacritics
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    s = text.lower()
    # Strip leading numeric indices like "01-02 " or "12_", but PRESERVE
    # purely numeric titles (e.g., "212") used as actual song names
    import re
    s_no_ws = s.strip()
    if not re.fullmatch(r"[\d\s\-_.()]+", s_no_ws) or not re.fullmatch(r"\d+[\s\-_.()]*", s_no_ws):
        s = re.sub(r"^[\s\-_.]*\d{1,3}([\-_]\d{1,3})?[\s\-_.]*", "", s)
    # Remove stem indicators
    s = re.sub(r"\((?:vocals?|instrumentals?)\)", "", s)
    s = re.sub(r"\b(?:vocals?|instrumentals?|no_vocals|music|instru)\b", "", s)
    # Canonicalize symbols, strip brackets
    s = s.replace("&", " and ")
    s = re.sub(r"\[(.*?)\]|\{(.*?)\}", " ", s)
    # Remove common release descriptors and feat credits
    s = re.sub(r"\b(remaster(?:ed)?|mono|stereo|version|edit|mix|remix|live|radio|extended|deluxe|explicit|clean|dirty|album|single|digital)\b", " ", s)
    # Remove plain years (e.g., 1997, 2010) and year in parentheses/brackets
    s = re.sub(r"\((?:19|20)\d{2}\)", " ", s)
    s = re.sub(r"\b(?:19|20)\d{2}\b", " ", s)
    s = re.sub(r"\b(feat\.?|featuring)\b.*$", " ", s)
    # Turn separators into spaces
    s = re.sub(r"[\-_]+", " ", s)
    s = re.sub(r"[\.,:;!\?\"'`/\\]+", " ", s)
    # Collapse spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(text: str) -> set:
    s = normalize_text(text)
    if not s:
        return set()
    tokens = set(s.split())
    stop = {
        "the", "a", "an", "and", "to", "of", "in", "on", "for", "with", "at", "by",
        "is", "it", "its", "this", "that", "my", "your", "our", "we", "you", "me",
    }
    return {t for t in tokens if t not in stop}


def best_key_match(query: str, keys: List[str]) -> Tuple[str | None, float]:
    q_norm = normalize_text(query)
    if not q_norm or not keys:
        return None, 0.0

    q_tokens = tokenize(q_norm)
    best_k = None
    best_score = 0.0
    for k in keys:
        # quick boost for prefix/substring
        prefix_boost = 0.0
        if k.startswith(q_norm) or q_norm.startswith(k):
            prefix_boost += 0.1
        if k in q_norm or q_norm in k:
            prefix_boost += 0.05

        k_tokens = tokenize(k)
        if not k_tokens and not q_tokens:
            overlap = 1.0
        else:
            inter = len(q_tokens & k_tokens)
            union = len(q_tokens | k_tokens) or 1
            overlap = inter / union

        char_sim = difflib.SequenceMatcher(None, q_norm, k).ratio()
        score = 0.6 * overlap + 0.4 * char_sim + prefix_boost
        if score > best_score:
            best_k, best_score = k, score
    return best_k, best_score


def load_metadata(metadata_path: Path) -> Dict[str, List[str]]:
    """Return index: normalized_title -> assigned_tags list (by title)."""
    with open(metadata_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    index: Dict[str, List[str]] = {}
    for tr in data.get("tracks", []):
        title = tr.get("title") or tr.get("Title") or ""
        norm = normalize_text(title)
        tags = tr.get("assigned_tags", []) or []
        # If duplicate title appears, prefer the one with more tags
        if norm:
            prev = index.get(norm)
            if prev is None or len(tags) > len(prev):
                index[norm] = list(tags)
    return index


def load_metadata_by_filename(metadata_path: Path) -> Dict[str, List[str]]:
    """Return index: lowercase filename base (no extension) -> assigned_tags list.

    Uses the metadata 'filename' field if available; falls back to last path component
    of 'relative_path'. The key is lowercased and does not include the extension.
    """
    with open(metadata_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    index: Dict[str, List[str]] = {}
    for tr in data.get("tracks", []):
        filename = (tr.get("filename") or "").strip()
        if not filename:
            rel = (tr.get("relative_path") or "").strip()
            filename = Path(rel).name if rel else ""
        if not filename:
            continue
        base = Path(filename).stem.lower()
        tags = tr.get("assigned_tags", []) or []
        prev = index.get(base)
        if prev is None or len(tags) > len(prev):
            index[base] = list(tags)
    return index


def write_flac_tags(path: Path, tags: List[str], commit: bool) -> bool:
    try:
        audio = FLAC(str(path))
    except Exception as e:
        flush_print(f"    ✗ Failed reading FLAC: {path.name}: {e}")
        return False

    # Prepare fields
    tag_str = ", ".join(tags)
    # Use custom field and also append into comment
    audio["ALLDJ_TAGS"] = tags
    comments = list(audio.get("comment", []))
    # Deduplicate if same marker already exists
    marker = f"ALLDJ_TAGS: {tag_str}"
    if marker not in comments:
        comments.append(marker)
    audio["comment"] = comments

    if commit:
        try:
            audio.save()
            return True
        except Exception as e:
            flush_print(f"    ✗ Failed saving FLAC: {path.name}: {e}")
            return False
    else:
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Copy ALLDJ assigned tags into stem FLAC comments (ALLDJ_TAGS + comment) using fuzzy title matching"
    )
    parser.add_argument(
        "--metadata",
        default="music_collection_metadata.json",
        help="Path to music_collection_metadata.json"
    )
    parser.add_argument(
        "--stems-dir",
        default="/Volumes/T7 Shield/3000AD/alldj_stem_separated",
        help="Path to root of stem-separated audio files"
    )
    parser.add_argument(
        "--flac-dir",
        default=str((Path(__file__).resolve().parent / "flac")),
        help="Path to directory containing original FLAC files (for fallback title lookup)"
    )
    parser.add_argument(
        "--prefer-prefix",
        action="store_true",
        help="Prefer matching stems by filename prefix against metadata filename before fuzzy title matching"
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write tags to FLAC files (default: dry-run)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a line for each processed file"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.72,
        help="Minimum fuzzy match score to accept a mapping (default: 0.72)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N stem files (0 = all)"
    )
    parser.add_argument(
        "--from-unmatched",
        type=str,
        default="",
        help="Path to stems_tag_unmatched.csv to process only those entries"
    )
    parser.add_argument(
        "--accept-suggested",
        action="store_true",
        help="When using --from-unmatched, accept the CSV's suggested match_key regardless of threshold (optionally gated by --min-suggested-score)"
    )
    parser.add_argument(
        "--min-suggested-score",
        type=float,
        default=0.55,
        help="Minimum score from CSV to accept suggested match_key when --accept-suggested is set (default: 0.55)"
    )

    args = parser.parse_args()

    stems_root = Path(args.stems_dir)
    if not stems_root.exists():
        flush_print(f"Error: stems directory not found: {stems_root}")
        sys.exit(1)

    metadata_path = Path(args.metadata)
    if not metadata_path.exists():
        flush_print(f"Error: metadata file not found: {metadata_path}")
        sys.exit(1)

    flush_print(f"Loading metadata: {metadata_path}")
    meta_index = load_metadata(metadata_path)
    keys = list(meta_index.keys())
    fname_index = load_metadata_by_filename(metadata_path)
    fname_keys = list(fname_index.keys())
    flush_print(f"✓ Loaded metadata with {len(keys)} titles and {len(fname_keys)} filenames")

    # Iterate stems
    stem_files: List[Path]
    suggested_map: Dict[Path, Tuple[str, float]] = {}
    if args.from_unmatched:
        # Read CSV and restrict to those file paths that exist
        try:
            rows = []
            with open(args.from_unmatched, "r", encoding="utf-8") as f:
                import csv as _csv
                reader = _csv.DictReader(f)
                for r in reader:
                    sp = r.get("stem_path") or ""
                    score_str = r.get("score") or "0"
                    try:
                        score_val = float(score_str)
                    except Exception:
                        score_val = 0.0
                    if sp:
                        p = Path(sp)
                        if p.exists() and p.is_file() and p.suffix.lower() == ".flac" and not p.name.startswith("._"):
                            rows.append((p, score_val))
                            mk = (r.get("match_key") or "").strip()
                            suggested_map[p] = (mk, score_val)
            # Sort by score desc, then keep only paths
            rows.sort(key=lambda t: t[1], reverse=True)
            stem_files = [p for p, _ in rows]
        except Exception as e:
            flush_print(f"Error reading --from-unmatched CSV: {e}")
            stem_files = []
    else:
        stem_files = [p for p in stems_root.rglob("*.flac") if p.is_file() and not p.name.startswith("._")]
    flush_print(f"Scanning stems in: {stems_root}")
    flush_print(f"Found {len(stem_files)} FLAC stems")

    updated = 0
    skipped = 0
    unmatched_rows = []
    changes_rows = []

    total_to_process = len(stem_files) if args.limit <= 0 else min(args.limit, len(stem_files))
    # Preserve prepared ordering (e.g., from-unmatched sorted by score)
    flac_dir = Path(args.flac_dir)
    for idx, p in enumerate(stem_files[:total_to_process]):
        stem_base = p.stem.lower()
        # Strip common stem suffix markers like _ (Vocals) / _ (Instrumental)
        stripped = stem_base
        for marker in ["_(vocals)", "_(instrumental)", " (vocals)", " (instrumental)"]:
            if stripped.endswith(marker):
                stripped = stripped[: -len(marker)]
                break

        key = None
        score = 0.0

        # 1) Prefer prefix match against metadata filenames if requested
        if args.prefer_prefix:
            # Find any filename base that equals or is a prefix of the stem name
            # e.g., '212' matches '212_(Instrumental)'
            match_key = None
            if stripped in fname_index:
                match_key = stripped
            else:
                # try startswith by checking candidates where stem starts with candidate
                for fk in fname_keys:
                    if stripped.startswith(fk):
                        match_key = fk
                        break
            if match_key:
                key = match_key
                score = 1.0

        # 2) If no filename prefix match, try fuzzy match by title
        if key is None:
            base = normalize_text(p.name)
            key, score = best_key_match(base, keys)

        # 3) Fallback: If still no tags and prefix was intended, try reading original FLAC's Title tag
        inferred_tags: List[str] = []
        if args.prefer_prefix:
            # Try to find an original FLAC matching the stripped stem base
            candidate = flac_dir / f"{stripped}.flac"
            if candidate.exists():
                try:
                    orig = FLAC(str(candidate))
                    title_vals = list(orig.get("title", []))
                    title_val = title_vals[0] if title_vals else ""
                    norm_title = normalize_text(title_val)
                    if norm_title:
                        inferred_tags = meta_index.get(norm_title, [])
                        if inferred_tags and not key:
                            key = norm_title
                            score = 0.95
                except Exception:
                    pass
        # Prefer suggested match from CSV if provided and allowed
        if args.from_unmatched and p in suggested_map:
            suggested_key, suggested_score = suggested_map.get(p, ("", 0.0))
            if suggested_key:
                if args.accept_suggested:
                    if suggested_score >= args.min_suggested_score:
                        key, score = suggested_key, suggested_score
                elif suggested_score >= args.threshold:
                    key, score = suggested_key, suggested_score
        if key and (score >= args.threshold or args.prefer_prefix):
            # Resolve tags from indices
            tags = meta_index.get(key, []) or fname_index.get(key, []) or inferred_tags
            if tags:
                ok = write_flac_tags(p, tags, args.commit)
                if ok:
                    updated += 1
                    changes_rows.append({
                        "stem_path": str(p),
                        "match_key": key,
                        "score": f"{score:.3f}",
                        "tags": "; ".join(tags),
                    })
                    if args.verbose:
                        flush_print(f"[{idx+1}/{len(stem_files)}] ✓ {p.name} <- {key} ({score:.3f})")
                else:
                    skipped += 1
                    if args.verbose:
                        flush_print(f"[{idx+1}/{len(stem_files)}] ✗ {p.name} (save failed)")
            else:
                skipped += 1
                unmatched_rows.append({
                    "stem_path": str(p),
                    "reason": "matched title has no tags",
                    "match_key": key,
                    "score": f"{score:.3f}",
                })
                if args.verbose:
                    flush_print(f"[{idx+1}/{len(stem_files)}] - {p.name} (no tags for match)")
        else:
            skipped += 1
            unmatched_rows.append({
                "stem_path": str(p),
                "reason": "no sufficient match",
                "match_key": key or "",
                "score": f"{(score or 0):.3f}",
            })
            if args.verbose:
                flush_print(f"[{idx+1}/{len(stem_files)}] - {p.name} (no match)")

        # Frequent flush so progress shows up in real time
        if not args.verbose and (idx + 1) % 50 == 0:
            flush_print(f"Processed {idx+1}/{total_to_process}...")

    # Write reports
    try:
        with open("stems_tag_update_report.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["stem_path", "match_key", "score", "tags"])
            writer.writeheader()
            for row in changes_rows:
                writer.writerow(row)
        with open("stems_tag_unmatched.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["stem_path", "reason", "match_key", "score"])
            writer.writeheader()
            for row in unmatched_rows:
                writer.writerow(row)
    except Exception as e:
        flush_print(f"Warning: could not write CSV reports: {e}")

    flush_print("\nSummary:")
    flush_print(f"  Processed:            {total_to_process} (limit={args.limit or 'all'})")
    flush_print(f"  Updated (tags copied): {updated}")
    flush_print(f"  Skipped/Unmatched:    {skipped}")
    flush_print(f"  Mode: {'COMMIT' if args.commit else 'DRY-RUN'}")
    flush_print("  Reports: stems_tag_update_report.csv, stems_tag_unmatched.csv")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        flush_print("\nCancelled")
        sys.exit(1)

