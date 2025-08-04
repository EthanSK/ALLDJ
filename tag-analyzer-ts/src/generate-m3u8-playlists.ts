#!/usr/bin/env ts-node

import * as fs from 'fs';
import * as path from 'path';

interface TrackMetadata {
  relative_path: string;
  filename: string;
  artist?: string;
  title?: string;
  assigned_tags?: string[];
  duration_seconds?: number;
}

interface MetadataCollection {
  tracks: TrackMetadata[];
}

class M3U8PlaylistGenerator {
  private basePath: string;
  private metadataPath: string;
  private outputDir: string;
  private tracks: TrackMetadata[] = [];

  constructor(basePath: string, metadataPath: string, outputDir: string) {
    this.basePath = basePath;
    this.metadataPath = metadataPath;
    this.outputDir = outputDir;
  }

  async loadMetadata(): Promise<void> {
    const content = await fs.promises.readFile(this.metadataPath, 'utf-8');
    const data: MetadataCollection = JSON.parse(content);
    this.tracks = data.tracks;
    console.log(`📚 Loaded ${this.tracks.length} tracks`);
  }

  private formatDuration(seconds: number): string {
    return Math.round(seconds).toString();
  }

  private createM3U8Content(tracks: TrackMetadata[], playlistName: string): string {
    let content = '#EXTM3U\n';
    content += `# ${playlistName} - Generated from intelligent tags\n`;
    
    tracks.forEach(track => {
      const duration = track.duration_seconds ? this.formatDuration(track.duration_seconds) : '0';
      const artist = track.artist || 'Unknown Artist';
      const title = track.title || track.filename;
      const filePath = path.join(this.basePath, track.relative_path);
      
      content += `#EXTINF:${duration},${artist} - ${title}\n`;
      content += `${filePath}\n`;
    });
    
    return content;
  }

  private async ensureDirectoryExists(dirPath: string): Promise<void> {
    try {
      await fs.promises.access(dirPath);
    } catch {
      await fs.promises.mkdir(dirPath, { recursive: true });
    }
  }

  private getTracksWithTag(tag: string): TrackMetadata[] {
    return this.tracks.filter(track => 
      track.assigned_tags && track.assigned_tags.includes(tag)
    );
  }

  private getTracksWithTags(tags: string[]): TrackMetadata[] {
    return this.tracks.filter(track => 
      track.assigned_tags && tags.every(tag => track.assigned_tags!.includes(tag))
    );
  }

  async generateAllPlaylists(): Promise<void> {
    await this.ensureDirectoryExists(this.outputDir);

    const categories = {
      '01_DOPAMINE_SOURCE': [
        'nostalgic-hit',
        'euphoric-melody', 
        'emotional-depth',
        'textural-beauty',
        'rhythmic-hypnosis',
        'harmonic-surprise',
        'vocal-magic',
        'psychedelic-journey',
        'sophisticated-groove'
      ],
      
      '02_MIXING_ROLE': [
        'rhythmic-foundation',
        'melodic-overlay',
        'bridge-element',
        'texture-add',
        'anchor-track',
        'wildcard',
        'transition-tool',
        'emotional-crescendo',
        'palate-cleanser'
      ],
      
      '03_DANCEABILITY': [
        'instant-dancefloor',
        'crowd-pleaser',
        'peak-time',
        'body-mover',
        'head-nodder',
        'non-danceable-standalone'
      ],
      
      '04_ENERGY_DYNAMICS': [
        'energetic',
        'energy-injector',
        'energy-sustainer',
        'energy-shifter',
        'instant-impact',
        'slow-burn',
        'lifts-mood'
      ],
      
      '05_GENRES': [
        'electronic-dance',
        'electronic-experimental',
        'electronic-ambient',
        'rock-psychedelic',
        'rock-indie',
        'rock-classic',
        'hip-hop-conscious',
        'hip-hop-experimental',
        'pop-sophisticated',
        'world-fusion'
      ],
      
      '06_ERA_BRIDGING': [
        'timeless-classic',
        'contemporary-classic',
        'retro-modern',
        'genre-crossover',
        'cultural-moment',
        'generational-bridge'
      ],
      
      '07_GENERATIONAL_APPEAL': [
        'gen-z-nostalgia',
        'millennial-comfort',
        'gen-x-wisdom',
        'boomer-classic',
        'indie-cred',
        'mainstream-crossover'
      ],
      
      '08_MIXING_COMPATIBILITY': [
        'layer-friendly',
        'breakdown-rich',
        'loop-gold',
        'mashup-ready',
        'beatmatched-friendly',
        'smooth-transitions'
      ],
      
      '09_SET_POSITIONING': [
        'set-opener',
        'warm-up',
        'peak-time',
        'emotional-peak',
        'comedown',
        'sunrise',
        'interlude'
      ],
      
      '10_PSYCHEDELIC_CONSCIOUSNESS': [
        'mind-expanding',
        'reality-bending',
        'time-dilation',
        'dream-logic',
        'color-synesthesia',
        'meditation-inducer'
      ],
      
      '11_PERSONAL_TAGS': [
        'deep',
        'dopamine',
        'funny',
        'drum-bass-layer'
      ]
    };

    // Generate single-tag playlists
    for (const [categoryName, tags] of Object.entries(categories)) {
      const categoryDir = path.join(this.outputDir, categoryName);
      await this.ensureDirectoryExists(categoryDir);
      
      for (const tag of tags) {
        const tracks = this.getTracksWithTag(tag);
        if (tracks.length > 0) {
          const playlistName = tag.split('-').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
          ).join(' ');
          
          const content = this.createM3U8Content(tracks, playlistName);
          const filename = `${playlistName.replace(/[^a-zA-Z0-9\s]/g, '').replace(/\s+/g, '_')}.m3u8`;
          const filepath = path.join(categoryDir, filename);
          
          await fs.promises.writeFile(filepath, content);
          console.log(`✅ Created: ${filename} (${tracks.length} tracks)`);
        }
      }
    }

