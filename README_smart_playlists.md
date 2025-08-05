# Smart Playlist Creator for Rekordbox

This Python script automatically creates smart playlists in Rekordbox DJ software by directly modifying its database. It reads your music metadata and creates one smart playlist for each unique tag found in the COMMENT fields of your tracks.

## Features

- ✅ **Automatic Smart Playlist Creation**: Creates one smart playlist per tag
- ✅ **Direct Database Modification**: Uses pyrekordbox to safely modify Rekordbox's SQLite database
- ✅ **Intelligent Organization**: Groups all tag playlists in a "Smart Playlists by Tag" folder
- ✅ **Safe Operation**: Creates automatic backups before making changes
- ✅ **Dry Run Mode**: Preview what will be created without making changes
- ✅ **Duplicate Prevention**: Skips playlists that already exist
- ✅ **Error Handling**: Robust error handling with detailed feedback

## How It Works

The script uses the `pyrekordbox` library to:

1. **Connect** to Rekordbox's encrypted SQLite database (`master.db`)
2. **Read** your music metadata from the JSON file created by your FLAC tagger
3. **Extract** all unique tags from track COMMENT fields
4. **Create** smart playlists with criteria: "Comments contains 'tag-name'"
5. **Organize** all tag playlists in a dedicated folder
6. **Commit** changes safely to the database

Each smart playlist automatically updates when you add new tracks with matching tags.

## Requirements

