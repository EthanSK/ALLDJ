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

async function findLosslessFiles(directory: string): Promise<string[]> {
  const losslessFiles: string[] = [];
  
  async function scanDirectory(dir: string): Promise<void> {
    try {
      const entries = await fs.promises.readdir(dir, { withFileTypes: true });
      
      for (const entry of entries) {
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

async function copyFileWithStructure(sourcePath: string, sourceRoot: string, destinationRoot: string): Promise<boolean> {
  try {
    const relativePath = path.relative(sourceRoot, sourcePath);
    const destinationPath = path.join(destinationRoot, relativePath);
    const destinationDir = path.dirname(destinationPath);
    
    await ensureDirectoryExists(destinationDir);
    
    // Check if file already exists
    try {
      await fs.promises.access(destinationPath);
      console.log(`Skipping existing file: ${relativePath}`);
      return false;
    } catch {
      // File doesn't exist, proceed with copy
    }
    
    await fs.promises.copyFile(sourcePath, destinationPath);
    console.log(`Copied: ${relativePath}`);
    return true;
  } catch (error) {
    console.error(`Error copying file ${sourcePath}:`, error);
    throw error;
  }
}

async function copyLosslessFiles(): Promise<void> {
  console.log('Starting lossless file copy process...');
  console.log('Supported lossless formats:', LOSSLESS_EXTENSIONS.join(', '));
  console.log('');
  
  await ensureDirectoryExists(DESTINATION_BASE);
  
  const totalStats: CopyStats = {
    totalFiles: 0,
    copiedFiles: 0,
    skippedFiles: 0,
    errors: 0
  };
  
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
        const wasCopied = await copyFileWithStructure(filePath, sourceDir, DESTINATION_BASE);
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
  console.log(`\nDestination: ${DESTINATION_BASE}`);
}

// Run the script
copyLosslessFiles().catch(error => {
  console.error('Script failed:', error);
  process.exit(1);
});