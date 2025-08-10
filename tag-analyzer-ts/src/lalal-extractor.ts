#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import dotenv from "dotenv";
dotenv.config();

// LALAL.AI API Types
interface LalalUploadResponse {
  status: 'success' | 'error';
  id?: string;
  size?: number;
  duration?: number;
  expires?: number;
  error?: string;
}

interface LalalSplitResponse {
  status: 'success' | 'error';
  task_id?: string;
  error?: string;
}

interface LalalCheckTaskResponse {
  status: 'success' | 'error';
  result?: {
    [fileId: string]: {
      status: 'success' | 'error';
      name?: string;
      size?: number;
      duration?: number;
      splitter?: 'phoenix' | 'orion' | 'perseus';
      stem?: string;
      split?: {
        duration: number;
        stem: string;
        stem_track: string;
        stem_track_size: number;
        back_track: string;
        back_track_size: number;
      };
      task?: {
        state: 'success' | 'error' | 'progress' | 'cancelled';
        error?: string;
        progress?: number;
      };
      error?: string;
    };
  };
  error?: string;
}

interface ProcessingConfig {
  stem: 'vocals' | 'voice' | 'drum' | 'piano' | 'bass' | 'electric_guitar' | 'acoustic_guitar' | 'synthesizer' | 'strings' | 'wind';
  splitter?: 'phoenix' | 'orion' | 'perseus';
  dereverb_enabled?: boolean;
  enhanced_processing_enabled?: boolean;
  noise_cancelling_level?: 0 | 1 | 2; // Only for 'voice' stem
}

class LalalAIExtractor {
  private apiKey: string;
  private baseUrl: string = 'https://www.lalal.ai/api';
  private flacDir: string;
  private outputDir: string;

  constructor(apiKey?: string, flacDir?: string, outputDir?: string) {
    this.apiKey = apiKey || process.env.LALAL_API_KEY || '';
    if (!this.apiKey) {
      throw new Error('LALAL.AI API key is required. Set LALAL_API_KEY environment variable or pass it as parameter.');
    }

    this.flacDir = flacDir || '/Users/ethansarif-kattan/Music/ALLDJ/flac';
    this.outputDir = outputDir || '/Users/ethansarif-kattan/Music/ALLDJ/extracted';

    // Create output directory if it doesn't exist
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
  }

