#!/usr/bin/env python3

"""
Test WAV import with metadata copied from FLAC files
"""

import json
import sys
import re
import unicodedata
from pathlib import Path
from pyrekordbox import Rekordbox6Database

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

def find_matching_flac_metadata(wav_filename: str, metadata: dict):
    """Find metadata for the corresponding FLAC file"""
    wav_normalized = normalize_title(wav_filename)
    
    # Search through all tracks in metadata
    for track in metadata.get('tracks', []):
        # Try matching by title
        title = track.get('title', '') or track.get('Title', '')
        if title:
            title_normalized = normalize_title(title)
            if title_normalized and title_normalized == wav_normalized:
                return track
        
        # Try matching by filename
        filename = track.get('filename', '')
        if filename:
            filename_normalized = normalize_title(filename)
            if filename_normalized and filename_normalized == wav_normalized:
                return track
    
    return None

def apply_metadata_to_wav(db, wav_content, flac_metadata):
    """Apply FLAC metadata to WAV content in Rekordbox"""
    try:
        # Get the content ID to update
        content_id = getattr(wav_content, 'ID', None)
        if not content_id:
            print("    Warning: No content ID found")
            return False
        
        # Prepare metadata fields
        updates = {}
        
        # Basic metadata
        if flac_metadata.get('title') or flac_metadata.get('Title'):
            updates['Title'] = flac_metadata.get('title') or flac_metadata.get('Title')
        
        if flac_metadata.get('artist') or flac_metadata.get('Artist'):
            updates['Artist'] = flac_metadata.get('artist') or flac_metadata.get('Artist')
        
        if flac_metadata.get('album') or flac_metadata.get('Album'):
            updates['Album'] = flac_metadata.get('album') or flac_metadata.get('Album')
        
        if flac_metadata.get('albumartist') or flac_metadata.get('AlbumArtist'):
            updates['AlbumArtist'] = flac_metadata.get('albumartist') or flac_metadata.get('AlbumArtist')
        
        if flac_metadata.get('genre') or flac_metadata.get('Genre'):
            updates['Genre'] = flac_metadata.get('genre') or flac_metadata.get('Genre')
        
        if flac_metadata.get('year') or flac_metadata.get('Year'):
            updates['Year'] = flac_metadata.get('year') or flac_metadata.get('Year')
        
        # Track number
        if flac_metadata.get('tracknumber') or flac_metadata.get('TrackNumber'):
            track_num = flac_metadata.get('tracknumber') or flac_metadata.get('TrackNumber')
            if isinstance(track_num, str) and '/' in track_num:
                track_num = track_num.split('/')[0]
            try:
                updates['TrackNumber'] = int(track_num)
            except (ValueError, TypeError):
                pass
        
        # Comments with tags
        comments = []
        if flac_metadata.get('assigned_tags'):
            tags = flac_metadata.get('assigned_tags', [])
            comments.append(f"Tags: {', '.join(tags)}")
        
        if flac_metadata.get('comment') or flac_metadata.get('Comment'):
            original_comment = flac_metadata.get('comment') or flac_metadata.get('Comment')
            comments.append(original_comment)
        
        if comments:
            updates['Comments'] = ' | '.join(comments)
        
        # Apply updates
        if updates:
            print(f"    → Updating metadata: {list(updates.keys())}")
            
            # Update the content using database update method
            try:
                # For pyrekordbox, we need to update through the database
                content_table = db.get_content_table()
                content_id = getattr(wav_content, 'ID', None)
                
                if content_id:
                    # Build update query
                    update_data = {}
                    for field, value in updates.items():
                        if field and value:
                            update_data[field] = str(value)[:255]  # Limit length
                            print(f"      {field}: {value}")
                    
                    if update_data:
                        # Update using SQL
                        query = content_table.update().where(content_table.c.ID == content_id).values(**update_data)
                        db.engine.execute(query)
                        print(f"    ✓ Updated {len(update_data)} metadata fields")
                    
                else:
                    print(f"    Warning: No content ID found for update")
                
            except Exception as e:
                print(f"    Warning: Database update failed: {e}")
                # Fallback to direct attribute setting
                for field, value in updates.items():
                    try:
                        setattr(wav_content, field, value)
                        print(f"      {field}: {value} (fallback)")
                    except Exception as e2:
                        print(f"      Warning: Could not set {field}: {e2}")
            
            return True
        else:
            print("    → No metadata to apply")
            return False
            
    except Exception as e:
        print(f"    Error applying metadata: {e}")
        return False

