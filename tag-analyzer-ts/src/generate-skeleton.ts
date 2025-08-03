#!/usr/bin/env node

import * as fs from "fs";
import * as path from "path";
import { MusicMetadata, Track } from "./types";

function scanFlacDirectory(): Track[] {
  const flacDir = path.resolve(__dirname, "../../flac");
  const tracks: Track[] = [];
  
  if (!fs.existsSync(flacDir)) {
    console.error(`❌ FLAC directory not found: ${flacDir}`);
    console.error("Make sure you have a 'flac' directory with your music files.");
    process.exit(1);
  }

  console.log(`📁 Scanning FLAC directory: ${flacDir}`);
  
  const files = fs.readdirSync(flacDir);
  const flacFiles = files.filter(file => file.toLowerCase().endsWith('.flac'));
  
  console.log(`🎵 Found ${flacFiles.length} FLAC files`);
  
  for (const filename of flacFiles.sort()) {
    const filePath = path.join(flacDir, filename);
    const stats = fs.statSync(filePath);
    
    // Create basic track structure with empty/unknown fields
    const track: Track = {
      relative_path: `flac/${filename}`,
      filename: filename,
      file_size_mb: Math.round((stats.size / 1024 / 1024) * 100) / 100,
      duration_seconds: 0, // Will be populated by actual metadata extraction
      duration_formatted: "Unknown",
      artist: "Unknown",
      title: "Unknown", 
      album: "Unknown",
      albumartist: "Unknown",
      date: "Unknown",
      genre: "Unknown",
      track: "Unknown",
      tracktotal: "Unknown",
      disc: "Unknown",
      disctotal: "Unknown",
      composer: "Unknown",
      label: "Unknown",
      isrc: "Unknown",
      bpm: "Unknown",
      key: "Unknown",
      comment: "Unknown",
      grouping: "Unknown",
      bitrate: 0,
      sample_rate: 0,
      channels: 0,
      bits_per_sample: 0,
      assigned_tags: [], // Empty - ready for AI tagging
      tag_confidence: undefined,
      research_notes: undefined
    };
    
    tracks.push(track);
  }
  
  return tracks;
}

function generateSkeletonMetadata(): MusicMetadata {
  const tracks = scanFlacDirectory();
  const now = new Date();
  
  const metadata: MusicMetadata = {
    metadata: {
      total_files: tracks.length,
      successful_extractions: 0, // Will be updated when metadata is extracted
      failed_extractions: 0,
      scan_date: now.toISOString().split('T')[0],
      scan_time: now.toTimeString().split(' ')[0],
      directory_path: path.resolve(__dirname, "../../flac"),
      collection_duration_hours: 0, // Will be calculated later
      total_size_gb: Math.round(tracks.reduce((sum, track) => sum + track.file_size_mb, 0) / 1024 * 100) / 100
    },
    tracks: tracks
  };
  
  return metadata;
}

function main() {
  console.log("🔄 Generating fresh music collection metadata skeleton...\n");
  
  const outputPath = path.resolve(__dirname, "../music_collection_metadata.json");
  
  // Check if file exists and warn user
  if (fs.existsSync(outputPath)) {
    console.log("⚠️  WARNING: This will overwrite your existing metadata file!");
    console.log(`📁 File: ${outputPath}`);
    console.log("🏷️  All existing tags and metadata will be lost.");
    console.log("\nPress Ctrl+C now to cancel, or any key to continue...");
    
    // In a real CLI, you'd wait for user input, but for batch usage we'll add a flag
    const forceOverwrite = process.argv.includes('--force') || process.argv.includes('-f');
    
    if (!forceOverwrite) {
      console.log("\n❌ Cancelled. Use --force flag to overwrite without confirmation.");
      process.exit(1);
    }
  }
  
  try {
    const skeleton = generateSkeletonMetadata();
    
    // Write the skeleton JSON
    fs.writeFileSync(outputPath, JSON.stringify(skeleton, null, 2));
    
    console.log("✅ Successfully generated skeleton metadata!");
    console.log(`📁 File: ${outputPath}`);
    console.log(`🎵 Tracks: ${skeleton.tracks.length}`);
    console.log(`💾 Size: ${skeleton.metadata.total_size_gb} GB`);
    console.log("\n🚀 Ready for AI tagging! Run:");
    console.log(`   npm run analyze:batch 10`);
    
  } catch (error) {
    console.error("❌ Error generating skeleton:", error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}