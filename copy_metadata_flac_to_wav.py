#!/usr/bin/env python3

"""
Copy metadata from FLAC files to corresponding WAV files
"""

import os
import sys
import re
import unicodedata
from pathlib import Path
import argparse

def normalize_title(text: str) -> str:
    """Normalize a title/filename for robust matching."""
    if not text:
        return ""

    # Remove extension if present
    text = Path(text).stem

    # Unicode normalize and strip diacritics
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    lowered = text.lower()

    # Drop AppleDouble prefix if present
    if lowered.startswith("._"):
        lowered = lowered[2:]

    # Remove leading numeric index patterns
    lowered = re.sub(r"^[\s\-_.]*\d{1,3}([\-_]\d{1,3})?[\s\-_.]*", "", lowered)

    # Remove stem designation parts
    lowered = re.sub(r"\((?:vocals?|instrumentals?)\)", "", lowered)
    lowered = re.sub(r"\b(?:vocals?|instrumentals?|no_vocals|music|instru)\b", "", lowered)

    # Replace separators with spaces
    lowered = re.sub(r"[\-_]+", " ", lowered)

    # Normalize &/and, remove common noise words and bracketed descriptors
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"\[(.*?)\]|\{(.*?)\}", " ", lowered)
    # Remove common release descriptors
    lowered = re.sub(r"\b(remaster(?:ed)?|mono|stereo|version|edit|mix|remix|live|radio|extended)\b", " ", lowered)
    # Remove feat/featuring credits
    lowered = re.sub(r"\b(feat\.?|featuring)\b.*$", " ", lowered)

    # Collapse punctuation to spaces
    lowered = re.sub(r"[\.,:;!\?\"'`/\\]+", " ", lowered)

    # Collapse whitespace
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered

def copy_metadata_with_mutagen(flac_file: Path, wav_file: Path) -> bool:
    """Copy metadata from FLAC to WAV using mutagen"""
    try:
        from mutagen.flac import FLAC
        from mutagen.wave import WAVE
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TYER, TCON, COMM, TRCK
        
        # Read FLAC metadata
        flac_audio = FLAC(str(flac_file))
        if not flac_audio:
            return False
        
        # Read or create WAV file with ID3 tags
        try:
            wav_audio = WAVE(str(wav_file))
            if wav_audio.tags is None:
                wav_audio.add_tags()
        except Exception:
            # If WAVE doesn't work, try creating ID3 tags directly
            wav_audio = ID3()
            wav_audio.load(str(wav_file))
        
        # Copy basic metadata
        metadata_copied = []
        
        # Title
        if 'title' in flac_audio:
            wav_audio.tags.add(TIT2(encoding=3, text=flac_audio['title'][0]))
            metadata_copied.append('Title')
        
        # Artist
        if 'artist' in flac_audio:
            wav_audio.tags.add(TPE1(encoding=3, text=flac_audio['artist'][0]))
            metadata_copied.append('Artist')
        
        # Album
        if 'album' in flac_audio:
            wav_audio.tags.add(TALB(encoding=3, text=flac_audio['album'][0]))
            metadata_copied.append('Album')
        
        # Album Artist
        if 'albumartist' in flac_audio:
            wav_audio.tags.add(TPE2(encoding=3, text=flac_audio['albumartist'][0]))
            metadata_copied.append('Album Artist')
        
        # Year/Date
        if 'date' in flac_audio:
            wav_audio.tags.add(TYER(encoding=3, text=flac_audio['date'][0]))
            metadata_copied.append('Year')
        elif 'year' in flac_audio:
            wav_audio.tags.add(TYER(encoding=3, text=flac_audio['year'][0]))
            metadata_copied.append('Year')
        
        # Genre
        if 'genre' in flac_audio:
            wav_audio.tags.add(TCON(encoding=3, text=flac_audio['genre'][0]))
            metadata_copied.append('Genre')
        
        # Track number
        if 'tracknumber' in flac_audio:
            wav_audio.tags.add(TRCK(encoding=3, text=flac_audio['tracknumber'][0]))
            metadata_copied.append('Track Number')
        
        # Comments (preserve any existing comments and add original)
        comments = []
        if 'comment' in flac_audio:
            comments.append(flac_audio['comment'][0])
        
        if comments:
            wav_audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=' | '.join(comments)))
            metadata_copied.append('Comments')
        
        # Copy album art if present
        if flac_audio.pictures:
            try:
                from mutagen.id3 import APIC
                picture = flac_audio.pictures[0]
                wav_audio.tags.add(APIC(
                    encoding=3,
                    mime=picture.mime,
                    type=picture.type,
                    desc='Cover',
                    data=picture.data
                ))
                metadata_copied.append('Album Art')
            except Exception as e:
                print(f"    Warning: Could not copy album art: {e}")
        
        # Save the changes
        wav_audio.save()
        
        print(f"    ✓ Copied: {', '.join(metadata_copied)}")
        return True
        
    except ImportError:
        print(f"    ⚠️  mutagen not installed. Install with: pip install mutagen")
        return False
    except Exception as e:
        print(f"    ✗ Error copying metadata: {e}")
        return False

