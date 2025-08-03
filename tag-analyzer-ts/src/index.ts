#!/usr/bin/env node

import dotenv from "dotenv";
dotenv.config();

import { MusicTagAnalyzer } from "./tag-analyzer";

async function main() {
  const filename = process.argv[2];

  try {
    // Use OpenAI by default
    const analyzer = new MusicTagAnalyzer(undefined, undefined, true);

    if (filename) {
      console.log(`Analyzing specific track: ${filename}`);
      const result = await analyzer.analyzeAndUpdateTrack(filename);

      if ("error" in result) {
        console.error(`Error: ${result.error}`);
        process.exit(1);
      }

      printResults(result);
    } else {
      console.log("Finding first untagged track...");
      const result = await analyzer.analyzeAndUpdateTrack();

      if ("error" in result) {
        console.error(`Error: ${result.error}`);
        process.exit(1);
      }

      printResults(result);
    }
  } catch (error) {
    console.error("Error:", error);
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
