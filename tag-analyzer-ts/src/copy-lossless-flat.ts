import * as fs from 'fs';
import * as path from 'path';

interface CopyStats {
  totalFiles: number;
  copiedFiles: number;
  skippedFiles: number;
  errors: number;
}

const LOSSLESS_EXTENSIONS = [
  '.flac',
  '.wav',
  '.aiff',
  '.aif',
  '.m4a',
  '.alac',
  '.ape',
  '.wv',
  '.dsd',
  '.dsf',
  '.dff'
];

const SOURCE_DIRECTORIES = [
  '/Volumes/T7 Shield/3000AD',
  '/Users/ethansarif-kattan/Music/Music/Media.localized/Music'
];

const DESTINATION_BASE = '/Volumes/T7 Shield/3000AD/all_og_lossless';

async function ensureDirectoryExists(dirPath: string): Promise<void> {
  try {
    await fs.promises.access(dirPath);
  } catch {
    await fs.promises.mkdir(dirPath, { recursive: true });
    console.log(`Created directory: ${dirPath}`);
  }
}

async function clearDestinationDirectory(dirPath: string): Promise<void> {
  try {
    await fs.promises.access(dirPath);
    const entries = await fs.promises.readdir(dirPath);
    
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry);
      const stat = await fs.promises.stat(fullPath);
      
      if (stat.isDirectory()) {
        await fs.promises.rm(fullPath, { recursive: true });
        console.log(`Removed directory: ${entry}`);
      } else {
        await fs.promises.unlink(fullPath);
        console.log(`Removed file: ${entry}`);
      }
    }
  } catch (error) {
    console.log(`Destination directory doesn't exist or is empty`);
  }
}

async function findLosslessFiles(directory: string): Promise<string[]> {
  const losslessFiles: string[] = [];
  
  async function scanDirectory(dir: string): Promise<void> {
    try {
      const entries = await fs.promises.readdir(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        // Skip hidden files and system files
        if (entry.name.startsWith('.')) {
          continue;
        }
        
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory()) {
          await scanDirectory(fullPath);
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();
          if (LOSSLESS_EXTENSIONS.includes(ext)) {
            losslessFiles.push(fullPath);
          }
        }
      }
    } catch (error) {
      console.error(`Error scanning directory ${dir}:`, error);
    }
  }
  
  await scanDirectory(directory);
  return losslessFiles;
}

function generateUniqueFileName(baseName: string, destinationDir: string, existingNames: Set<string>): string {
  const ext = path.extname(baseName);
  const nameWithoutExt = path.basename(baseName, ext);
  
  let uniqueName = baseName;
  let counter = 1;
  
  while (existingNames.has(uniqueName.toLowerCase())) {
    uniqueName = `${nameWithoutExt} (${counter})${ext}`;
    counter++;
  }
  
  existingNames.add(uniqueName.toLowerCase());
  return uniqueName;
}

async function copyFileFlat(sourcePath: string, destinationDir: string, existingNames: Set<string>): Promise<boolean> {
  try {
    const originalName = path.basename(sourcePath);
    const uniqueName = generateUniqueFileName(originalName, destinationDir, existingNames);
    const destinationPath = path.join(destinationDir, uniqueName);
    
    await fs.promises.copyFile(sourcePath, destinationPath);
    
    if (uniqueName !== originalName) {
      console.log(`Copied: ${originalName} → ${uniqueName}`);
    } else {
      console.log(`Copied: ${originalName}`);
    }
    
    return true;
  } catch (error) {
    console.error(`Error copying file ${sourcePath}:`, error);
    throw error;
  }
}

async function copyLosslessFilesFlat(): Promise<void> {
  console.log('Starting lossless file copy process (FLAT structure)...');
  console.log('Supported lossless formats:', LOSSLESS_EXTENSIONS.join(', '));
  console.log('');
  
  await ensureDirectoryExists(DESTINATION_BASE);
  console.log('Clearing existing files...');
  await clearDestinationDirectory(DESTINATION_BASE);
  console.log('');
  
  const totalStats: CopyStats = {
    totalFiles: 0,
    copiedFiles: 0,
    skippedFiles: 0,
    errors: 0
  };
  
  const existingNames = new Set<string>();
  
  for (const sourceDir of SOURCE_DIRECTORIES) {
    console.log(`Processing source directory: ${sourceDir}`);
    
    try {
      await fs.promises.access(sourceDir);
    } catch {
      console.log(`Source directory does not exist: ${sourceDir}`);
      continue;
    }
    
    const losslessFiles = await findLosslessFiles(sourceDir);
    console.log(`Found ${losslessFiles.length} lossless files in ${sourceDir}`);
    
    const stats: CopyStats = {
      totalFiles: losslessFiles.length,
      copiedFiles: 0,
      skippedFiles: 0,
      errors: 0
    };
    
    for (const filePath of losslessFiles) {
      try {
        const wasCopied = await copyFileFlat(filePath, DESTINATION_BASE, existingNames);
        if (wasCopied) {
          stats.copiedFiles++;
        } else {
          stats.skippedFiles++;
        }
      } catch (error) {
        stats.errors++;
      }
    }
    
    console.log(`\nResults for ${sourceDir}:`);
    console.log(`  Total files found: ${stats.totalFiles}`);
    console.log(`  Files copied: ${stats.copiedFiles}`);
    console.log(`  Files skipped: ${stats.skippedFiles}`);
    console.log(`  Errors: ${stats.errors}`);
    console.log('');
    
    totalStats.totalFiles += stats.totalFiles;
    totalStats.copiedFiles += stats.copiedFiles;
    totalStats.skippedFiles += stats.skippedFiles;
    totalStats.errors += stats.errors;
  }
  
  console.log('=== FINAL SUMMARY ===');
  console.log(`Total lossless files found: ${totalStats.totalFiles}`);
  console.log(`Total files copied: ${totalStats.copiedFiles}`);
  console.log(`Total files skipped: ${totalStats.skippedFiles}`);
  console.log(`Total errors: ${totalStats.errors}`);
  console.log(`\nAll files copied FLAT to: ${DESTINATION_BASE}`);
}

// Run the script
copyLosslessFilesFlat().catch(error => {
  console.error('Script failed:', error);
  process.exit(1);
});