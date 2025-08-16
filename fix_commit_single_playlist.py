#!/usr/bin/env python3

"""
Clean up the FLAC-WAV mapping file to only keep essential fields:
- flac_path
- wav_path 
- wav_exists

Remove all the irrelevant metadata bloat.
"""

import json
import sys
from pathlib import Path

def main():
    print("🧹 Cleaning up FLAC-WAV mapping file")
    
    mapping_file = "flac_wav_mapping.json"
    if not Path(mapping_file).exists():
        print(f"❌ {mapping_file} not found")
        return 1
    
    print(f"📋 Loading {mapping_file}...")
    with open(mapping_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    original_count = len(data.get('mappings', []))
    print(f"📊 Original mappings: {original_count}")
    
    # Clean up - keep only essential fields
    cleaned_mappings = []
    valid_mappings = 0
    
    for mapping in data.get('mappings', []):
        # Only keep mappings where WAV exists
        if mapping.get('wav_exists', False):
            cleaned_mapping = {
                'flac_path': mapping.get('flac_path'),
                'wav_path': mapping.get('wav_path'),
                'wav_exists': True
            }
            cleaned_mappings.append(cleaned_mapping)
            valid_mappings += 1
    
    # Create simplified structure
    cleaned_data = {
        'total_mappings': len(cleaned_mappings),
        'mappings': cleaned_mappings
    }
    
    # Save cleaned file
    cleaned_file = "flac_wav_mapping_clean.json"
    print(f"💾 Saving cleaned mapping to {cleaned_file}...")
    
    with open(cleaned_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Cleaned mapping file created!")
    print(f"📊 Results:")
    print(f"   Original mappings: {original_count}")
    print(f"   Valid WAV mappings: {valid_mappings}")
    print(f"   File size reduction: ~{((1 - Path(cleaned_file).stat().st_size / Path(mapping_file).stat().st_size) * 100):.1f}%")
    print(f"   Cleaned file: {cleaned_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
