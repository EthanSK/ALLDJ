# LALAL.AI Vocal & Instrumental Extractor

This TypeScript script provides automated vocal and instrumental extraction for your FLAC music collection using the LALAL.AI API.

## Features

- ✅ Batch processing of all FLAC files
- ✅ Multiple stem extraction (vocals, drums, bass, etc.)
- ✅ High-quality Phoenix splitter support
- ✅ Enhanced processing options
- ✅ Noise reduction and dereverberation
- ✅ Automatic file organization
- ✅ Progress tracking and error handling
- ✅ Account limits checking

## Setup

### 1. Get LALAL.AI API Key

1. Visit [LALAL.AI API](https://www.lalal.ai/api/)
2. Sign up or log in to your account
3. Get your API license key

### 2. Environment Configuration

Add your API key to the `.env` file in the project root:

```bash
LALAL_API_KEY=your_api_key_here
```

### 3. Install Dependencies

Make sure you have the required dependencies installed:

```bash
npm install
```

## Usage

### Basic Usage - Extract Vocals Only

```bash
npm run extract
```

This will:
- Process all FLAC files in `/Users/ethansarif-kattan/Music/ALLDJ/flac/`
- Extract vocals using the Phoenix splitter (highest quality)
- Save results to `/Users/ethansarif-kattan/Music/ALLDJ/extracted/`

### Custom Processing

Edit `src/lalal-example.ts` to customize:

```typescript
const config: ProcessingConfig[] = [
  {
    stem: 'vocals',
    splitter: 'phoenix',
    enhanced_processing_enabled: true,
  },
  {
    stem: 'drum',
    splitter: 'phoenix',
  },
  {
    stem: 'bass',
    splitter: 'phoenix',
  }
];
```

### Available Stems

- `vocals` - Vocal extraction
- `voice` - Voice with noise reduction options
- `drum` - Drum extraction
- `piano` - Piano extraction
- `bass` - Bass extraction
- `electric_guitar` - Electric guitar
- `acoustic_guitar` - Acoustic guitar
- `synthesizer` - Synthesizer
- `strings` - String instruments
- `wind` - Wind instruments

### Available Splitters

- `phoenix` - Highest quality (supports all stems)
- `orion` - Good quality (supports most stems)
- `perseus` - Fast processing (limited stems)

## Output Structure

Files are organized as follows:

```
extracted/
├── song_name_1/
│   ├── song_name_1_vocals.wav
│   └── song_name_1_instrumental.wav
├── song_name_2/
│   ├── song_name_2_vocals.wav
│   ├── song_name_2_drum.wav
│   ├── song_name_2_bass.wav
│   └── song_name_2_instrumental.wav
```

## Advanced Options

### Processing Configuration

```typescript
interface ProcessingConfig {
  stem: 'vocals' | 'voice' | 'drum' | 'piano' | 'bass' | 'electric_guitar' | 'acoustic_guitar' | 'synthesizer' | 'strings' | 'wind';
  splitter?: 'phoenix' | 'orion' | 'perseus';
  dereverb_enabled?: boolean;
  enhanced_processing_enabled?: boolean;
  noise_cancelling_level?: 0 | 1 | 2; // Only for 'voice' stem
}
```

### Voice Processing Example

```typescript
const voiceConfig: ProcessingConfig[] = [
  {
    stem: 'voice',
    splitter: 'phoenix',
    dereverb_enabled: true,
    noise_cancelling_level: 1, // 0=mild, 1=normal, 2=aggressive
  }
];
```

## API Limits

The script automatically checks your account limits before processing. Make sure you have sufficient processing time available.

Check limits manually:
```typescript
const extractor = new LalalAIExtractor();
await extractor.checkLimits();
```

## Error Handling

- **Continue on Error**: By default, if one file fails, processing continues with the next
- **Stop on Error**: Set `continueOnError: false` to stop on first error
- **Rate Limiting**: 5-second delay between files to respect API limits

## Safety Features

- ✅ Dry-run capability for testing
- ✅ File existence checks
- ✅ Safe filename generation
- ✅ Output directory creation
- ✅ API key validation
- ✅ Comprehensive error messages

## Cost Considerations

- Each file uses processing time from your LALAL.AI account
- Phoenix splitter provides highest quality but uses more time
- Check your limits before starting large batches
- Consider starting with a test file first

## Examples

### Process Single File (Testing)

```typescript
const extractor = new LalalAIExtractor();
await extractor.processFile('path/to/test.flac', [
  { stem: 'vocals', splitter: 'phoenix' }
]);
```

### Custom Directories

```typescript
const extractor = new LalalAIExtractor(
  'your_api_key',
  '/path/to/flac/files',
  '/path/to/output'
);
```

## Troubleshooting

### Common Issues

1. **API Key Not Found**
   ```
   Error: LALAL_API_KEY environment variable is required
   ```
   Solution: Add your API key to `.env` file

2. **File Not Found**
   ```
   Error: FLAC directory not found
   ```
   Solution: Check the FLAC directory path is correct

3. **Upload Failed**
   ```
   Error: Upload failed: No file name
   ```
   Solution: Usually a temporary issue, try again

4. **Processing Timeout**
   ```
   Error: Task timed out
   ```
   Solution: Large files may take longer, increase timeout in code

### Getting Help

- Check the [LALAL.AI API documentation](https://www.lalal.ai/api/help/)
- Verify your account has sufficient processing time
- Test with a single small file first
- Check network connectivity

## License

MIT License - see project root for details.
