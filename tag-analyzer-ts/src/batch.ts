#!/usr/bin/env node

import dotenv from "dotenv";
dotenv.config();

import { MusicTagAnalyzer } from "./tag-analyzer";

let shouldCancel = false;

// Handle graceful shutdown
process.on("SIGINT", () => {
  console.log("\n\n🛑 Received cancellation signal (Ctrl+C)");
  console.log("🔄 Finishing current track analysis...");
  console.log("💡 Press Ctrl+C again to force quit");
  shouldCancel = true;

  // Force quit on second Ctrl+C
  process.on("SIGINT", () => {
    console.log("\n💥 Force quitting...");
    process.exit(130);
  });
});

async function main() {
  const batchSize = parseInt(process.argv[2]) || 10;
  const useOpenAI = process.argv.includes('--anthropic') ? false : true; // Default to OpenAI o3

  console.log(`🎵 Running batch analysis for ${batchSize} tracks...`);
  console.log(`🤖 Using ${useOpenAI ? 'OpenAI o3 (reasoning)' : 'Anthropic Claude'}`);
  console.log(`💡 Press Ctrl+C to gracefully stop after current track`);
  console.log("=".repeat(60));

  try {
    const analyzer = new MusicTagAnalyzer(
      process.env.ANTHROPIC_API_KEY,
      process.env.OPENAI_API_KEY,
      useOpenAI
    );

    let processed = 0;
    let successful = 0;
    let errors = 0;

    for (let i = 0; i < batchSize; i++) {
      // Check for cancellation signal
      if (shouldCancel) {
        console.log(
          `\n🛑 Batch cancelled gracefully after ${processed} tracks`
        );
        break;
      }

      console.log(`\n🔄 Processing track ${i + 1} of ${batchSize}...`);

      try {
        const result = await analyzer.analyzeAndUpdateTrack();

        if ("error" in result) {
          console.error(`❌ Error: ${result.error}`);
          errors++;

          // If no more untagged tracks, break early
          if (result.error.includes("No untagged tracks found")) {
            console.log("\n✅ No more untagged tracks found. Batch complete!");
            break;
          }

          // Exit completely on any other error
          console.error("\n💥 Exiting due to analysis failure.");
          process.exit(1);
        } else {
          console.log(`✅ Successfully analyzed: ${result.track}`);
          console.log(
            `   Tags (${result.new_tags.length}): ${result.new_tags.join(", ")}`
          );
          console.log(`   Confidence: ${result.confidence}%`);
          successful++;
        }
      } catch (error) {
        console.error(`❌ Unexpected error processing track ${i + 1}:`, error);
        errors++;
        console.error("\n💥 Exiting due to unexpected error.");
        process.exit(1);
      }

      processed++;

      // Add a small delay to avoid rate limiting (but check for cancellation)
      if (i < batchSize - 1 && !shouldCancel) {
        console.log("⏳ Waiting 2 seconds before next track...");
        // Use shorter intervals to check for cancellation more frequently
        for (let j = 0; j < 20; j++) {
          if (shouldCancel) break;
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
      }
    }

    // Final summary
    console.log("\n" + "=".repeat(60));
    console.log("📊 BATCH ANALYSIS SUMMARY");
    console.log("=".repeat(60));
    console.log(`Total processed: ${processed}`);
    console.log(`Successful: ${successful}`);
    console.log(`Errors: ${errors}`);
    console.log(
      `Success rate: ${
        processed > 0 ? Math.round((successful / processed) * 100) : 0
      }%`
    );

    if (successful > 0) {
      console.log("\n🎉 Batch analysis completed successfully!");
    }
  } catch (error) {
    console.error("❌ Fatal error during batch analysis:", error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