- **macOS** (tested on macOS)
- **Rekordbox 6.x** (the script works with Rekordbox 6's encrypted database)
- **Python 3.7+**
- **pyrekordbox library**
- **Your music files** must have tags in their COMMENT fields (created by your FLAC tagger)

## Installation

1. **Install Python dependencies:**

   ```bash
   pip install -r requirements_smart_playlists.txt
   ```

2. **Ensure Rekordbox is completely closed** before running the script

3. **Make sure you have your metadata file** (`music_collection_metadata.json`) with track tags

## Usage

### Basic Usage

```bash
# Preview what will be created (recommended first run)
python create_smart_playlists.py --dry-run

# Create the smart playlists
python create_smart_playlists.py
```

### Advanced Options

```bash
# Use a custom metadata file
python create_smart_playlists.py --metadata my_custom_metadata.json

# Skip creating a backup (not recommended)
python create_smart_playlists.py --no-backup

# Dry run with custom metadata file
python create_smart_playlists.py --dry-run --metadata my_metadata.json
```

### Command Line Options

- `--metadata FILE`: Path to metadata JSON file (default: `music_collection_metadata.json`)
- `--dry-run`: Show what would be created without making changes
- `--no-backup`: Skip creating a backup of the Rekordbox database

## Example Output

```
🎵 Smart Playlist Creator for Rekordbox
=====================================

Loading metadata from: music_collection_metadata.json
✓ Loaded metadata for 1108 tracks

Extracting unique tags...
✓ Found 151 unique tags
Preview tags: euphoric-melody, instant-dancefloor, nostalgic-hit, summer-vibes, underground-gem
... and 146 more

Creating backup: /Users/username/Library/Pioneer/rekordbox_backup_20250805_142301
✓ Backup created successfully

Connecting to Rekordbox database...
✓ Connected successfully

Creating smart playlists...
[1/151] Processing tag: 'euphoric-melody'
  ✓ Created smart playlist: 'Tag: euphoric-melody' (ID: 2147483647)
[2/151] Processing tag: 'instant-dancefloor'
  ✓ Created smart playlist: 'Tag: instant-dancefloor' (ID: 2147483646)
...

Organizing playlists in folder...
✓ Created folder: 'Smart Playlists by Tag'
✓ Moved 151 playlists into folder

Committing changes to database...
✓ Changes committed successfully

📊 Summary:
   Total tags: 151
   Created: 151
   Skipped (existing): 0
   Failed: 0

✅ Smart playlist creation complete!
   Open Rekordbox to see your new smart playlists
```

## How Smart Playlists Work

Each created smart playlist has the following criteria:

- **Property**: Comments
- **Operator**: Contains
- **Value**: The specific tag name (e.g., "euphoric-melody")

This means:

- When you add new tracks with matching tags in their COMMENT field, they automatically appear in the corresponding smart playlist
- The playlists update in real-time as you import new music
- You can modify the criteria later in Rekordbox if needed

## Database Structure

The script works with Rekordbox 6's database structure:

- **Database Location**: `~/Library/Pioneer/rekordbox6/master.db`
- **Encryption**: Uses pyrekordbox to handle SQLCipher encryption
- **Tables Modified**:
  - `djmdPlaylist`: Stores playlist information
  - `masterPlaylists6.xml`: Playlist metadata file

## Safety Features

### Automatic Backups

- Creates timestamped backup of entire Rekordbox database directory
- Backup location: `~/Library/Pioneer/rekordbox_backup_YYYYMMDD_HHMMSS/`
- Can be disabled with `--no-backup` (not recommended)

### Safe Database Operations

- Uses transactions for atomic operations
- Properly handles database locking
- Graceful error handling and cleanup
- Warns if Rekordbox is running

### Duplicate Prevention

- Checks for existing playlists before creating
- Skips playlists that already exist
- Reports summary of created/skipped/failed playlists

## Troubleshooting

### "Failed to connect to Rekordbox database"

- **Solution**: Make sure Rekordbox is completely closed
- **Check**: Rekordbox 6 is installed and has been used at least once

### "Metadata file not found"

- **Solution**: Run your FLAC tagger first to create the metadata file
- **Check**: File path is correct and contains track data with `assigned_tags`

### "No tags found in metadata"

- **Solution**: Ensure your tracks have tags in their COMMENT fields
- **Check**: Your FLAC tagger has processed the files and populated tags

### "Permission denied" errors

- **Solution**: Run with appropriate permissions
- **Check**: Rekordbox database directory is accessible

### Key extraction fails (Rekordbox 6.6.5+)

- **Issue**: Pioneer obfuscated key extraction in newer versions
- **Solution**: Use `frida` method as mentioned in pyrekordbox documentation
- **Alternative**: Use an older Rekordbox version if possible

## File Structure

After running the script, your Rekordbox will have:

```
Root
└── Smart Playlists by Tag/
    ├── Tag: euphoric-melody
    ├── Tag: instant-dancefloor
    ├── Tag: nostalgic-hit
    ├── Tag: summer-vibes
    └── ... (one for each unique tag)
```

## Integration with Your FLAC Tagger

This script is designed to work with your existing FLAC tagger (`flac-tagger.ts`):

1. **FLAC Tagger**: Adds tags to COMMENT fields and creates metadata JSON
2. **Smart Playlist Creator**: Reads metadata and creates Rekordbox smart playlists
3. **Result**: Automatic playlist organization based on your intelligent tagging system

## Technical Details

### Dependencies

- **pyrekordbox**: Python library for Rekordbox database access
- **Standard library**: json, os, shutil, sys, pathlib, datetime, argparse

### Database Access

- Uses SQLCipher to decrypt Rekordbox database
- Handles 28-bit ID generation for playlists
- Properly updates USN (Update Sequence Numbers)
- Maintains referential integrity

### Smart List XML Format

The script generates XML conditions like:

```xml
<NODE Id="-123456789" LogicalOperator="1" AutomaticUpdate="0">
    <CONDITION PropertyName="comments" Operator="8" ValueUnit=""
               ValueLeft="euphoric-melody" ValueRight=""/>
</NODE>
```

## Limitations

- **Rekordbox Version**: Designed for Rekordbox 6.x
- **Platform**: Tested on macOS (should work on Windows/Linux with path adjustments)
- **Database Encryption**: Requires pyrekordbox to handle SQLCipher encryption
- **Concurrent Access**: Rekordbox must be closed during script execution

## Future Enhancements

Potential improvements:

- Support for more complex smart playlist criteria
- Batch operations for multiple metadata files
- Integration with other DJ software
- GUI interface for easier use
- Real-time synchronization

## Support

If you encounter issues:

1. **Check Requirements**: Ensure all dependencies are installed
2. **Verify Setup**: Run with `--dry-run` first to test
3. **Check Logs**: Review error messages for specific issues
4. **Backup**: Always keep backups of your Rekordbox database

## License

This script is provided as-is for educational and personal use. Always backup your Rekordbox database before running any database modification scripts.
