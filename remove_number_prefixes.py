#!/usr/bin/env python3
import os
import re
from pathlib import Path

def remove_number_prefixes():
    """Remove number_ prefixes from filenames in the stem directory"""
    directory = Path("/Volumes/T7 Shield/3000AD/alldj_stem_separated")
    
    if not directory.exists():
        print(f"Directory does not exist: {directory}")
        return
    
    pattern = re.compile(r'^\d+_')
    renamed_count = 0
    
    print(f"Processing files in: {directory}")
    
    for file_path in directory.iterdir():
        if file_path.is_file():
            old_name = file_path.name
            
            # Check if filename starts with number_
            if pattern.match(old_name):
                # Remove the number_ prefix
                new_name = pattern.sub('', old_name)
                new_path = file_path.parent / new_name
                
                # Rename the file
                try:
                    file_path.rename(new_path)
                    print(f"Renamed: {old_name} -> {new_name}")
                    renamed_count += 1
                except Exception as e:
                    print(f"Error renaming {old_name}: {e}")
    
    print(f"\nCompleted! Renamed {renamed_count} files.")

if __name__ == "__main__":
    remove_number_prefixes()