    // Generate combination playlists
    const comboDir = path.join(this.outputDir, '12_COMBO_PLAYLISTS');
    await this.ensureDirectoryExists(comboDir);

    const combos = [
      { name: 'Dancefloor_Classics', tags: ['instant-dancefloor', 'timeless-classic'] },
      { name: 'Energetic_Crowd_Pleasers', tags: ['energetic', 'crowd-pleaser'] },
      { name: 'Euphoric_Peak_Time', tags: ['euphoric-melody', 'peak-time'] },
      { name: 'Nostalgic_Dancefloor', tags: ['nostalgic-hit', 'instant-dancefloor'] },
      { name: 'Psychedelic_Journey_Layers', tags: ['psychedelic-journey', 'layer-friendly'] },
      { name: 'Electronic_Dance_Foundations', tags: ['electronic-dance', 'rhythmic-foundation'] },
      { name: 'Vocal_Magic_Overlays', tags: ['vocal-magic', 'melodic-overlay'] },
      { name: 'Contemporary_Layer_Friendly', tags: ['contemporary-classic', 'layer-friendly'] },
      { name: 'Deep_Emotional_Journeys', tags: ['deep', 'emotional-depth'] },
      { name: 'Dopamine_Energy_Hits', tags: ['dopamine', 'energetic'] }
    ];

    for (const combo of combos) {
      const tracks = this.getTracksWithTags(combo.tags);
      if (tracks.length > 0) {
        const content = this.createM3U8Content(tracks, combo.name.replace(/_/g, ' '));
        const filepath = path.join(comboDir, `${combo.name}.m3u8`);
        
        await fs.promises.writeFile(filepath, content);
        console.log(`✅ Created combo: ${combo.name}.m3u8 (${tracks.length} tracks)`);
      }
    }

    console.log(`\n🎵 Generated playlists in: ${this.outputDir}`);
    console.log(`📁 Import these M3U8 files into Rekordbox via File > Import > Import Playlist`);
  }
}

async function main() {
  const basePath = '/Users/ethansarif-kattan/Music/ALLDJ/';
  const metadataPath = path.join(basePath, 'music_collection_metadata.json');
  const outputDir = path.join(basePath, 'rekordbox_playlists');

  console.log('🎵 Generating M3U8 Playlists for Rekordbox');
  console.log('=========================================');

  const generator = new M3U8PlaylistGenerator(basePath, metadataPath, outputDir);
  
  try {
    await generator.loadMetadata();
    await generator.generateAllPlaylists();
    
    console.log('\n✅ All playlists generated successfully!');
    console.log('\n📋 To import into Rekordbox:');
    console.log('1. Open Rekordbox');
    console.log('2. File > Import > Import Playlist');
    console.log(`3. Navigate to: ${path.join(basePath, 'rekordbox_playlists')}`);
    console.log('4. Select and import the M3U8 files you want');
    
  } catch (error) {
    console.error('❌ Error generating playlists:', error);
  }
}

if (require.main === module) {
  main().catch(console.error);
}