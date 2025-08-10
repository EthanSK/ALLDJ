#!/usr/bin/env node

import fs from 'fs';
import path from 'path';

/**
 * Setup script for LALAL.AI extractor
 * This script helps you configure the environment for LALAL.AI vocal extraction
 */

function checkSetup() {
  console.log('🎵 LALAL.AI Extractor Setup Check\n');

  const envPath = path.join(__dirname, '..', '.env');
  const flacDir = '/Users/ethansarif-kattan/Music/ALLDJ/flac';
  const outputDir = '/Users/ethansarif-kattan/Music/ALLDJ/extracted';

  // Check .env file
  if (fs.existsSync(envPath)) {
    console.log('✅ .env file found');
    
    const envContent = fs.readFileSync(envPath, 'utf8');
    if (envContent.includes('LALAL_API_KEY')) {
      console.log('✅ LALAL_API_KEY is configured');
    } else {
      console.log('❌ LALAL_API_KEY is missing from .env file');
      console.log('   Add this line to your .env file:');
      console.log('   LALAL_API_KEY=your_api_key_here');
    }
  } else {
    console.log('❌ .env file not found');
  }

  // Check FLAC directory
  if (fs.existsSync(flacDir)) {
    const flacFiles = fs.readdirSync(flacDir).filter(f => f.endsWith('.flac'));
    console.log(`✅ FLAC directory found with ${flacFiles.length} files`);
  } else {
    console.log(`❌ FLAC directory not found: ${flacDir}`);
  }

  // Check/create output directory
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
    console.log(`✅ Created output directory: ${outputDir}`);
  } else {
    console.log(`✅ Output directory exists: ${outputDir}`);
  }

  console.log('\n📋 Next Steps:');
  console.log('1. Get your LALAL.AI API key from: https://www.lalal.ai/api/');
  console.log('2. Add LALAL_API_KEY=your_key_here to your .env file');
  console.log('3. Run: npm run extract:example (for testing)');
  console.log('4. Run: npm run extract (for full processing)');
  
  console.log('\n⚠️  Important Notes:');
  console.log('- Each file uses processing time from your LALAL.AI account');
  console.log('- Start with the example script to test a single file first');
  console.log('- Check your account limits before processing large batches');
}

if (require.main === module) {
  checkSetup();
}
