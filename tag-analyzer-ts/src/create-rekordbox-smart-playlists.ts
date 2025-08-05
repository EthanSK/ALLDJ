#!/usr/bin/env ts-node

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

interface TrackMetadata {
  assigned_tags?: string[];
}

interface MetadataCollection {
  tracks: TrackMetadata[];
}

class RekordboxSmartPlaylistCreator {
  private metadataPath: string;
  private allTags: Set<string> = new Set();

  constructor(metadataPath: string) {
    this.metadataPath = metadataPath;
  }

  async loadMetadata(): Promise<void> {
    const content = await fs.promises.readFile(this.metadataPath, 'utf-8');
    const data: MetadataCollection = JSON.parse(content);
    
    // Extract all unique tags
    data.tracks.forEach(track => {
      if (track.assigned_tags) {
        track.assigned_tags.forEach(tag => this.allTags.add(tag));
      }
    });

    console.log(`📚 Found ${this.allTags.size} unique tags`);
  }

  private generateRekordboxXML(): string {
    const tags = Array.from(this.allTags).sort();
    
    let xml = `<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
  <PLAYLISTS>
`;

    // Generate folder structure with smart playlists
    const categories = {
      'DOPAMINE SOURCE': [
        'nostalgic-hit', 'euphoric-melody', 'emotional-depth', 'textural-beauty',
        'rhythmic-hypnosis', 'harmonic-surprise', 'vocal-magic', 'psychedelic-journey',
        'sophisticated-groove'
      ],
      'MIXING ROLE': [
        'rhythmic-foundation', 'melodic-overlay', 'bridge-element', 'texture-add',
        'anchor-track', 'wildcard', 'transition-tool', 'emotional-crescendo', 'palate-cleanser'
      ],
      'DANCEABILITY': [
        'instant-dancefloor', 'crowd-pleaser', 'peak-time', 'body-mover',
        'head-nodder', 'non-danceable-standalone'
      ],
      'ENERGY DYNAMICS': [
        'energetic', 'energy-injector', 'energy-sustainer', 'energy-shifter',
        'instant-impact', 'slow-burn', 'lifts-mood'
      ],
      'GENRES': [
        'electronic-dance', 'electronic-experimental', 'electronic-ambient',
        'rock-psychedelic', 'rock-indie', 'rock-classic', 'hip-hop-conscious',
        'hip-hop-experimental', 'pop-sophisticated', 'world-fusion'
      ],
      'ERA BRIDGING': [
        'timeless-classic', 'contemporary-classic', 'retro-modern',
        'genre-crossover', 'cultural-moment', 'generational-bridge'
      ],
      'GENERATIONAL APPEAL': [
        'gen-z-nostalgia', 'millennial-comfort', 'gen-x-wisdom',
        'boomer-classic', 'indie-cred', 'mainstream-crossover'
      ],
      'MIXING COMPATIBILITY': [
        'layer-friendly', 'breakdown-rich', 'loop-gold', 'mashup-ready',
        'beatmatched-friendly', 'smooth-transitions'
      ],
      'SET POSITIONING': [
        'set-opener', 'warm-up', 'peak-time', 'emotional-peak',
        'comedown', 'sunrise', 'interlude'
      ],
      'PSYCHEDELIC/CONSCIOUSNESS': [
        'mind-expanding', 'reality-bending', 'time-dilation',
        'dream-logic', 'color-synesthesia', 'meditation-inducer'
      ],
      'PERSONAL TAGS': [
        'deep', 'dopamine', 'funny', 'drum-bass-layer'
      ]
    };

    let nodeId = 1;

    // Create category folders with smart playlists
    Object.entries(categories).forEach(([categoryName, categoryTags]) => {
      xml += `    <NODE Type="1" Name="${categoryName}" Count="0" Expanded="1">\n`;
      
      categoryTags.forEach(tag => {
        if (this.allTags.has(tag)) {
          const playlistName = tag.split('-').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
          ).join(' ');
          
          // Create smart playlist XML node
          xml += `      <NODE Type="2" Name="${playlistName}" Count="0" Expanded="0">\n`;
          xml += `        <SMARTLIST Name="${playlistName}" Count="0">\n`;
          xml += `          <SMARTCRITERIA>\n`;
          xml += `            <CRITERIA Field="Comment" Operator="Contains" Value="${tag}"/>\n`;
          xml += `          </SMARTCRITERIA>\n`;
          xml += `        </SMARTLIST>\n`;
          xml += `      </NODE>\n`;
        }
      });
      
      xml += `    </NODE>\n`;
    });

