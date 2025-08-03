#!/usr/bin/env python3
"""
Clean assigned_tags and confidence fields from music metadata JSON
"""

import json
from pathlib import Path

def clean_metadata(json_file_path):
    """Remove all AI-generated fields from tracks."""
    
    print(f"Loading {json_file_path}...")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Found {len(data['tracks'])} tracks")
    
    # AI-generated fields to remove
    ai_fields = [
        'assigned_tags',
        'confidence', 
        'research_notes',
        'ai_processed',
        'processing_id',
        'processed_date',
        'ai_model',
        'estimated_bpm',
        'estimated_key',
        'energy_level',
        'danceability',
        'mood'
    ]
    
    tracks_cleaned = 0
    fields_removed_total = 0
    
    for track in data['tracks']:
        track_had_ai_fields = False
        fields_removed_this_track = 0
        
        for field in ai_fields:
            if field in track:
                # For assigned_tags, just empty it instead of removing completely
                if field == 'assigned_tags':
                    if track[field]:  # Only count if it had content
                        track[field] = []
                        fields_removed_this_track += 1
                        track_had_ai_fields = True
                else:
                    del track[field]
                    fields_removed_this_track += 1
                    track_had_ai_fields = True
        
        if track_had_ai_fields:
            tracks_cleaned += 1
            fields_removed_total += fields_removed_this_track
            print(f"Cleaned {fields_removed_this_track} fields from: {track.get('artist', 'Unknown')} - {track.get('title', 'Unknown')}")
    
    print(f"\nCleaning complete:")
    print(f"- Cleaned {tracks_cleaned} tracks")
    print(f"- Removed {fields_removed_total} AI-generated fields total")
    
    # Save the cleaned data
    print(f"\nSaving cleaned data to {json_file_path}...")
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("Done!")

if __name__ == "__main__":
    json_file = "/Users/ethansarif-kattan/Music/ALLDJ/music_collection_metadata.json"
    clean_metadata(json_file)
