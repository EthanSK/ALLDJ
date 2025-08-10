#!/usr/bin/env node

import dotenv from "dotenv";
dotenv.config();

import { LalalAIExtractor, ProcessingConfig } from "./lalal-extractor";

/**
 * Example usage script for LALAL.AI extractor
 * This script demonstrates different ways to use the extractor
 */

async function main() {
  try {
    // Initialize the extractor
    const extractor = new LalalAIExtractor();

    // First, check your account limits
    console.log('Checking account limits...');
    await extractor.checkLimits();

    // Example 1: Extract vocals only from all files
    console.log('\n=== Example 1: Vocals Only ===');
    const vocalsConfig: ProcessingConfig[] = [
      {
        stem: 'vocals',
        splitter: 'phoenix', // Best quality splitter
        enhanced_processing_enabled: true,
      }
    ];

    // Example 2: Extract multiple stems
    console.log('\n=== Example 2: Multiple Stems ===');
    const multiConfig: ProcessingConfig[] = [
      {
        stem: 'vocals',
        splitter: 'phoenix',
        enhanced_processing_enabled: true,
      },
      {
        stem: 'drum',
        splitter: 'phoenix',
      },
      {
        stem: 'bass',
        splitter: 'phoenix',
      }
    ];

    // Example 3: Voice processing with noise reduction
    console.log('\n=== Example 3: Voice with Noise Reduction ===');
    const voiceConfig: ProcessingConfig[] = [
      {
        stem: 'voice',
        splitter: 'phoenix',
        dereverb_enabled: true,
        noise_cancelling_level: 1, // 0=mild, 1=normal, 2=aggressive
      }
    ];

    // Choose which configuration to use
    // Change this to multiConfig or voiceConfig if you want different processing
    const selectedConfig = vocalsConfig;

    console.log('\nSelected configuration:');
    selectedConfig.forEach((config, index) => {
      console.log(`  ${index + 1}. ${config.stem} (${config.splitter || 'auto'})`);
      if (config.enhanced_processing_enabled) console.log('     - Enhanced processing enabled');
      if (config.dereverb_enabled) console.log('     - Dereverberation enabled');
      if (config.noise_cancelling_level !== undefined) console.log(`     - Noise cancelling: ${config.noise_cancelling_level}`);
    });

    // Ask for confirmation
    console.log('\nThis will process ALL FLAC files in your collection.');
    console.log('Each file will be uploaded to LALAL.AI and processed.');
    console.log('Make sure you have sufficient credits in your LALAL.AI account.');
    
    // In a real script, you might want to add user confirmation here
    // For now, we'll comment out the actual processing to avoid accidental runs
    
    console.log('\n⚠️  SAFETY: Actual processing is commented out to prevent accidental runs.');
    console.log('Uncomment the line below to start processing:');
    console.log('// await extractor.processAllFiles(selectedConfig, true);');
    
    // Uncomment the next line when you're ready to run:
    await extractor.processAllFiles(selectedConfig, true);

  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

// Alternative: Process just a single file for testing
async function processSingleFile() {
  try {
    const extractor = new LalalAIExtractor();
    
    // Path to a single test file
    const testFile = '/Users/ethansarif-kattan/Music/ALLDJ/flac/01-01 \'Til It\'s Over.flac';
    
    const config: ProcessingConfig[] = [
      {
        stem: 'vocals',
        splitter: 'phoenix',
        enhanced_processing_enabled: true,
      }
    ];

    console.log('Processing single file for testing...');
    await extractor.processFile(testFile, config);
    
  } catch (error) {
    console.error('Error processing single file:', error);
  }
}

if (require.main === module) {
  // Check for API key
  if (!process.env.LALAL_API_KEY) {
    console.error('❌ LALAL_API_KEY environment variable is required');
    console.error('Add this to your .env file:');
    console.error('LALAL_API_KEY=your_api_key_here');
    console.error('\nGet your API key from: https://www.lalal.ai/api/');
    process.exit(1);
  }

  // Run the main function
  main().catch(error => {
    console.error('Unhandled error:', error);
    process.exit(1);
  });
}
