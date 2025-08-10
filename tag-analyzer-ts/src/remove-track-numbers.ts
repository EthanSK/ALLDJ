import * as fs from 'fs';
import * as path from 'path';

const TARGET_DIRECTORY = '/Volumes/T7 Shield/3000AD/all_og_lossless';

interface RenameStats {
  totalFiles: number;
  renamedFiles: number;
  skippedFiles: number;
  errors: number;
}

function removeTrackNumbers(filename: string): string {
  // Remove various track number patterns:
  // "01 Song.ext" -> "Song.ext"
  // "2-03 Song.ext" -> "Song.ext" 
  // "1-05 Song.ext" -> "Song.ext"
  // "31 Song.ext" -> "Song.ext"
  
  let cleanName = filename;
  
  // Pattern 1: Simple track numbers "01 ", "02 ", etc.
  cleanName = cleanName.replace(/^(\d{1,2})\s+/, '');
  
  // Pattern 2: Disc-track numbers "1-01 ", "2-03 ", etc.
  cleanName = cleanName.replace(/^(\d{1,2})-(\d{1,2})\s+/, '');
  
  return cleanName;
}

function generateUniqueFileName(baseName: string, directory: string, existingNames: Set<string>): string {
  const ext = path.extname(baseName);
  const nameWithoutExt = path.basename(baseName, ext);
  
  let uniqueName = baseName;
  let counter = 1;
  
  while (existingNames.has(uniqueName.toLowerCase()) || 
         fs.existsSync(path.join(directory, uniqueName))) {
    uniqueName = `${nameWithoutExt} (${counter})${ext}`;
    counter++;
  }
  
  existingNames.add(uniqueName.toLowerCase());
  return uniqueName;
}

async function removeTrackNumbersFromFiles(): Promise<void> {
  console.log('Removing track numbers from filenames...');
  console.log(`Target directory: ${TARGET_DIRECTORY}`);
  console.log('');
  
  try {
    await fs.promises.access(TARGET_DIRECTORY);
  } catch {
    console.log(`Directory does not exist: ${TARGET_DIRECTORY}`);
    return;
  }
  
  const files = await fs.promises.readdir(TARGET_DIRECTORY);
  const musicFiles = files.filter(file => {
    const ext = path.extname(file).toLowerCase();
    return ['.flac', '.wav', '.aiff', '.aif', '.m4a', '.alac', '.ape', '.wv', '.dsd', '.dsf', '.dff'].includes(ext);
  });
  
  console.log(`Found ${musicFiles.length} music files to process`);
  console.log('');
  
  const stats: RenameStats = {
    totalFiles: musicFiles.length,
    renamedFiles: 0,
    skippedFiles: 0,
    errors: 0
  };
  
  const usedNames = new Set<string>();
  
  for (const originalFile of musicFiles) {
    try {
      const cleanName = removeTrackNumbers(originalFile);
      
      // If the name didn't change, skip it
      if (cleanName === originalFile) {
        console.log(`Skipped (no track number): ${originalFile}`);
        stats.skippedFiles++;
        usedNames.add(cleanName.toLowerCase());
        continue;
      }
      
      // Generate unique name if needed
      const uniqueName = generateUniqueFileName(cleanName, TARGET_DIRECTORY, usedNames);
      
      const oldPath = path.join(TARGET_DIRECTORY, originalFile);
      const newPath = path.join(TARGET_DIRECTORY, uniqueName);
      
      await fs.promises.rename(oldPath, newPath);
      
      if (uniqueName !== cleanName) {
        console.log(`Renamed: ${originalFile} → ${uniqueName} (conflict resolved)`);
      } else {
        console.log(`Renamed: ${originalFile} → ${cleanName}`);
      }
      
      stats.renamedFiles++;
      
    } catch (error) {
      console.error(`Error processing ${originalFile}:`, error);
      stats.errors++;
    }
  }
  
  console.log('\n=== FINAL SUMMARY ===');
  console.log(`Total files processed: ${stats.totalFiles}`);
  console.log(`Files renamed: ${stats.renamedFiles}`);
  console.log(`Files skipped: ${stats.skippedFiles}`);
  console.log(`Errors: ${stats.errors}`);
}

// Run the script
removeTrackNumbersFromFiles().catch(error => {
  console.error('Script failed:', error);
  process.exit(1);
});