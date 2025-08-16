#!/usr/bin/env python3

"""
Enhance the FLAC-WAV mapping to include local FLAC files from /Users/ethansarif-kattan/Music/ALLDJ/flac/
and try to find corresponding WAV files in the T7 Shield directories.
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a, b).ratio()

def find_best_match(local_flac_name, t7_wav_paths, threshold=0.7):
    """Find the best matching WAV file for a local FLAC file"""
    best_match = None
    best_score = 0
    
    # Clean up the local FLAC name - remove track numbers and extensions
    clean_local = local_flac_name.replace('.flac', '')
    # Remove common track number patterns
    import re
    clean_local = re.sub(r'^\d+-\d+\s+', '', clean_local)  # Remove "01-01 " patterns
    clean_local = re.sub(r'^\d+\.\s+', '', clean_local)     # Remove "1. " patterns
    clean_local = re.sub(r'^\d+\s+', '', clean_local)       # Remove "01 " patterns
    
    for wav_path in t7_wav_paths:
        wav_name = Path(wav_path).stem
        score = similarity(clean_local.lower(), wav_name.lower())
        if score > best_score and score >= threshold:
            best_score = score
            best_match = wav_path
    
    return best_match, best_score

def main():
    print("🔍 Creating enhanced FLAC-WAV mapping with local files")
    
    # Load existing complete mapping
    complete_mapping_file = "flac_wav_mapping_complete.json"
    if not Path(complete_mapping_file).exists():
        print(f"❌ {complete_mapping_file} not found - run fix_mapping_keep_all.py first")
        return 1
    
    with open(complete_mapping_file, 'r', encoding='utf-8') as f:
        existing_data = json.load(f)
    
    print(f"✅ Loaded {len(existing_data['mappings'])} existing mappings")
    
    # Get all local FLAC files
    local_flac_dir = Path("/Users/ethansarif-kattan/Music/ALLDJ/flac")
    if not local_flac_dir.exists():
        print(f"❌ Local FLAC directory not found: {local_flac_dir}")
        return 1
    
    local_flac_files = list(local_flac_dir.glob("*.flac"))
    print(f"📁 Found {len(local_flac_files)} local FLAC files")
    
    # Get all existing WAV paths from T7 Shield for matching
    existing_wav_paths = []
    for mapping in existing_data['mappings']:
        if mapping.get('wav_path') and mapping.get('wav_exists'):
            existing_wav_paths.append(mapping['wav_path'])
    
    print(f"🎵 Have {len(existing_wav_paths)} existing WAV files to match against")
    
    # Create enhanced mapping
    enhanced_mappings = existing_data['mappings'].copy()
    new_mappings = 0
    matched_mappings = 0
    
    for local_flac in local_flac_files:
        flac_path = str(local_flac)
        
        # Check if this local FLAC is already in the mapping
        already_exists = any(m.get('flac_path') == flac_path for m in enhanced_mappings)
        if already_exists:
            continue
        
        # Try to find a matching WAV file
        best_match, score = find_best_match(local_flac.name, existing_wav_paths, threshold=0.6)
        
        if best_match:
            enhanced_mappings.append({
                'flac_path': flac_path,
                'wav_path': best_match,
                'wav_exists': True,
                'match_score': round(score, 3),
                'match_type': 'local_to_t7'
            })
            matched_mappings += 1
            print(f"   ✅ {local_flac.name} → {Path(best_match).name} (score: {score:.3f})")
        else:
            # Add as unmapped
            enhanced_mappings.append({
                'flac_path': flac_path,
                'wav_path': None,
                'wav_exists': False,
                'match_type': 'local_unmapped'
            })
            new_mappings += 1
            print(f"   ⚠️  {local_flac.name} → No match found")
    
    # Create enhanced data structure
    enhanced_data = {
        'total_mappings': len(enhanced_mappings),
        'original_mappings': len(existing_data['mappings']),
        'local_matched': matched_mappings,
        'local_unmapped': new_mappings,
        'mappings': enhanced_mappings
    }
    
    # Save enhanced mapping
    enhanced_file = "flac_wav_mapping_enhanced.json"
    print(f"💾 Saving enhanced mapping to {enhanced_file}...")
    
    with open(enhanced_file, 'w', encoding='utf-8') as f:
        json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Enhanced mapping created!")
    print(f"📊 Results:")
    print(f"   Total mappings: {len(enhanced_mappings)}")
    print(f"   Original T7 mappings: {len(existing_data['mappings'])}")
    print(f"   Local FLAC matched to T7 WAV: {matched_mappings}")
    print(f"   Local FLAC unmapped: {new_mappings}")
    print(f"   Enhanced file: {enhanced_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())