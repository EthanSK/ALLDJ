#!/usr/bin/env ts-node

import * as fs from 'fs';
import * as path from 'path';

interface TrackMetadata {
  relative_path: string;
  filename: string;
  artist?: string;
  title?: string;
  album?: string;
  assigned_tags?: string[];
  bpm?: string | number;
  key?: string;
  research_notes?: {
    mood?: string;
    energy_level?: number;
    [key: string]: any;
  };
}

interface MetadataCollection {
  metadata: {
    total_files: number;
    directory_path: string;
  };
  tracks: TrackMetadata[];
}

class FlacTagger {
  private basePath: string;
  private metadataPath: string;

  constructor(basePath: string, metadataPath: string) {
    this.basePath = basePath;
    this.metadataPath = metadataPath;
  }

  async loadMetadata(): Promise<MetadataCollection | null> {
    try {
      const content = await fs.promises.readFile(this.metadataPath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      console.error('Error loading metadata:', error);
      return null;
    }
  }

  private async updateFlacWithCommand(filePath: string, tags: Record<string, string>): Promise<boolean> {
    const { spawn } = require('child_process');
    
    return new Promise((resolve) => {
      // Use metaflac command-line tool for reliable FLAC metadata editing
      const args = ['--preserve-modtime'];
      
      // Remove existing tags first to avoid conflicts
      Object.keys(tags).forEach(key => {
        args.push(`--remove-tag=${key.toUpperCase()}`);
      });
      
      // Add new tags
      Object.entries(tags).forEach(([key, value]) => {
        if (value && value.trim()) {
          args.push(`--set-tag=${key.toUpperCase()}=${value}`);
        }
      });
      
      args.push(filePath);
      
      const metaflac = spawn('metaflac', args);
      
      metaflac.on('close', (code: number) => {
        resolve(code === 0);
      });
      
      metaflac.on('error', (error: Error) => {
        console.error(`Error running metaflac: ${error}`);
        resolve(false);
      });
    });
  }

  async updateFlacTags(flacPath: string, trackMetadata: TrackMetadata, dryRun: boolean = false): Promise<boolean> {
    try {
      if (!fs.existsSync(flacPath)) {
        console.log(`Warning: File not found: ${flacPath}`);
        return false;
      }

      const tags: Record<string, string> = {};
      let changesMade = false;

      // Add all tags to COMMENT field only
      if (trackMetadata.assigned_tags && trackMetadata.assigned_tags.length > 0) {
        tags.COMMENT = trackMetadata.assigned_tags.join(', ');
        console.log(`  Will update COMMENT: ${tags.COMMENT}`);
        changesMade = true;
      }

      if (!changesMade) {
        return false;
      }

      if (dryRun) {
        console.log(`  [DRY RUN] Would update ${Object.keys(tags).length} tags in ${flacPath}`);
        return true;
      }

      // Use metaflac command for reliable updates
      const success = await this.updateFlacWithCommand(flacPath, tags);
      
      if (success) {
        console.log(`  ✓ Successfully updated ${flacPath}`);
      } else {
        console.log(`  ✗ Failed to update ${flacPath}`);
      }

      return success;

    } catch (error) {
      console.error(`Error updating ${flacPath}:`, error);
      return false;
    }
  }

  async processFiles(options: {
    dryRun?: boolean;
    filter?: string;
    limit?: number;
  } = {}): Promise<void> {
    const { dryRun = false, filter, limit } = options;

    console.log(`Loading metadata from: ${this.metadataPath}`);
    const data = await this.loadMetadata();
    
    if (!data) {
      console.error('Failed to load metadata');
      return;
    }

    console.log(`Found ${data.tracks.length} tracks in metadata`);
    
    if (dryRun) {
      console.log('🔍 DRY RUN MODE - No changes will be made');
    }

    let updatedCount = 0;
    let processedCount = 0;

    for (const track of data.tracks) {
      // Apply filter if specified
      if (filter && !track.filename.toLowerCase().includes(filter.toLowerCase())) {
        continue;
      }

      // Apply limit if specified
      if (limit && processedCount >= limit) {
        break;
      }

      const flacPath = path.join(this.basePath, track.relative_path);

      console.log(`\n📀 Processing: ${track.filename}`);
      console.log(`   Artist: ${track.artist || 'Unknown'}`);
      console.log(`   Title: ${track.title || 'Unknown'}`);
      console.log(`   Tags: ${track.assigned_tags?.length || 0} assigned`);

      try {
        const updated = await this.updateFlacTags(flacPath, track, dryRun);
        if (updated) {
          updatedCount++;
        }
      } catch (error) {
        console.error(`   Error processing file: ${error}`);
      }

      processedCount++;
    }

    console.log(`\n📊 Summary:`);
    console.log(`   Processed: ${processedCount} files`);
    console.log(`   Updated: ${updatedCount} files`);
    
    if (dryRun) {
      console.log('\n💡 Run without --dry-run to apply changes');
    } else {
      console.log('\n✅ Tagging complete!');
    }
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);
  
  const options = {
    basePath: '/Users/ethansarif-kattan/Music/ALLDJ/',
    metadataFile: 'music_collection_metadata.json',
    dryRun: false,
    filter: '',
    limit: 0
  };

  // Parse command line arguments
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--filter':
        options.filter = args[++i] || '';
        break;
      case '--limit':
        options.limit = parseInt(args[++i] || '0');
        break;
      case '--metadata':
        options.metadataFile = args[++i] || options.metadataFile;
        break;
      case '--base-path':
        options.basePath = args[++i] || options.basePath;
        break;
      case '--help':
        console.log(`
FLAC Tagger - Add metadata tags to FLAC files for Rekordbox

Usage: ts-node src/flac-tagger.ts [options]

Options:
  --dry-run           Show what would be changed without making changes
  --filter <text>     Only process files containing this text
  --limit <number>    Limit number of files to process
  --metadata <file>   Path to metadata JSON file (default: music_collection_metadata.json)
  --base-path <path>  Base path for music files (default: current directory)
  --help              Show this help message

Examples:
  ts-node src/flac-tagger.ts --dry-run
  ts-node src/flac-tagger.ts --filter "Beatles" --limit 10
  ts-node src/flac-tagger.ts --metadata my_metadata.json
        `);
        return;
    }
  }

  const metadataPath = path.join(options.basePath, options.metadataFile);
  const tagger = new FlacTagger(options.basePath, metadataPath);

  console.log('🎵 FLAC Tagger for Rekordbox');
  console.log('============================');
  
  await tagger.processFiles({
    dryRun: options.dryRun,
    filter: options.filter,
    limit: options.limit
  });
}

if (require.main === module) {
  main().catch(console.error);
}

export { FlacTagger };