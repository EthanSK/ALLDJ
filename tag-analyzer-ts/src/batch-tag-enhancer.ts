#!/usr/bin/env node

import dotenv from "dotenv";
dotenv.config();

import { MusicTagAnalyzer } from "./tag-analyzer";
import { Track, MusicMetadata, AnalysisResult } from "./types";
import * as fs from "fs";
import * as path from "path";

export class BatchTagEnhancer extends MusicTagAnalyzer {
  private chunkSize: number;

  constructor(apiKey?: string, chunkSize: number = 25) {
    super(apiKey);
    this.chunkSize = chunkSize;
  }

  /**
   * Get tracks that already have some tags but could benefit from additional ones
   */
  private getTaggedTracks(): Track[] {
    const metadata = this.loadMusicMetadata();
    return metadata.tracks.filter(track => {
      const assignedTags = track.assigned_tags || [];
      return assignedTags.length > 0 && assignedTags.length < 15; // Has tags but room for more
    });
  }

  /**
   * Get tracks with no tags at all
   */
  private getUntaggedTracks(): Track[] {
    const metadata = this.loadMusicMetadata();
    return metadata.tracks.filter(track => {
      const assignedTags = track.assigned_tags || [];
      return assignedTags.length === 0;
    });
  }

  /**
   * Merge new tags with existing tags, avoiding duplicates
   */
  private mergeTagsWithExisting(existingTags: string[], newTags: string[]): string[] {
    const merged = [...existingTags];
    
    for (const newTag of newTags) {
      if (!merged.includes(newTag)) {
        merged.push(newTag);
      }
    }
    
    return merged;
  }

  /**
   * Enhanced update method that merges tags instead of replacing them
   */
  updateTrackTagsEnhanced(filename: string, analysisResult: AnalysisResult, mergeMode: boolean = true): boolean {
    try {
      const metadata = this.loadMusicMetadata();

      for (const track of metadata.tracks) {
        if (
          track.filename === filename ||
          track.relative_path.endsWith(filename)
        ) {
          const existingTags = track.assigned_tags || [];
          
          if (mergeMode && existingTags.length > 0) {
            // Merge new tags with existing ones
            track.assigned_tags = this.mergeTagsWithExisting(existingTags, analysisResult.tags);
            console.log(`🔄 Merged ${analysisResult.tags.length} new tags with ${existingTags.length} existing tags`);
            console.log(`   New tags added: ${analysisResult.tags.filter(tag => !existingTags.includes(tag)).join(", ")}`);
          } else {
            // Replace all tags (for untagged tracks)
            track.assigned_tags = analysisResult.tags;
          }

          // Update confidence and research notes
          track.tag_confidence = analysisResult.confidence;
          track.research_notes = analysisResult.research_notes;

          const metadataPath = path.resolve(
            __dirname,
            "../../music_collection_metadata.json"
          );
          fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
          return true;
        }
      }

      console.log(`Track '${filename}' not found in metadata`);
      return false;
    } catch (error) {
      console.error("Error updating metadata:", error);
      return false;
    }
  }