  private async makeRequest(endpoint: string, options: RequestInit): Promise<any> {
    const url = `${this.baseUrl}${endpoint}`;
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Authorization': `license ${this.apiKey}`,
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`Request failed for ${endpoint}:`, error);
      throw error;
    }
  }

  private async uploadFile(filePath: string): Promise<LalalUploadResponse> {
    console.log(`Uploading ${path.basename(filePath)}...`);
    
    const fileBuffer = fs.readFileSync(filePath);
    const fileName = path.basename(filePath);

    const response = await this.makeRequest('/upload/', {
      method: 'POST',
      headers: {
        'Content-Disposition': `attachment; filename="${fileName}"`,
      },
      body: fileBuffer,
    });

    console.log(`Upload response for ${fileName}:`, response);
    return response;
  }

  private async startSplitTask(fileId: string, config: ProcessingConfig): Promise<LalalSplitResponse> {
    console.log(`Starting split task for file ID: ${fileId} with stem: ${config.stem}`);

    const params = JSON.stringify([{
      id: fileId,
      stem: config.stem,
      ...(config.splitter && { splitter: config.splitter }),
      ...(config.dereverb_enabled !== undefined && { dereverb_enabled: config.dereverb_enabled }),
      ...(config.enhanced_processing_enabled !== undefined && { enhanced_processing_enabled: config.enhanced_processing_enabled }),
      ...(config.noise_cancelling_level !== undefined && { noise_cancelling_level: config.noise_cancelling_level }),
    }]);

    const formData = new URLSearchParams();
    formData.append('params', params);

    const response = await this.makeRequest('/split/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    console.log(`Split task response:`, response);
    return response;
  }

  private async checkTaskStatus(fileId: string): Promise<LalalCheckTaskResponse> {
    const formData = new URLSearchParams();
    formData.append('id', fileId);

    const response = await this.makeRequest('/check/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    return response;
  }

  private async downloadFile(url: string, outputPath: string): Promise<void> {
    console.log(`Downloading to ${outputPath}...`);
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      const buffer = await response.arrayBuffer();
      fs.writeFileSync(outputPath, Buffer.from(buffer));
      console.log(`Downloaded: ${outputPath}`);
    } catch (error) {
      console.error(`Download failed for ${outputPath}:`, error);
      throw error;
    }
  }

  private async waitForCompletion(fileId: string, maxWaitTime: number = 300000): Promise<LalalCheckTaskResponse> {
    const startTime = Date.now();
    const checkInterval = 10000; // Check every 10 seconds

    while (Date.now() - startTime < maxWaitTime) {
      const status = await this.checkTaskStatus(fileId);
      
      if (status.status === 'error') {
        throw new Error(`Task failed: ${status.error}`);
      }

      if (status.result && status.result[fileId]) {
        const fileResult = status.result[fileId];
        
        if (fileResult.status === 'error') {
          throw new Error(`File processing failed: ${fileResult.error}`);
        }

        if (fileResult.task) {
          if (fileResult.task.state === 'success' && fileResult.split) {
            console.log('Processing completed successfully!');
            return status;
          }
          
          if (fileResult.task.state === 'error') {
            throw new Error(`Task error: ${fileResult.task.error}`);
          }
          
          if (fileResult.task.state === 'cancelled') {
            throw new Error('Task was cancelled');
          }
          
          if (fileResult.task.state === 'progress') {
            console.log(`Progress: ${fileResult.task.progress}%`);
          }
        }
      }

      await new Promise(resolve => setTimeout(resolve, checkInterval));
    }

    throw new Error('Task timed out');
  }

  private getFlacFiles(): string[] {
    if (!fs.existsSync(this.flacDir)) {
      throw new Error(`FLAC directory not found: ${this.flacDir}`);
    }

    const files = fs.readdirSync(this.flacDir)
      .filter(file => file.toLowerCase().endsWith('.flac'))
      .map(file => path.join(this.flacDir, file));

    console.log(`Found ${files.length} FLAC files`);
    return files;
  }

  private getSafeFileName(originalName: string): string {
    return originalName.replace(/[^a-zA-Z0-9.-]/g, '_');
  }

  async processFile(filePath: string, configs: ProcessingConfig[]): Promise<void> {
    const fileName = path.basename(filePath, '.flac');
    const safeFileName = this.getSafeFileName(fileName);
    
    console.log(`\n=== Processing: ${fileName} ===`);

    try {
      // Upload file
      const uploadResult = await this.uploadFile(filePath);
      if (uploadResult.status === 'error') {
        throw new Error(`Upload failed: ${uploadResult.error}`);
      }

      const fileId = uploadResult.id!;
      console.log(`File uploaded with ID: ${fileId}`);

      // Process each configuration
      for (const config of configs) {
        console.log(`\n--- Processing ${config.stem} extraction ---`);
        
        // Start split task
        const splitResult = await this.startSplitTask(fileId, config);
        if (splitResult.status === 'error') {
          throw new Error(`Split task failed: ${splitResult.error}`);
        }

        // Wait for completion
        const finalResult = await this.waitForCompletion(fileId);
        const fileResult = finalResult.result![fileId];

        if (fileResult.split) {
          // Create separate vocal and instrumental directories
          const vocalDir = path.join(this.outputDir, 'vocal');
          const instrumentalDir = path.join(this.outputDir, 'instrumental');
          
          if (!fs.existsSync(vocalDir)) {
            fs.mkdirSync(vocalDir, { recursive: true });
          }
          if (!fs.existsSync(instrumentalDir)) {
            fs.mkdirSync(instrumentalDir, { recursive: true });
          }

          // Download stem track (e.g., vocals) to vocal folder
          const stemFileName = `${safeFileName}_${config.stem}.wav`;
          const stemPath = path.join(vocalDir, stemFileName);
          await this.downloadFile(fileResult.split.stem_track, stemPath);

          // Download back track (instrumental) to instrumental folder
          const backFileName = `${safeFileName}_instrumental.wav`;
          const backPath = path.join(instrumentalDir, backFileName);
          await this.downloadFile(fileResult.split.back_track, backPath);

          console.log(`✅ Completed ${config.stem} extraction for ${fileName}`);
          console.log(`   Vocal: ${stemPath}`);
          console.log(`   Instrumental: ${backPath}`);
        }
      }

    } catch (error) {
      console.error(`❌ Failed to process ${fileName}:`, error);
      throw error;
    }
  }

  async processAllFiles(configs: ProcessingConfig[], continueOnError: boolean = true): Promise<void> {
    const flacFiles = this.getFlacFiles();
    
    console.log(`Starting batch processing of ${flacFiles.length} files...`);
    console.log(`Output directory: ${this.outputDir}`);
    
    let processed = 0;
    let failed = 0;

    for (let i = 0; i < flacFiles.length; i++) {
      const file = flacFiles[i];
      
      try {
        console.log(`\n[${i + 1}/${flacFiles.length}] Processing: ${path.basename(file)}`);
        await this.processFile(file, configs);
        processed++;
      } catch (error) {
        failed++;
        console.error(`Failed to process ${path.basename(file)}:`, error);
        
        if (!continueOnError) {
          console.log('Stopping due to error (continueOnError = false)');
          break;
        }
      }

      // Add a small delay between files to be respectful to the API
      if (i < flacFiles.length - 1) {
        console.log('Waiting 5 seconds before next file...');
        await new Promise(resolve => setTimeout(resolve, 5000));
      }
    }

    console.log(`\n=== BATCH PROCESSING COMPLETE ===`);
    console.log(`Processed: ${processed}/${flacFiles.length}`);
    console.log(`Failed: ${failed}/${flacFiles.length}`);
  }

  async checkLimits(): Promise<void> {
    try {
      const response = await fetch(`https://www.lalal.ai/billing/get-limits/?key=${this.apiKey}`);
      const data = await response.json();
      
      if (data.status === 'success') {
        console.log('\n=== ACCOUNT LIMITS ===');
        console.log(`Plan: ${data.option}`);
        console.log(`Email: ${data.email}`);
        console.log(`Duration limit: ${data.process_duration_limit} minutes`);
        console.log(`Duration used: ${data.process_duration_used} minutes`);
        console.log(`Duration left: ${data.process_duration_left} minutes`);
      } else {
        console.error('Failed to check limits:', data.error);
      }
    } catch (error) {
      console.error('Error checking limits:', error);
    }
  }
}

