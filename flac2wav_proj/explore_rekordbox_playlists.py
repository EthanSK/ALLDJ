#!/usr/bin/env python3

import pyrekordbox
import json
from pathlib import Path

def explore_rekordbox_playlists():
    """Explore Rekordbox database to find ALLDJ Stems playlists"""
    try:
        # Initialize the Rekordbox database
        db = pyrekordbox.Rekordbox6Database()
        
        # Get all playlists
        playlists = db.get_playlist()
        
        print("All playlists in Rekordbox database:")
        print("=" * 50)
        
        # Build playlist hierarchy to understand folder structure
        def build_playlist_path(playlist):
            """Build the full path of a playlist by traversing up the parent chain"""
            path_parts = [playlist.Name]
            current = playlist
            while current.Parent:
                current = current.Parent
                path_parts.insert(0, current.Name)
            return " > ".join(path_parts)
        
        # Look for ALLDJ Stems playlists
        alldj_stems_playlists = []
        
        print("Looking for ALLDJ Stems playlists with tracks...")
        for playlist in playlists:
            full_path = build_playlist_path(playlist)
            
            # Only focus on ALLDJ Stems playlists that have actual tracks
            if "ALLDJ Stems" in full_path and playlist.Songs and len(playlist.Songs) > 0:
                print(f"Found ALLDJ Stems playlist: {playlist.Name}")
                print(f"  Full Path: {full_path}")
                print(f"  Songs: {len(playlist.Songs)}")
                print("-" * 30)
                
                alldj_stems_playlists.append({
                    'name': playlist.Name,
                    'full_path': full_path,
                    'id': playlist.ID,
                    'is_folder': playlist.is_folder,
                    'is_playlist': playlist.is_playlist,
                    'song_count': len(playlist.Songs),
                    'playlist_obj': playlist
                })
        
        print(f"\nFound {len(alldj_stems_playlists)} ALLDJ Stems playlists:")
        for playlist in alldj_stems_playlists:
            print(f"  - {playlist['name']} (Path: {playlist['full_path']}) [Songs: {playlist['song_count']}]")
        
        # Focus on the first playlist for testing
        if alldj_stems_playlists:
            first_playlist = alldj_stems_playlists[0]
            print(f"\n=== Analyzing first playlist: {first_playlist['name']} ===")
            
            # Get tracks in this playlist using the Songs attribute
            playlist_obj = first_playlist['playlist_obj']
            
            print(f"Number of songs: {len(playlist_obj.Songs) if playlist_obj.Songs else 0}")
            
            playlist_data = {
                'playlist_info': {
                    'name': first_playlist['name'],
                    'path': first_playlist['path'],
                    'id': first_playlist['id']
                },
                'tracks': []
            }
            
            if playlist_obj.Songs:
                print("\nFirst 5 tracks in playlist:")
                for i, song in enumerate(playlist_obj.Songs[:5]):
                    content = song.Content
                    print(f"  {i+1}. {content.Title} - {content.Artist.Name if content.Artist else 'Unknown'}")
                    print(f"     File: {content.FilePath}")
                    print()
                
                # Save all track info
                for song in playlist_obj.Songs:
                    content = song.Content
                    playlist_data['tracks'].append({
                        'title': content.Title,
                        'artist': content.Artist.Name if content.Artist else 'Unknown',
                        'file_path': content.FilePath
                    })
            
            # Save to JSON file
            with open('first_alldj_stems_playlist.json', 'w') as f:
                json.dump(playlist_data, f, indent=2)
            
            print(f"\nSaved playlist data to 'first_alldj_stems_playlist.json'")
            
        else:
            print("No ALLDJ Stems playlists found!")
            
    except Exception as e:
        print(f"Error accessing Rekordbox database: {e}")
        print("Make sure Rekordbox is closed and the database is accessible.")

if __name__ == "__main__":
    explore_rekordbox_playlists()