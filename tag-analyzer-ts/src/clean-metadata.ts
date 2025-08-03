#!/usr/bin/env node

import * as fs from "fs";
import * as path from "path";
import { MusicMetadata } from "./types";

class MetadataCleaner {
  private tagTaxonomy: string;

  constructor() {
    this.tagTaxonomy = this.loadTagTaxonomy();
  }

  private loadTagTaxonomy(): string {
    try {
      const taxonomyPath = path.resolve(__dirname, "../../tag taxonomy.txt");
      return fs.readFileSync(taxonomyPath, "utf-8");
    } catch (error) {
      throw new Error("tag taxonomy.txt not found in parent directory");
    }
  }

  private getValidTags(): string[] {
    // Extract all valid tags from the taxonomy
    const taxonomyLines = this.tagTaxonomy.split("\n");
    const validTags: string[] = [];

    for (const line of taxonomyLines) {
      const trimmed = line.trim();
      // Look for lines that start with a tag (word followed by " - ")
      const tagMatch = trimmed.match(/^([a-z-]+)\s*-/);
      if (tagMatch) {
        validTags.push(tagMatch[1]);
      }
    }

    return validTags;
  }

  private validateTags(tags: string[]): { valid: string[]; invalid: string[] } {
    const validTags = this.getValidTags();
    const valid: string[] = [];
    const invalid: string[] = [];

    for (const tag of tags) {
      if (validTags.includes(tag)) {
        valid.push(tag);
      } else {
        invalid.push(tag);
      }
    }

    return { valid, invalid };
  }

  cleanMetadata(): void {
    const metadataPath = path.resolve(
      __dirname,
      "../../music_collection_metadata.json"
    );

    console.log("Loading metadata...");
    const data = fs.readFileSync(metadataPath, "utf-8");
    const metadata: MusicMetadata = JSON.parse(data);

    let totalTracksWithTags = 0;
    let totalInvalidTags = 0;
    let totalValidTags = 0;
    let tracksModified = 0;

    console.log("Validating tags against taxonomy...");

    for (const track of metadata.tracks) {
      if (track.assigned_tags && track.assigned_tags.length > 0) {
        totalTracksWithTags++;

        const validation = this.validateTags(track.assigned_tags);

        if (validation.invalid.length > 0) {
          console.log(
            `\n🎵 Track: ${track.artist || "Unknown"} - ${
              track.title || "Unknown"
            }`
          );
          console.log(`  ❌ Invalid tags: ${validation.invalid.join(", ")}`);
          console.log(`  ✅ Valid tags: ${validation.valid.join(", ")}`);

          // Update the track with only valid tags
          track.assigned_tags = validation.valid;

          // Reduce confidence if we removed tags
          if (track.tag_confidence && validation.invalid.length > 0) {
            track.tag_confidence = Math.max(
              0,
              track.tag_confidence - validation.invalid.length * 5
            );
          }

          // Update research notes
          if (track.research_notes) {
            track.research_notes += ` (Note: ${validation.invalid.length} invalid tags were removed during cleanup)`;
          }

          tracksModified++;
        }

        totalInvalidTags += validation.invalid.length;
        totalValidTags += validation.valid.length;
      }
    }

    console.log("\n=== CLEANUP SUMMARY ===");
    console.log(`Total tracks with tags: ${totalTracksWithTags}`);
    console.log(`Tracks modified: ${tracksModified}`);
    console.log(`Total valid tags: ${totalValidTags}`);
    console.log(`Total invalid tags removed: ${totalInvalidTags}`);
    console.log("=======================\n");

    if (tracksModified > 0) {
      console.log("Saving cleaned metadata...");
      fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
      console.log("✅ Metadata cleaned and saved!");
    } else {
      console.log("✅ No invalid tags found - metadata is already clean!");
    }
  }
}

const cleaner = new MetadataCleaner();
cleaner.cleanMetadata();
