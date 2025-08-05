#!/usr/bin/env ts-node

import * as fs from 'fs';
import * as path from 'path';

interface TrackMetadata {
  assigned_tags?: string[];
}

interface MetadataCollection {
  tracks: TrackMetadata[];
}

class RekordboxExportFormatCreator {
  private metadataPath: string;
  private allTags: Set<string> = new Set();

  constructor(metadataPath: string) {
    this.metadataPath = metadataPath;
  }

  async loadMetadata(): Promise<void> {
    const content = await fs.promises.readFile(this.metadataPath, 'utf-8');
    const data: MetadataCollection = JSON.parse(content);
    
    data.tracks.forEach(track => {
      if (track.assigned_tags) {
        track.assigned_tags.forEach(tag => this.allTags.add(tag));
      }
    });

    console.log(`📚 Found ${this.allTags.size} unique tags`);
  }

  private generateRekordboxExportXML(): string {
    const tags = Array.from(this.allTags).sort();
    
    let xml = `<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
  <COLLECTION Entries="0"/>
  <PLAYLISTS>
`;

    let playlistKeyId = 1;

    // Create root folder for all smart playlists
    xml += `    <NODE Type="0" Name="AI Smart Playlists" Count="0" Expanded="1">\n`;

    // Single-tag playlists
    tags.forEach(tag => {
      const playlistName = tag.split('-').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ');
      
      xml += `      <NODE Type="1" Name="${playlistName}" KeyType="0" Entries="${playlistKeyId++}">\n`;
      xml += `        <SMARTLIST Name="${playlistName}">\n`;
      xml += `          <SMARTCRITERIA>\n`;
      xml += `            <CRITERIA Field="Comment" Operator="Contains" Value="${tag}"/>\n`;
      xml += `          </SMARTCRITERIA>\n`;
      xml += `        </SMARTLIST>\n`;
      xml += `      </NODE>\n`;
    });

    // Combo playlists
    const combos = [
      { name: 'Dancefloor Classics', tags: ['instant-dancefloor', 'timeless-classic'] },
      { name: 'Energetic Crowd Pleasers', tags: ['energetic', 'crowd-pleaser'] },
      { name: 'Euphoric Peak Time', tags: ['euphoric-melody', 'peak-time'] },
      { name: 'Nostalgic Dancefloor', tags: ['nostalgic-hit', 'instant-dancefloor'] },
      { name: 'Psychedelic Journey Layers', tags: ['psychedelic-journey', 'layer-friendly'] },
      { name: 'Electronic Dance Foundations', tags: ['electronic-dance', 'rhythmic-foundation'] },
      { name: 'Vocal Magic Overlays', tags: ['vocal-magic', 'melodic-overlay'] },
      { name: 'Contemporary Layer Friendly', tags: ['contemporary-classic', 'layer-friendly'] }
    ];

    combos.forEach(combo => {
      if (combo.tags.every(tag => this.allTags.has(tag))) {
        xml += `      <NODE Type="1" Name="${combo.name}" KeyType="0" Entries="${playlistKeyId++}">\n`;
        xml += `        <SMARTLIST Name="${combo.name}">\n`;
        xml += `          <SMARTCRITERIA>\n`;
        combo.tags.forEach((tag, index) => {
          xml += `            <CRITERIA Field="Comment" Operator="Contains" Value="${tag}"`;
          if (index < combo.tags.length - 1) {
            xml += ` LogicalOperator="And"`;
          }
          xml += `/>\n`;
        });
        xml += `          </SMARTCRITERIA>\n`;
        xml += `        </SMARTLIST>\n`;
        xml += `      </NODE>\n`;
      }
    });

    xml += `    </NODE>\n`;
    xml += `  </PLAYLISTS>\n`;
    xml += `</DJ_PLAYLISTS>`;

    return xml;
  }

  async createExportFormat(): Promise<void> {
    try {
      const xml = this.generateRekordboxExportXML();
      const outputPath = path.join(process.cwd(), 'rekordbox_library_export.xml');
      
      await fs.promises.writeFile(outputPath, xml, 'utf-8');
      
      console.log(`✅ Created Rekordbox Export Format: ${outputPath}`);
      console.log(`\n📋 Import Instructions:`);
      console.log(`\n🔄 Method 1: Library Import (Recommended)`);
      console.log(`1. Close Rekordbox completely`);
      console.log(`2. Open Rekordbox`);
      console.log(`3. File → Library → Import Library`);
      console.log(`4. Select: ${outputPath}`);
      console.log(`5. Choose "Add to current library" (NOT "Replace")`);
      console.log(`\n🔄 Method 2: If Library Import doesn't work:`);
      console.log(`1. File → Export → Export Library`);
      console.log(`2. Export your current library first (backup)`);
      console.log(`3. Then use File → Import → Import Library with the backup`);
      console.log(`4. Then import this XML file`);
      console.log(`\n⚠️  Note: If Rekordbox prompts to restart, let it restart`);
      console.log(`   The playlists should appear after restart`);
      
    } catch (error) {
      console.error('❌ Error creating export format:', error);
    }
  }

  // Alternative: Create rekordbox.xml file directly 
  async createDirectDatabaseFile(): Promise<void> {
    console.log(`\n💡 Alternative: Direct Database Method`);
    console.log(`\nRekordbox stores data in:`);
    console.log(`~/Library/Pioneer/rekordbox/master.db (SQLite database)`);
    console.log(`\nFor safety, we're not modifying the database directly.`);
    console.log(`Use the XML import method above instead.`);
  }
}

async function main() {
  const basePath = '/Users/ethansarif-kattan/Music/ALLDJ/';
  const metadataPath = path.join(basePath, 'music_collection_metadata.json');

  console.log('🎵 Creating Rekordbox Library Export Format');
  console.log('===========================================');

  const creator = new RekordboxExportFormatCreator(metadataPath);
  
  try {
    await creator.loadMetadata();
    await creator.createExportFormat();
    await creator.createDirectDatabaseFile();
    
    console.log('\n✅ Export format creation complete!');
    console.log('\n🚨 If import still fails, try:');
    console.log('   1. Update Rekordbox to latest version');
    console.log('   2. Try importing just a few playlists at a time');
    console.log('   3. Create playlists manually using the guide');
    
  } catch (error) {
    console.error('❌ Error:', error);
  }
}

if (require.main === module) {
  main().catch(console.error);
}