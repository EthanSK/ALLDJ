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

const SOURCE_DIRECTORY = '/Volumes/T7 Shield/3000AD';
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
        
        // Skip the destination directory to avoid recursive copying
        if (fullPath === DESTINATION_BASE) {
          continue;
        }
        
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

function generateUniqueFileName(baseName: string, existingNames: Set<string>): string {
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

function truncateFileName(fileName: string, maxLength: number = 250): string {
  if (fileName.length <= maxLength) {
    return fileName;
  }
  
  const ext = path.extname(fileName);
  const nameWithoutExt = path.basename(fileName, ext);
  const truncatedName = nameWithoutExt.substring(0, maxLength - ext.length - 10) + '...' + ext;
  
  return truncatedName;
}

async function copyFileFlat(sourcePath: string, destinationDir: string, existingNames: Set<string>): Promise<boolean> {
  try {
    let originalName = path.basename(sourcePath);
    originalName = truncateFileName(originalName);
    
    const uniqueName = generateUniqueFileName(originalName, existingNames);
    const destinationPath = path.join(destinationDir, uniqueName);
    
    await fs.promises.copyFile(sourcePath, destinationPath);
    
    if (uniqueName !== originalName) {
      console.log(`Copied: ${path.basename(sourcePath)} → ${uniqueName}`);
    } else {
      console.log(`Copied: ${originalName}`);
    }
    
    return true;
  } catch (error) {
    console.error(`Error copying file ${sourcePath}:`, error);
    return false;
  }
}

async function copyT7LosslessFiles(): Promise<void> {
  console.log('Copying lossless files from T7 Shield 3000AD folder only...');
  console.log('Supported lossless formats:', LOSSLESS_EXTENSIONS.join(', '));
  console.log('');
  
  await ensureDirectoryExists(DESTINATION_BASE);
  console.log('Clearing existing files...');
  await clearDestinationDirectory(DESTINATION_BASE);
  console.log('');
  
  console.log(`Processing source directory: ${SOURCE_DIRECTORY}`);
  
  try {
    await fs.promises.access(SOURCE_DIRECTORY);
  } catch {
    console.log(`Source directory does not exist: ${SOURCE_DIRECTORY}`);
    return;
  }
  
  const losslessFiles = await findLosslessFiles(SOURCE_DIRECTORY);
  console.log(`Found ${losslessFiles.length} lossless files in ${SOURCE_DIRECTORY}`);
  console.log('');
  
  const stats: CopyStats = {
    totalFiles: losslessFiles.length,
    copiedFiles: 0,
    skippedFiles: 0,
    errors: 0
  };
  
  const existingNames = new Set<string>();
  
  for (const filePath of losslessFiles) {
    const wasCopied = await copyFileFlat(filePath, DESTINATION_BASE, existingNames);
    if (wasCopied) {
      stats.copiedFiles++;
    } else {
      stats.errors++;
    }
  }
  
  console.log('\n=== FINAL SUMMARY ===');
  console.log(`Total lossless files found: ${stats.totalFiles}`);
  console.log(`Files copied: ${stats.copiedFiles}`);
  console.log(`Errors: ${stats.errors}`);
  console.log(`\nAll files copied FLAT to: ${DESTINATION_BASE}`);
}

// Run the script
copyT7LosslessFiles().catch(error => {
  console.error('Script failed:', error);
  process.exit(1);
});