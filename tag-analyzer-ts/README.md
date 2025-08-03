# Music Tag Analyzer (TypeScript)

Analyze music tracks and assign sophisticated tags using Claude Opus 4 with extended thinking and web search.

## Setup

```bash
cd tag-analyzer-ts
npm install
```

## Usage

Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY="your_api_key_here"
```

Run the analyzer:
```bash
# Auto-analyze first untagged track
npm run analyze

# Or analyze a specific track
npm run analyze "02-10 Don't Matter To Me (1).flac"

# Development mode
npm run dev
```

## Features

- Uses Claude Opus 4 with extended thinking (2048 token budget)
- Web search capability for track research
- Auto-selects first untagged track when no filename provided
- Adds confidence scores and research notes to metadata
- Updates `music_collection_metadata.json` with new tags

## Scripts

- `npm run build` - Compile TypeScript to JavaScript
- `npm run start` - Run compiled JavaScript
- `npm run dev` - Run TypeScript directly with ts-node
- `npm run analyze` - Build and run the analyzer