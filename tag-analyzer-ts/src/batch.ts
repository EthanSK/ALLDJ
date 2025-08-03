#!/usr/bin/env node

import dotenv from "dotenv";
dotenv.config();

import { MusicTagAnalyzer } from "./tag-analyzer";

async function main() {
  const batchSize = parseInt(process.argv[2]) || 10;
  
  console.log(`🎵 Running batch analysis for ${batchSize} tracks...`);
  console.log("=".repeat(60));

  try {
    const analyzer = new MusicTagAnalyzer();
    
    let processed = 0;
    let successful = 0;
    let errors = 0;

    for (let i = 0; i < batchSize; i++) {
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
        } else {
          console.log(`✅ Successfully analyzed: ${result.track}`);
          console.log(`   Tags (${result.new_tags.length}): ${result.new_tags.join(", ")}`);
          console.log(`   Confidence: ${result.confidence}%`);
          successful++;
        }
      } catch (error) {
        console.error(`❌ Unexpected error processing track ${i + 1}:`, error);
        errors++;
      }
      
      processed++;
      
      // Add a small delay to avoid rate limiting
      if (i < batchSize - 1) {
        console.log("⏳ Waiting 2 seconds before next track...");
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }

    // Final summary
    console.log("\n" + "=".repeat(60));
    console.log("📊 BATCH ANALYSIS SUMMARY");
    console.log("=".repeat(60));
    console.log(`Total processed: ${processed}`);
    console.log(`Successful: ${successful}`);
    console.log(`Errors: ${errors}`);
    console.log(`Success rate: ${processed > 0 ? Math.round((successful / processed) * 100) : 0}%`);
    
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
