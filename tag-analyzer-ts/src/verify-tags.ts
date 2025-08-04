#!/usr/bin/env ts-node

import * as fs from 'fs';
import * as path from 'path';
import { parseFile } from 'music-metadata';

async function verifyTags(filePath: string): Promise<void> {
  try {
    if (!fs.existsSync(filePath)) {
      console.log(`❌ File not found: ${filePath}`);
      return;
    }

    const metadata = await parseFile(filePath);
    const comments = metadata.common.comment || [];
    let comment = 'No comment found';
    
    if (comments.length > 0) {
      if (typeof comments[0] === 'string') {
        comment = comments[0];
      } else if (comments[0] && typeof comments[0] === 'object' && 'text' in comments[0]) {
        comment = (comments[0] as any).text || 'No text in comment object';
      } else {
        comment = JSON.stringify(comments[0]);
      }
    }
    
    console.log(`\n📀 ${path.basename(filePath)}`);
    console.log(`   Artist: ${metadata.common.artist || 'Unknown'}`);
    console.log(`   Title: ${metadata.common.title || 'Unknown'}`);
    console.log(`   Genre: ${metadata.common.genre?.[0] || 'No genre'}`);
    console.log(`   FULL COMMENT: "${comment}"`);
    
  } catch (error) {
    console.error(`❌ Error reading ${filePath}:`, error);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const limit = args.includes('--limit') ? parseInt(args[args.indexOf('--limit') + 1] || '5') : 5;
  
  console.log('🔍 Verifying FLAC tags in COMMENT field');
  console.log('=====================================');
  
  // Test the files we just updated
  const testFiles = [
    'flac/02-06 Watermelon In Easter Hay.flac',
    'flac/01-03 It\'s A Lovely Day Today.flac', 
    'flac/01-05 Left Hand Free.flac',
    'flac/01-04 50 Ways to Leave Your Lover.flac',
    'flac/01-01 Marea (we\'ve lost dancing).flac'
  ];
  
  const basePath = '/Users/ethansarif-kattan/Music/ALLDJ/';
  
  for (let i = 0; i < Math.min(testFiles.length, limit); i++) {
    const fullPath = path.join(basePath, testFiles[i]);
    await verifyTags(fullPath);
  }
}

if (require.main === module) {
  main().catch(console.error);
}