def main():
    # Load metadata
    print("Loading FLAC metadata...")
    with open("music_collection_metadata.json", 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    print(f"✓ Loaded metadata for {len(metadata.get('tracks', []))} tracks")
    
    # WAV directory
    wav_dir = Path("/Volumes/T7 Shield/3000AD/wav_liked_songs")
    
    if not wav_dir.exists():
        print(f"Error: WAV directory not found: {wav_dir}")
        return 1
    
    # Get first 3 WAV files
    wav_files = list(wav_dir.glob("*.wav"))[:3]
    wav_files = [f for f in wav_files if not f.name.startswith("._")][:3]
    
    if not wav_files:
        print("No WAV files found!")
        return 1
    
    print(f"\nTesting {len(wav_files)} WAV files with metadata:")
    for i, f in enumerate(wav_files, 1):
        print(f"  {i}. {f.name}")
    
    # Connect to Rekordbox
    try:
        db_paths = [
            Path.home() / "Library/Pioneer/rekordbox7",
            Path.home() / "Library/Pioneer/rekordbox6", 
            Path.home() / "Library/Pioneer/rekordbox"
        ]
        
        db_path = None
        for path in db_paths:
            if path.exists():
                db_path = path
                break
        
        if not db_path:
            print("Error: Could not find Rekordbox database")
            return 1
        
        print(f"\nConnecting to Rekordbox at: {db_path}")
        db = Rekordbox6Database(db_dir=str(db_path))
        print("✓ Connected successfully")
        
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return 1
    
    # Create test playlist
    test_playlist_name = "WAV With Metadata Test"
    
    # Delete existing test playlist if it exists
    existing = db.get_playlist(Name=test_playlist_name).first()
    if existing:
        db.delete_playlist(existing)
        print(f"✓ Deleted existing test playlist")
    
    # Create new test playlist
    playlist = db.create_playlist(test_playlist_name)
    print(f"✓ Created test playlist: {test_playlist_name}")
    
    # Process each WAV file
    successful_imports = 0
    
    for i, wav_file in enumerate(wav_files, 1):
        print(f"\nProcessing file {i}: {wav_file.name}")
        
        try:
            # Find matching FLAC metadata
            flac_metadata = find_matching_flac_metadata(wav_file.stem, metadata)
            if flac_metadata:
                print(f"  ✓ Found matching FLAC metadata")
                print(f"    Title: {flac_metadata.get('title', 'N/A')}")
                print(f"    Artist: {flac_metadata.get('artist', 'N/A')}")
                print(f"    Album: {flac_metadata.get('album', 'N/A')}")
                tags = flac_metadata.get('assigned_tags', [])
                print(f"    Tags: {len(tags)} tags")
            else:
                print(f"  ⚠️  No matching FLAC metadata found")
            
            # Add to Rekordbox or get existing
            absolute_path = wav_file.resolve()
            existing_content = db.get_content(FolderPath=str(absolute_path)).first()
            
            if existing_content:
                print(f"  ✓ File already in Rekordbox collection")
                content = existing_content
            else:
                print(f"  → Adding file to Rekordbox collection...")
                content = db.add_content(str(absolute_path))
                if content:
                    print(f"  ✓ Successfully added to collection")
                else:
                    print(f"  ✗ Failed to add to collection")
                    continue
            
            # Apply metadata if we found matching FLAC data
            if flac_metadata:
                metadata_applied = apply_metadata_to_wav(db, content, flac_metadata)
                if metadata_applied:
                    print(f"  ✓ Metadata applied successfully")
                else:
                    print(f"  ⚠️  Metadata application failed")
            
            # Add to playlist
            print(f"  → Adding to playlist...")
            db.add_to_playlist(playlist, content)
            print(f"  ✓ Successfully added to playlist")
            successful_imports += 1
            
        except Exception as e:
            print(f"  ✗ Error with file {wav_file.name}: {e}")
            continue
    
    print(f"\n📊 Results:")
    print(f"   Files processed: {len(wav_files)}")
    print(f"   Successfully imported: {successful_imports}")
    print(f"   Failed: {len(wav_files) - successful_imports}")
    
    if successful_imports > 0:
        print(f"\n→ Committing changes to database...")
        try:
            db.commit()
            print(f"✅ Changes committed! Check '{test_playlist_name}' playlist in Rekordbox")
            print(f"   The WAV files should now have proper titles, artists, albums, and tags in comments")
        except Exception as e:
            print(f"❌ Failed to commit changes: {e}")
    else:
        print(f"\n❌ No files were successfully imported")
    
    # Close database
    db.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
