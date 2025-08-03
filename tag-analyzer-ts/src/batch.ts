#!/usr/bin/env node

import dotenv from "dotenv";
dotenv.config();

import { MusicTagAnalyzer } from "./tag-analyzer";

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  
  // Colors
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  gray: '\x1b[90m',
  
  // Background colors
  bgRed: '\x1b[41m',
  bgGreen: '\x1b[42m',
  bgYellow: '\x1b[43m',
  bgBlue: '\x1b[44m',
};

// Helper functions for colored output
const colorLog = {
  success: (msg: string) => console.log(`${colors.green}✅ ${msg}${colors.reset}`),
  error: (msg: string) => console.log(`${colors.red}❌ ${msg}${colors.reset}`),
  warning: (msg: string) => console.log(`${colors.yellow}⚠️  ${msg}${colors.reset}`),
  info: (msg: string) => console.log(`${colors.blue}ℹ️  ${msg}${colors.reset}`),
  processing: (msg: string) => console.log(`${colors.cyan}🔄 ${msg}${colors.reset}`),
  music: (msg: string) => console.log(`${colors.magenta}🎵 ${msg}${colors.reset}`),
  robot: (msg: string) => console.log(`${colors.yellow}🤖 ${msg}${colors.reset}`),
  stats: (msg: string) => console.log(`${colors.bright}${colors.white}📊 ${msg}${colors.reset}`),
  header: (msg: string) => console.log(`${colors.bright}${colors.cyan}${msg}${colors.reset}`),
  dim: (msg: string) => console.log(`${colors.dim}${colors.gray}${msg}${colors.reset}`),
};

let shouldCancel = false;

// Handle graceful shutdown
process.on("SIGINT", () => {
  colorLog.warning("\n\n🛑 Received cancellation signal (Ctrl+C)");
  colorLog.processing("Finishing current track analysis...");
  colorLog.dim("💡 Press Ctrl+C again to force quit");
  shouldCancel = true;

  // Force quit on second Ctrl+C
  process.on("SIGINT", () => {
    colorLog.error("\n💥 Force quitting...");
    process.exit(130);
  });
});

async function main() {
  const batchSize = parseInt(process.argv[2]) || 10;
  const useOpenAI = process.argv.includes('--anthropic') ? false : true; // Default to OpenAI o3

  colorLog.music(`Running batch analysis for ${batchSize} tracks...`);
  colorLog.robot(`Using ${useOpenAI ? 'OpenAI o3 (reasoning)' : 'Anthropic Claude'}`);
  colorLog.dim(`💡 Press Ctrl+C to gracefully stop after current track`);
  colorLog.header("=".repeat(60));

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

      colorLog.processing(`\nProcessing track ${i + 1} of ${batchSize}...`);

      try {
        const result = await analyzer.analyzeAndUpdateTrack();

        if ("error" in result) {
          colorLog.error(`${result.error}`);
          errors++;

          // If no more untagged tracks, break early
          if (result.error.includes("No untagged tracks found")) {
            colorLog.success("\nNo more untagged tracks found. Batch complete!");
            break;
          }

          // Exit completely on any other error
          colorLog.error("\n💥 Exiting due to analysis failure.");
          process.exit(1);
        } else {
          colorLog.success(`Successfully analyzed: ${colors.bright}${result.track}${colors.reset}`);
          console.log(`   ${colors.cyan}Tags (${result.new_tags.length}):${colors.reset} ${colors.yellow}${result.new_tags.join(", ")}${colors.reset}`);
          console.log(`   ${colors.blue}Confidence:${colors.reset} ${colors.green}${result.confidence}%${colors.reset}`);
          successful++;
        }
      } catch (error) {
        colorLog.error(`Unexpected error processing track ${i + 1}: ${error}`);
        errors++;
        colorLog.error("\n💥 Exiting due to unexpected error.");
        process.exit(1);
      }

      processed++;

      // Add a small delay to avoid rate limiting (but check for cancellation)
      if (i < batchSize - 1 && !shouldCancel) {
        colorLog.dim("⏳ Waiting 2 seconds before next track...");
        // Use shorter intervals to check for cancellation more frequently
        for (let j = 0; j < 20; j++) {
          if (shouldCancel) break;
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
      }
    }

    // Final summary
    console.log("\n" + `${colors.bright}${colors.cyan}${"=".repeat(60)}${colors.reset}`);
    colorLog.stats("BATCH ANALYSIS SUMMARY");
    console.log(`${colors.bright}${colors.cyan}${"=".repeat(60)}${colors.reset}`);
    console.log(`${colors.white}Total processed:${colors.reset} ${colors.bright}${processed}${colors.reset}`);
    console.log(`${colors.green}Successful:${colors.reset} ${colors.bright}${successful}${colors.reset}`);
    console.log(`${colors.red}Errors:${colors.reset} ${colors.bright}${errors}${colors.reset}`);
    console.log(
      `${colors.blue}Success rate:${colors.reset} ${colors.bright}${colors.green}${
        processed > 0 ? Math.round((successful / processed) * 100) : 0
      }%${colors.reset}`
    );

    if (successful > 0) {
      colorLog.success("\n🎉 Batch analysis completed successfully!");
    }
  } catch (error) {
    colorLog.error(`Fatal error during batch analysis: ${error}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