    // Add combination playlists
    xml += `    <NODE Type="1" Name="COMBO PLAYLISTS" Count="0" Expanded="1">\n`;
    
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
        xml += `      <NODE Type="2" Name="${combo.name}" Count="0" Expanded="0">\n`;
        xml += `        <SMARTLIST Name="${combo.name}" Count="0">\n`;
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

  private getRekordboxDataPath(): string {
    const platform = os.platform();
    const homeDir = os.homedir();
    
    if (platform === 'darwin') {
      // macOS
      return path.join(homeDir, 'Library', 'Application Support', 'Pioneer', 'rekordbox');
    } else if (platform === 'win32') {
      // Windows
      return path.join(homeDir, 'AppData', 'Roaming', 'Pioneer', 'rekordbox');
    } else {
      throw new Error(`Unsupported platform: ${platform}`);
    }
  }

  async createSmartPlaylists(): Promise<void> {
    try {
      const xml = this.generateRekordboxXML();
      const outputPath = path.join(process.cwd(), 'rekordbox_smart_playlists_import.xml');
      
      await fs.promises.writeFile(outputPath, xml, 'utf-8');
      
      console.log(`✅ Created Rekordbox XML: ${outputPath}`);
      console.log(`\n📋 To import into Rekordbox:`);
      console.log(`1. Close Rekordbox completely`);
      console.log(`2. Open Rekordbox`);
      console.log(`3. File → Library → Import Library`);
      console.log(`4. Select: ${outputPath}`);
      console.log(`5. Choose "Merge" when prompted`);
      console.log(`\n⚠️  IMPORTANT: This will import as a library, not individual playlists`);
      console.log(`   The smart playlists will appear in your Rekordbox library`);
      
      // Also create individual playlist files for manual import
      await this.createIndividualPlaylists();
      
    } catch (error) {
      console.error('❌ Error creating smart playlists:', error);
    }
  }

  private async createIndividualPlaylists(): Promise<void> {
    const playlistDir = path.join(process.cwd(), 'rekordbox_smart_playlist_files');
    await fs.promises.mkdir(playlistDir, { recursive: true });

    const tags = Array.from(this.allTags).sort();
    
    for (const tag of tags) {
      const playlistName = tag.split('-').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ');
      
      const xml = `<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
  <PLAYLISTS>
    <NODE Type="2" Name="${playlistName}" Count="0" Expanded="0">
      <SMARTLIST Name="${playlistName}" Count="0">
        <SMARTCRITERIA>
          <CRITERIA Field="Comment" Operator="Contains" Value="${tag}"/>
        </SMARTCRITERIA>
      </SMARTLIST>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>`;

      const filename = `${playlistName.replace(/[^a-zA-Z0-9\s]/g, '').replace(/\s+/g, '_')}.xml`;
      const filepath = path.join(playlistDir, filename);
      
      await fs.promises.writeFile(filepath, xml, 'utf-8');
    }

    console.log(`\n📁 Created ${tags.length} individual playlist files in:`);
    console.log(`   ${playlistDir}`);
    console.log(`\n💡 Alternative import method:`);
    console.log(`   File → Library → Import Library → Select individual XML files`);
  }
}

async function main() {
  const basePath = '/Users/ethansarif-kattan/Music/ALLDJ/';
  const metadataPath = path.join(basePath, 'music_collection_metadata.json');

  console.log('🎵 Creating Rekordbox Smart Playlists');
  console.log('====================================');

  const creator = new RekordboxSmartPlaylistCreator(metadataPath);
  
  try {
    await creator.loadMetadata();
    await creator.createSmartPlaylists();
    
    console.log('\n✅ Smart playlist creation complete!');
    
  } catch (error) {
    console.error('❌ Error:', error);
  }
}

if (require.main === module) {
  main().catch(console.error);
}