  /**
   * Process a chunk of tracks
   */
  async processTrackChunk(tracks: Track[], chunkIndex: number, mergeMode: boolean = true): Promise<{
    successful: number;
    errors: number;
    processed: number;
  }> {
    let successful = 0;
    let errors = 0;
    let processed = 0;

    console.log(`\n🎵 Processing chunk ${chunkIndex + 1} (${tracks.length} tracks)`);
    console.log("=".repeat(50));

    for (let i = 0; i < tracks.length; i++) {
      const track = tracks[i];
      console.log(`\n🔄 Processing track ${i + 1}/${tracks.length} in chunk ${chunkIndex + 1}`);
      console.log(`   ${track.artist} - ${track.title}`);
      
      if (track.assigned_tags && track.assigned_tags.length > 0) {
        console.log(`   Current tags (${track.assigned_tags.length}): ${track.assigned_tags.join(", ")}`);
      }

      try {
        const analysisResult = await this.analyzeTrackTags(track);
        
        if (analysisResult.tags.length === 0) {
          console.error(`❌ No tags generated for: ${track.artist} - ${track.title}`);
          errors++;
        } else {
          const updateSuccess = this.updateTrackTagsEnhanced(track.filename, analysisResult, mergeMode);
          
          if (updateSuccess) {
            console.log(`✅ Successfully processed: ${track.artist} - ${track.title}`);
            console.log(`   Final tag count: ${analysisResult.tags.length}`);
            console.log(`   Confidence: ${analysisResult.confidence}%`);
            successful++;
          } else {
            console.error(`❌ Failed to update tags for: ${track.artist} - ${track.title}`);
            errors++;
          }
        }
      } catch (error) {
        console.error(`❌ Error processing ${track.artist} - ${track.title}:`, error);
        errors++;
      }
      
      processed++;
      
      // Add delay between tracks to avoid rate limiting
      if (i < tracks.length - 1) {
        console.log("⏳ Waiting 2 seconds before next track...");
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }

    return { successful, errors, processed };
  }

  /**
   * Run batch enhancement on all tracks
   */
  async runBatchEnhancement(mode: 'untagged' | 'enhance' | 'all' = 'enhance'): Promise<void> {
    console.log(`🎵 Starting batch tag enhancement (mode: ${mode})`);
    console.log(`📦 Chunk size: ${this.chunkSize} tracks`);
    console.log("=".repeat(60));

    try {
      let tracksToProcess: Track[];
      let mergeMode: boolean;

      switch (mode) {
        case 'untagged':
          tracksToProcess = this.getUntaggedTracks();
          mergeMode = false;
          console.log(`📊 Found ${tracksToProcess.length} untagged tracks`);
          break;
        case 'enhance':
          tracksToProcess = this.getTaggedTracks();
          mergeMode = true;
          console.log(`📊 Found ${tracksToProcess.length} tracks with existing tags to enhance`);
          break;
        case 'all':
          const untagged = this.getUntaggedTracks();
          const tagged = this.getTaggedTracks();
          tracksToProcess = [...untagged, ...tagged];
          mergeMode = true; // Will be determined per track
          console.log(`📊 Found ${untagged.length} untagged + ${tagged.length} tagged = ${tracksToProcess.length} total tracks`);
          break;
      }

      if (tracksToProcess.length === 0) {
        console.log("✅ No tracks found to process!");
        return;
      }

      // Split tracks into chunks
      const chunks: Track[][] = [];
      for (let i = 0; i < tracksToProcess.length; i += this.chunkSize) {
        chunks.push(tracksToProcess.slice(i, i + this.chunkSize));
      }

      console.log(`📦 Split into ${chunks.length} chunks of up to ${this.chunkSize} tracks each`);

      let totalSuccessful = 0;
      let totalErrors = 0;
      let totalProcessed = 0;

      // Process each chunk
      for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
        const chunk = chunks[chunkIndex];
        
        // Determine merge mode for this chunk if in 'all' mode
        const chunkMergeMode = mode === 'all' 
          ? chunk[0].assigned_tags && chunk[0].assigned_tags.length > 0
          : mergeMode;

        const result = await this.processTrackChunk(chunk, chunkIndex, chunkMergeMode);
        
        totalSuccessful += result.successful;
        totalErrors += result.errors;
        totalProcessed += result.processed;

        // Add delay between chunks
        if (chunkIndex < chunks.length - 1) {
          console.log(`\n⏳ Completed chunk ${chunkIndex + 1}/${chunks.length}. Waiting 5 seconds before next chunk...`);
          await new Promise(resolve => setTimeout(resolve, 5000));
        }
      }

      // Final summary
      console.log("\n" + "=".repeat(60));
      console.log("📊 BATCH TAG ENHANCEMENT SUMMARY");
      console.log("=".repeat(60));
      console.log(`Mode: ${mode}`);
      console.log(`Chunk size: ${this.chunkSize}`);
      console.log(`Total chunks processed: ${chunks.length}`);
      console.log(`Total tracks processed: ${totalProcessed}`);
      console.log(`Successful: ${totalSuccessful}`);
      console.log(`Errors: ${totalErrors}`);
      console.log(`Success rate: ${totalProcessed > 0 ? Math.round((totalSuccessful / totalProcessed) * 100) : 0}%`);

      if (totalSuccessful > 0) {
        console.log("\n🎉 Batch tag enhancement completed successfully!");
      }

    } catch (error) {
      console.error("❌ Fatal error during batch enhancement:", error);
      throw error;
    }
  }
}

// CLI interface
async function main() {
  const mode = (process.argv[2] as 'untagged' | 'enhance' | 'all') || 'enhance';
  const chunkSize = parseInt(process.argv[3]) || 25;

  console.log(`🚀 Batch Tag Enhancer`);
  console.log(`Mode: ${mode}`);
  console.log(`Chunk Size: ${chunkSize}`);

  try {
    const enhancer = new BatchTagEnhancer(undefined, chunkSize);
    await enhancer.runBatchEnhancement(mode);
  } catch (error) {
    console.error("❌ Fatal error:", error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}