// Main execution
async function main() {
  try {
    const extractor = new LalalAIExtractor();

    // Check account limits first
    await extractor.checkLimits();

    // Define extraction configurations
    const configs: ProcessingConfig[] = [
      {
        stem: 'vocals',
        splitter: 'phoenix', // Best quality
        enhanced_processing_enabled: true,
      },
      // Uncomment if you want additional stems
      // {
      //   stem: 'drum',
      //   splitter: 'phoenix',
      // },
      // {
      //   stem: 'bass',
      //   splitter: 'phoenix',
      // },
    ];

    console.log('\n=== LALAL.AI FLAC EXTRACTOR ===');
    console.log('Configurations:');
    configs.forEach((config, index) => {
      console.log(`  ${index + 1}. ${config.stem} (${config.splitter || 'auto'})`);
    });

    // Process all files
    await extractor.processAllFiles(configs, true);

  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

// Command line interface
if (require.main === module) {
  // Check if API key is provided
  if (!process.env.LALAL_API_KEY) {
    console.error('Error: LALAL_API_KEY environment variable is required');
    console.error('Please add your LALAL.AI API key to your .env file:');
    console.error('LALAL_API_KEY=your_api_key_here');
    process.exit(1);
  }

  main().catch(error => {
    console.error('Unhandled error:', error);
    process.exit(1);
  });
}

export { LalalAIExtractor, ProcessingConfig };
