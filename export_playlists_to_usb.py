#!/usr/bin/env python3

"""
Export Rekordbox-style playlists to a DJ USB drive (resumable)

This script builds playlists from your tag taxonomy (same structure used by
your existing generators), copies referenced tracks to a destination USB drive,
and writes M3U8 files that reference the copied tracks. It is resilient: it
persists progress to the USB so it can resume after interruptions.

Usage examples:
  python export_playlists_to_usb.py \
    --usb-path "/Volumes/REKORDBOX" \
    --base-path "/Users/ethansarif-kattan/Music/ALLDJ" \
    --metadata "/Users/ethansarif-kattan/Music/ALLDJ/music_collection_metadata.json" \
    --limit 5 --dry-run

  python export_playlists_to_usb.py \
    --usb-path "/Volumes/REKORDBOX" \
    --base-path "/Users/ethansarif-kattan/Music/ALLDJ" \
    --metadata "/Users/ethansarif-kattan/Music/ALLDJ/music_collection_metadata.json"
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ------------------------ Data models ------------------------

@dataclass
class TrackMetadata:
    relative_path: str
    filename: str
    artist: Optional[str] = None
    title: Optional[str] = None
    assigned_tags: Optional[List[str]] = None
    duration_seconds: Optional[float] = None


@dataclass
class PlaylistDef:
    category_folder: str
    display_name: str
    tags_all: List[str]
    is_combo: bool = False


# ------------------------ Helpers ------------------------

def humanize_tag(tag: str) -> str:
    return " ".join(w.capitalize() for w in tag.split("-"))


def sanitize_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in name)
    safe = "_".join(s for s in safe.split())
    return safe[:200] if len(safe) > 200 else safe


def atomic_write_text(dest: Path, content: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(dest.parent), encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)


def copy_file_atomic(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(dest.parent)) as tmp:
        with src.open("rb") as fsrc:
            shutil.copyfileobj(fsrc, tmp)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)


def file_same_size(src: Path, dest: Path) -> bool:
    try:
        return src.stat().st_size == dest.stat().st_size
    except FileNotFoundError:
        return False


# ------------------------ Taxonomy and playlists ------------------------

def build_playlist_definitions() -> List[PlaylistDef]:
    """Mirrors tag-analyzer-ts/src/generate-m3u8-playlists.ts categories and combos."""
    categories: Dict[str, List[str]] = {
        "01_DOPAMINE_SOURCE": [
            "nostalgic-hit",
            "euphoric-melody",
            "emotional-depth",
            "textural-beauty",
            "rhythmic-hypnosis",
            "harmonic-surprise",
            "vocal-magic",
            "psychedelic-journey",
            "sophisticated-groove",
        ],
        "02_MIXING_ROLE": [
            "rhythmic-foundation",
            "melodic-overlay",
            "bridge-element",
            "texture-add",
            "anchor-track",
            "wildcard",
            "transition-tool",
            "emotional-crescendo",
            "palate-cleanser",
        ],
        "03_DANCEABILITY": [
            "instant-dancefloor",
            "crowd-pleaser",
            "peak-time",
            "body-mover",
            "head-nodder",
            "non-danceable-standalone",
        ],
        "04_ENERGY_DYNAMICS": [
            "energetic",
            "energy-injector",
            "energy-sustainer",
            "energy-shifter",
            "instant-impact",
            "slow-burn",
            "lifts-mood",
        ],
        "05_GENRES": [
            "electronic-dance",
            "electronic-experimental",
            "electronic-ambient",
            "rock-psychedelic",
            "rock-indie",
            "rock-classic",
            "hip-hop-conscious",
            "hip-hop-experimental",
            "pop-sophisticated",
            "world-fusion",
        ],
        "06_ERA_BRIDGING": [
            "timeless-classic",
            "contemporary-classic",
            "retro-modern",
            "genre-crossover",
            "cultural-moment",
            "generational-bridge",
        ],
        "07_GENERATIONAL_APPEAL": [
            "gen-z-nostalgia",
            "millennial-comfort",
            "gen-x-wisdom",
            "boomer-classic",
            "indie-cred",
            "mainstream-crossover",
        ],
        "08_MIXING_COMPATIBILITY": [
            "layer-friendly",
            "breakdown-rich",
            "loop-gold",
            "mashup-ready",
            "beatmatched-friendly",
            "smooth-transitions",
        ],
        "09_SET_POSITIONING": [
            "set-opener",
            "warm-up",
            "peak-time",
            "emotional-peak",
            "comedown",
            "sunrise",
            "interlude",
        ],
        "10_PSYCHEDELIC_CONSCIOUSNESS": [
            "mind-expanding",
            "reality-bending",
            "time-dilation",
            "dream-logic",
            "color-synesthesia",
            "meditation-inducer",
        ],
        "11_PERSONAL_TAGS": [
            "deep",
            "dopamine",
            "funny",
            "drum-bass-layer",
        ],
    }

    combos: List[Tuple[str, List[str]]] = [
        ("Dancefloor_Classics", ["instant-dancefloor", "timeless-classic"]),
        ("Energetic_Crowd_Pleasers", ["energetic", "crowd-pleaser"]),
        ("Euphoric_Peak_Time", ["euphoric-melody", "peak-time"]),
        ("Nostalgic_Dancefloor", ["nostalgic-hit", "instant-dancefloor"]),
        ("Psychedelic_Journey_Layers", ["psychedelic-journey", "layer-friendly"]),
        ("Electronic_Dance_Foundations", ["electronic-dance", "rhythmic-foundation"]),
        ("Vocal_Magic_Overlays", ["vocal-magic", "melodic-overlay"]),
        ("Contemporary_Layer_Friendly", ["contemporary-classic", "layer-friendly"]),
        ("Deep_Emotional_Journeys", ["deep", "emotional-depth"]),
        ("Dopamine_Energy_Hits", ["dopamine", "energetic"]),
    ]

    defs: List[PlaylistDef] = []
    for category, tags in categories.items():
        for tag in tags:
            defs.append(
                PlaylistDef(
                    category_folder=category,
                    display_name=humanize_tag(tag),
                    tags_all=[tag],
                    is_combo=False,
                )
            )

    for combo_name, tags in combos:
        defs.append(
            PlaylistDef(
                category_folder="12_COMBO_PLAYLISTS",
                display_name=combo_name.replace("_", " "),
                tags_all=tags,
                is_combo=True,
            )
        )

    return defs


# ------------------------ Exporter ------------------------

class ResumableExporter:
    def __init__(
        self,
        base_path: Path,
        usb_root: Path,
        metadata_path: Path,
        dry_run: bool = False,
        limit: Optional[int] = None,
    ) -> None:
        self.base_path = base_path
        self.usb_root = usb_root
        self.metadata_path = metadata_path
        self.dry_run = dry_run
        self.limit = limit

        self.music_dest_root = self.usb_root / "ALLDJ_MUSIC"
        self.playlists_root = self.usb_root / "PLAYLISTS"
        self.state_path = self.usb_root / ".alldj_export_state.json"

        self.tracks: List[TrackMetadata] = []
        self.state: Dict = {
            "version": 1,
            "base_path": str(self.base_path),
            "files": {},  # src_abs -> dest_abs
            "playlists": {},  # category/display_name -> status dict
        }

    def load_metadata(self) -> None:
        with self.metadata_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.tracks = [
            TrackMetadata(
                relative_path=t.get("relative_path", t.get("filename")),
                filename=t.get("filename"),
                artist=t.get("artist"),
                title=t.get("title"),
                assigned_tags=t.get("assigned_tags") or [],
                duration_seconds=t.get("duration_seconds"),
            )
            for t in data.get("tracks", [])
        ]

    def load_state(self) -> None:
        if self.state_path.exists():
            try:
                with self.state_path.open("r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                # If state is corrupt, start fresh but do not delete the file yet
                pass

    def save_state(self) -> None:
        if self.dry_run:
            return
        atomic_write_text(self.state_path, json.dumps(self.state, indent=2))

    def ensure_dirs(self) -> None:
        self.music_dest_root.mkdir(parents=True, exist_ok=True)
        self.playlists_root.mkdir(parents=True, exist_ok=True)

    def filter_tracks_by_tags_all(self, tags_all: List[str]) -> List[TrackMetadata]:
        wanted = []
        tags_all_set = set(tags_all)
        for tr in self.tracks:
            track_tags = set(tr.assigned_tags or [])
            if tags_all_set.issubset(track_tags):
                wanted.append(tr)
        return wanted

    def copy_track_if_needed(self, src_abs: Path) -> Optional[Path]:
        # Preserve original relative structure under ALLDJ_MUSIC
        try:
            rel = src_abs.relative_to(self.base_path)
        except ValueError:
            # Fallback: use filename only to avoid copying outside tree
            rel = Path(src_abs.name)

        dest_abs = self.music_dest_root / rel

        if dest_abs.exists() and file_same_size(src_abs, dest_abs):
            # Already copied
            return dest_abs

        if not src_abs.exists():
            return None

        if self.dry_run:
            return dest_abs

        copy_file_atomic(src_abs, dest_abs)
        return dest_abs

    def build_m3u8(self, playlist_name: str, tracks_abs: List[Tuple[TrackMetadata, Path]]) -> str:
        lines: List[str] = ["#EXTM3U", f"# {playlist_name} - Exported for Rekordbox"]
        for tr, dest_abs in tracks_abs:
            duration = int(round(tr.duration_seconds or 0))
            artist = tr.artist or "Unknown Artist"
            title = tr.title or tr.filename
            lines.append(f"#EXTINF:{duration},{artist} - {title}")
            lines.append(str(dest_abs))
        return "\n".join(lines) + "\n"

    def export(self) -> None:
        print("🎛️  Resumable Playlist Exporter → USB")
        print("====================================")

        if not self.usb_root.exists():
            print(f"Error: USB path not found: {self.usb_root}")
            sys.exit(1)

        self.ensure_dirs()
        self.load_state()
        self.load_metadata()

        playlist_defs = build_playlist_definitions()
        if self.limit is not None and self.limit > 0:
            playlist_defs = playlist_defs[: self.limit]

        total = len(playlist_defs)
        print(f"Found {total} playlists to export")

        for idx, pdef in enumerate(playlist_defs, 1):
            key = f"{pdef.category_folder}/{pdef.display_name}"
            status = self.state.get("playlists", {}).get(key, {})
            if status.get("completed"):
                print(f"[{idx}/{total}] {key} — already completed, skipping")
                continue

            print(f"[{idx}/{total}] Exporting: {key}")
            tracks = self.filter_tracks_by_tags_all(pdef.tags_all)
            if not tracks:
                print("  ⚠️  No tracks match; skipping")
                self.state.setdefault("playlists", {})[key] = {
                    "completed": True,
                    "tracks_total": 0,
                    "tracks_exported": 0,
                }
                self.save_state()
                continue

            # Copy tracks
            exported: List[Tuple[TrackMetadata, Path]] = []
            copied_count = 0

            for tr in tracks:
                src_abs = (self.base_path / tr.relative_path).resolve()
                dest_abs = self.copy_track_if_needed(src_abs)
                if dest_abs is None:
                    print(f"  Missing source, skipping: {src_abs}")
                    continue
                exported.append((tr, dest_abs))
                copied_count += 1

                # Persist partial progress occasionally
                if not self.dry_run and copied_count % 25 == 0:
                    self.state.setdefault("playlists", {})[key] = {
                        "completed": False,
                        "tracks_total": len(tracks),
                        "tracks_exported": copied_count,
                    }
                    self.save_state()

            # Write M3U8
            pl_dir = self.playlists_root / pdef.category_folder
            pl_dir.mkdir(parents=True, exist_ok=True)
            m3u8_name = sanitize_filename(pdef.display_name) + ".m3u8"
            m3u8_path = pl_dir / m3u8_name
            m3u8_content = self.build_m3u8(pdef.display_name, exported)
            if self.dry_run:
                print(f"  [DRY RUN] Would write: {m3u8_path}")
            else:
                atomic_write_text(m3u8_path, m3u8_content)

            # Mark complete
            self.state.setdefault("playlists", {})[key] = {
                "completed": True,
                "tracks_total": len(tracks),
                "tracks_exported": copied_count,
                "m3u8_path": str(m3u8_path),
            }
            self.save_state()

        print("\n✅ Export complete (or up-to-date).")
        print(f"Playlists at: {self.playlists_root}")
        print(f"Music at: {self.music_dest_root}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export playlists to a USB drive with resumable progress",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--usb-path",
        required=True,
        help="Path to mounted USB drive (e.g., /Volumes/REKORDBOX)",
    )
    parser.add_argument(
        "--base-path",
        default="/Users/ethansarif-kattan/Music/ALLDJ",
        help="Root of your ALLDJ collection",
    )
    parser.add_argument(
        "--metadata",
        default="/Users/ethansarif-kattan/Music/ALLDJ/music_collection_metadata.json",
        help="Path to music_collection_metadata.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If > 0, only process the first N playlists (useful for spot checks)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and log actions without copying or writing files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exporter = ResumableExporter(
        base_path=Path(args.base_path).resolve(),
        usb_root=Path(args.usb_path).resolve(),
        metadata_path=Path(args.metadata).resolve(),
        dry_run=bool(args.dry_run),
        limit=(args.limit if args.limit and args.limit > 0 else None),
    )
    try:
        exporter.export()
    except KeyboardInterrupt:
        print("\nInterrupted. Progress is saved; you can re-run to resume.")
        sys.exit(1)


if __name__ == "__main__":
    main()


