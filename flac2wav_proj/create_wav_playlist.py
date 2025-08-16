#!/usr/bin/env python3

import pyrekordbox
import json
import os
from pathlib import Path

def create_wav_playlist():
    """Create a WAV playlist mirroring the first ALLDJ Stems playlist"""
    
    # Load the FLAC to WAV mapping
    print("Loading FLAC to WAV mapping...")
    with open('flac_to_wav_mapping.json', 'r') as f:
        flac_to_wav_mapping = json.load(f)
    
    print(f"Loaded {len(flac_to_wav_mapping)} FLAC to WAV mappings")
    
    # Initialize Rekordbox database
    print("Connecting to Rekordbox database...")
    db = pyrekordbox.Rekordbox6Database()
    playlists = db.get_playlist()
    
    # Find the first ALLDJ Stems playlist with tracks (nostalgic-hit vocals)
    target_playlist = None
    for playlist in playlists:
        if (playlist.Name == "nostalgic-hit" and 
            playlist.Songs and 
            len(playlist.Songs) > 0):
            
            # Build full path to check if it's the vocals one
            path_parts = [playlist.Name]
            current = playlist
            while current.Parent:
                current = current.Parent
                path_parts.insert(0, current.Name)
            full_path = " > ".join(path_parts)
            
            if "ALLDJ Stems" in full_path and "Vocals" in full_path:
                target_playlist = playlist
                print(f"Found target playlist: {full_path}")
                print(f"Songs in playlist: {len(playlist.Songs)}")
                break
    
    if not target_playlist:
        print("Could not find the target ALLDJ Stems nostalgic-hit vocals playlist")
        return
    
    # Analyze the tracks and map to WAV
    print("\nAnalyzing tracks and mapping to WAV...")
    
    mapped_tracks = []
    unmapped_tracks = []
    
    for i, song in enumerate(target_playlist.Songs):
        content = song.Content
        
        # Check available attributes for the first track
        if i == 0:
            print(f"Available attributes: {[attr for attr in dir(content) if not attr.startswith('_')]}")
        
        # Try different possible path attributes
        track_path = None
        for path_attr in ['FilePath', 'FolderPath', 'Path', 'Location', 'FileLocation']:
            if hasattr(content, path_attr):
                track_path = getattr(content, path_attr)
                if track_path:
                    break
        
        print(f"Processing track {i+1}/{len(target_playlist.Songs)}: {content.Title} - {content.Artist.Name if content.Artist else 'Unknown'}")
        print(f"  Original path: {track_path}")
        
        # Try to find mapping
        if track_path in flac_to_wav_mapping:
            wav_path = flac_to_wav_mapping[track_path]
            print(f"  ✓ Mapped to WAV: {wav_path}")
            
            # Check if WAV file exists
            if os.path.exists(wav_path):
                print(f"  ✓ WAV file exists")
                mapped_tracks.append({
                    'title': content.Title,
                    'artist': content.Artist.Name if content.Artist else 'Unknown',
                    'original_flac_path': track_path,
                    'wav_path': wav_path
                })
            else:
                print(f"  ✗ WAV file not found at: {wav_path}")
                unmapped_tracks.append({
                    'title': content.Title,
                    'artist': content.Artist.Name if content.Artist else 'Unknown',
                    'original_flac_path': track_path,
                    'reason': 'WAV file not found'
                })
        else:
            print(f"  ✗ No mapping found")
            unmapped_tracks.append({
                'title': content.Title,
                'artist': content.Artist.Name if content.Artist else 'Unknown',
                'original_flac_path': track_path,
                'reason': 'No mapping found'
            })
    
    print(f"\n=== MAPPING RESULTS ===")
    print(f"Successfully mapped: {len(mapped_tracks)} tracks")
    print(f"Unmapped tracks: {len(unmapped_tracks)} tracks")
    
    # Save results
    result = {
        'source_playlist': {
            'name': target_playlist.Name,
            'full_path': full_path,
            'total_tracks': len(target_playlist.Songs)
        },
        'mapping_stats': {
            'mapped': len(mapped_tracks),
            'unmapped': len(unmapped_tracks)
        },
        'mapped_tracks': mapped_tracks,
        'unmapped_tracks': unmapped_tracks
    }
    
    with open('wav_playlist_mapping_result.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nSaved mapping results to 'wav_playlist_mapping_result.json'")
    
    if mapped_tracks:
        print(f"\n=== FIRST 5 SUCCESSFULLY MAPPED TRACKS ===")
        for i, track in enumerate(mapped_tracks[:5]):
            print(f"{i+1}. {track['title']} - {track['artist']}")
            print(f"   WAV: {track['wav_path']}")
    
    # Now create the actual Rekordbox playlist
    if mapped_tracks:
        print(f"\n=== CREATING REKORDBOX WAV PLAYLIST ===")
        create_rekordbox_wav_playlist(db, mapped_tracks, target_playlist.Name, full_path)
    
    return result

def create_rekordbox_wav_playlist(db, mapped_tracks, original_name, original_path):
    """Create a new Rekordbox playlist with WAV files"""
    
    print(f"Creating WAV playlist for: {original_name}")
    print(f"Original path: {original_path}")
    
    # For now, let's just save the playlist structure that we want to create
    # The actual creation of playlists in Rekordbox via pyrekordbox might be complex
    
    # Define the target WAV playlist structure
    wav_playlist_structure = {
        'root_folder': 'WAV',
        'subfolders': [
            'ALLDJ Stems',
            'Dopamine Source (what triggers the feeling)', 
            'Vocals'
        ],
        'playlist_name': original_name,
        'tracks': [{'path': track['wav_path'], 'title': track['title'], 'artist': track['artist']} for track in mapped_tracks]
    }
    
    # Save the structure for manual creation or future automation
    with open('wav_playlist_structure.json', 'w') as f:
        json.dump(wav_playlist_structure, f, indent=2)
    
    print(f"Saved WAV playlist structure to 'wav_playlist_structure.json'")
    print(f"This contains {len(mapped_tracks)} tracks ready for import")
    
    # Create an M3U playlist file for easy import
    create_m3u_playlist(mapped_tracks, f"WAV_{original_name}.m3u")

def create_m3u_playlist(tracks, filename):
    """Create an M3U playlist file"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for track in tracks:
            f.write(f"#EXTINF:-1,{track['artist']} - {track['title']}\n")
            f.write(f"{track['wav_path']}\n")
    
    print(f"Created M3U playlist: {filename}")
    print(f"You can import this into Rekordbox or use it with other DJ software")

if __name__ == "__main__":
    result = create_wav_playlist()