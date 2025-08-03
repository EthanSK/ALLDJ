#!/usr/bin/env node

import dotenv from "dotenv";
dotenv.config();

import { MusicTagAnalyzer } from "./tag-analyzer";

async function main() {
  try {
    // Constructor: (apiKey?: string, openaiApiKey?: string, useOpenAI = false)
    const analyzer = new MusicTagAnalyzer(undefined, undefined, true); // Use OpenAI by default

    // Run analysis for 10 tracks
    for (let i = 0; i < 10; i++) {
      console.log(`\n=== Processing track ${i + 1}/10 ===`);
      const result = await analyzer.analyzeAndUpdateTrack();

      if ("error" in result) {
        console.log(`Error: ${result.error}`);
        if (result.error === "No untagged tracks found") {
          console.log("No more untagged tracks to process.");
          break;
        }
        continue;
      }

      printResults(result);
    }
  } catch (error) {
    console.error("Error in main:", error);
    process.exit(1);
  }
}

function printResults(result: any) {
  console.log(`\nResults for: ${result.track}`);
  console.log(
    `Old tags (${result.old_tags.length}): ${result.old_tags.join(", ")}`
  );
  console.log(
    `New tags (${result.new_tags.length}): ${result.new_tags.join(", ")}`
  );
  console.log(`Confidence: ${result.confidence}%`);
  console.log(`Research notes: ${result.research_notes}`);
  console.log(`Updated: ${result.updated ? "✓" : "✗"}`);
}

if (require.main === module) {
  main();
}
