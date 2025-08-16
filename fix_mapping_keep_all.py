#!/usr/bin/env python3

"""
Clean up the FLAC-WAV mapping file to only keep essential fields but KEEP ALL mappings,
not just the ones where WAV exists. User wants all 4300+ mappings available.
"""

import json
import sys
from pathlib import Path

def main():
    print("🧹 Cleaning up FLAC-WAV mapping file (keeping ALL mappings)")
    
    mapping_file = "flac_wav_mapping.json"
    if not Path(mapping_file).exists():
        print(f"❌ {mapping_file} not found")
        return 1
    
    print(f"📋 Loading {mapping_file}...")
    with open(mapping_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    original_count = len(data.get('mappings', []))
    print(f"📊 Original mappings: {original_count}")
    
    # Clean up - keep only essential fields for ALL mappings
    cleaned_mappings = []
    
    for mapping in data.get('mappings', []):
        cleaned_mapping = {
            'flac_path': mapping.get('flac_path'),
            'wav_path': mapping.get('wav_path'),
            'wav_exists': mapping.get('wav_exists', False)
        }
        cleaned_mappings.append(cleaned_mapping)
    
    # Create simplified structure
    cleaned_data = {
        'total_mappings': len(cleaned_mappings),
        'mappings': cleaned_mappings
    }
    
    # Save cleaned file
    cleaned_file = "flac_wav_mapping_complete.json"
    print(f"💾 Saving complete cleaned mapping to {cleaned_file}...")
    
    with open(cleaned_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    # Count existing vs non-existing
    existing_count = sum(1 for m in cleaned_mappings if m.get('wav_exists', False))
    
    print(f"✅ Complete mapping file created!")
    print(f"📊 Results:")
    print(f"   Total mappings: {len(cleaned_mappings)}")
    print(f"   WAV files exist: {existing_count}")
    print(f"   WAV files missing: {len(cleaned_mappings) - existing_count}")
    print(f"   File size reduction: ~{((1 - Path(cleaned_file).stat().st_size / Path(mapping_file).stat().st_size) * 100):.1f}%")
    print(f"   Complete file: {cleaned_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())