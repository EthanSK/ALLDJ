import * as fs from 'fs';
import * as path from 'path';

const FLAC_DIRECTORY = '/Users/ethansarif-kattan/Music/ALLDJ/flac';

interface RenameStats {
  totalFiles: number;
  renamedFiles: number;
  skippedFiles: number;
  errors: number;
}

function removeDiscTrackNumbers(filename: string): string {
  // Remove disc-track patterns like:
  // "01-01 Song.flac" -> "Song.flac"
  // "02-06 Song.flac" -> "Song.flac" 
  // "01-15 Song.flac" -> "Song.flac"
  
  let cleanName = filename;
  
  // Pattern: Disc-Track numbers "01-01 ", "02-06 ", etc.
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

async function removeFlacTrackNumbers(): Promise<void> {
  console.log('Removing disc-track numbers from FLAC filenames...');
  console.log(`Target directory: ${FLAC_DIRECTORY}`);
  console.log('');
  
  try {
    await fs.promises.access(FLAC_DIRECTORY);
  } catch {
    console.log(`Directory does not exist: ${FLAC_DIRECTORY}`);
    return;
  }
  
  const files = await fs.promises.readdir(FLAC_DIRECTORY);
  const flacFiles = files.filter(file => file.toLowerCase().endsWith('.flac'));
  
  console.log(`Found ${flacFiles.length} FLAC files to process`);
  console.log('');
  
  const stats: RenameStats = {
    totalFiles: flacFiles.length,
    renamedFiles: 0,
    skippedFiles: 0,
    errors: 0
  };
  
  const usedNames = new Set<string>();
  
  for (const originalFile of flacFiles) {
    try {
      const cleanName = removeDiscTrackNumbers(originalFile);
      
      // If the name didn't change, skip it
      if (cleanName === originalFile) {
        console.log(`Skipped (no track number): ${originalFile}`);
        stats.skippedFiles++;
        usedNames.add(cleanName.toLowerCase());
        continue;
      }
      
      // Generate unique name if needed
      const uniqueName = generateUniqueFileName(cleanName, FLAC_DIRECTORY, usedNames);
      
      const oldPath = path.join(FLAC_DIRECTORY, originalFile);
      const newPath = path.join(FLAC_DIRECTORY, uniqueName);
      
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
removeFlacTrackNumbers().catch(error => {
  console.error('Script failed:', error);
  process.exit(1);
});