def build_flac_index(flac_directories):
    """Build an index of FLAC files for fast matching"""
    print("Building FLAC file index...")
    flac_index = {}
    total_flacs = 0
    
    for flac_dir in flac_directories:
        if not flac_dir.exists():
            print(f"  ⚠️  FLAC directory not found: {flac_dir}")
            continue
            
        print(f"  Indexing: {flac_dir}")
        flac_files = list(flac_dir.glob("**/*.flac"))
        
        for flac_file in flac_files:
            if flac_file.name.startswith("._"):
                continue
            
            normalized = normalize_title(flac_file.stem)
            if normalized:
                flac_index[normalized] = flac_file
                total_flacs += 1
    
    print(f"✓ Indexed {total_flacs} FLAC files")
    return flac_index

def process_wav_directory(wav_dir: Path, flac_index: dict, dry_run: bool = False):
    """Process all WAV files in a directory"""
    if not wav_dir.exists():
        print(f"⚠️  WAV directory not found: {wav_dir}")
        return 0, 0
    
    print(f"\nProcessing WAV directory: {wav_dir}")
    wav_files = list(wav_dir.glob("**/*.wav"))
    wav_files = [f for f in wav_files if not f.name.startswith("._")]
    
    print(f"Found {len(wav_files)} WAV files")
    
    matched = 0
    metadata_copied = 0
    
    for i, wav_file in enumerate(wav_files, 1):
        if i % 50 == 0 or i == len(wav_files):
            print(f"  Progress: {i}/{len(wav_files)}")
        
        # Normalize WAV filename for matching
        normalized = normalize_title(wav_file.stem)
        
        if normalized in flac_index:
            flac_file = flac_index[normalized]
            matched += 1
            
            if dry_run:
                print(f"  [DRY RUN] Would copy metadata:")
                print(f"    From: {flac_file.name}")
                print(f"    To:   {wav_file.name}")
            else:
                print(f"  Copying metadata: {wav_file.name}")
                print(f"    From FLAC: {flac_file.name}")
                if copy_metadata_with_mutagen(flac_file, wav_file):
                    metadata_copied += 1
        else:
            if i <= 5:  # Show first few unmatched for debugging
                print(f"  ✗ No match for: {wav_file.name} (normalized: '{normalized}')")
    
    print(f"\\n📊 Results for {wav_dir.name}:")
    print(f"   WAV files processed: {len(wav_files)}")
    print(f"   FLAC matches found: {matched}")
    print(f"   Metadata copied: {metadata_copied if not dry_run else 'N/A (dry run)'}")
    print(f"   Match rate: {matched/len(wav_files)*100:.1f}%" if wav_files else "0%")
    
    return matched, metadata_copied if not dry_run else matched

def main():
    parser = argparse.ArgumentParser(description="Copy metadata from FLAC to WAV files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--test", action="store_true", help="Process only first 10 files from each directory")
    
    args = parser.parse_args()
    
    print("🎵 FLAC to WAV Metadata Copier")
    print("=" * 40)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    
    if args.test:
        print("🧪 TEST MODE - Processing only first 10 files per directory")
    
    # Define directories
    wav_directories = [
        Path("/Volumes/T7 Shield/3000AD/wav_alldj_stem_separated"),
        Path("/Volumes/T7 Shield/3000AD/wav_og_separated_v2"), 
        Path("/Volumes/T7 Shield/3000AD/wav_liked_songs")
    ]
    
    flac_directories = [
        Path("/Volumes/T7 Shield/3000AD/og_separated_v2"),
        Path("/Volumes/T7 Shield/3000AD/alldj_stem_separated"),
        Path("/Volumes/T7 Shield/3000AD/flac_liked_songs"),
        Path("/Volumes/T7 Shield/3000AD/all_og_lossless"),
        Path("/Users/ethansarif-kattan/Music/ALLDJ/flac")  # Local FLAC folder
    ]
    
    # Check directories exist
    print("\\nChecking directories...")
    for wav_dir in wav_directories:
        status = "✓" if wav_dir.exists() else "✗"
        print(f"  {status} WAV: {wav_dir}")
    
    for flac_dir in flac_directories:
        status = "✓" if flac_dir.exists() else "✗"
        print(f"  {status} FLAC: {flac_dir}")
    
    # Build FLAC index
    flac_index = build_flac_index(flac_directories)
    
    if not flac_index:
        print("❌ No FLAC files found to copy metadata from")
        return 1
    
    # Process each WAV directory
    total_matched = 0
    total_copied = 0
    
    for wav_dir in wav_directories:
        if wav_dir.exists():
            # Limit files for testing
            if args.test:
                wav_files = list(wav_dir.glob("**/*.wav"))[:10]
                print(f"\\n[TEST MODE] Processing first {len(wav_files)} files from {wav_dir.name}")
            
            matched, copied = process_wav_directory(wav_dir, flac_index, args.dry_run)
            total_matched += matched
            total_copied += copied
    
    print(f"\\n🎉 Overall Summary:")
    print(f"   Total FLAC files indexed: {len(flac_index)}")
    print(f"   Total WAV-FLAC matches: {total_matched}")
    print(f"   Total metadata copied: {total_copied if not args.dry_run else 'N/A (dry run)'}")
    
    if args.dry_run:
        print(f"\\n💡 Run without --dry-run to actually copy metadata")
    elif total_copied > 0:
        print(f"\\n✅ Metadata copying complete!")
        print(f"   WAV files now have proper titles, artists, albums, and artwork")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
