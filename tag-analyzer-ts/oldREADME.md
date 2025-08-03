# Music Tag Analyzer

AI-powered music tagging system using OpenAI o3 reasoning models to analyze tracks and assign sophisticated curator-quality tags for DJ and music library management.

## 🚀 Quick Start

### Step 0: Generate Fresh Metadata (First Time Setup)

If you're starting fresh or want to clear existing tags:

```bash
# Generate skeleton metadata from your FLAC files
npm run generate:skeleton --force

# This will:
# ✅ Scan your /flac directory for all .flac files  
# ✅ Create music_collection_metadata.json with empty tags
# ⚠️  OVERWRITES existing metadata file (use --force flag)
```

### Step 1: Install Dependencies

```bash
cd tag-analyzer-ts
npm install
```

```bash
# Required: OpenAI API key (for o3 reasoning model)
OPENAI_API_KEY=sk-proj-your_openai_key_here

# Optional: Anthropic API key (fallback)
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here
```
Add these to `.env` file in the project root.

```bash
# Analyze 1 track (default: OpenAI o3 with reasoning)
npm run analyze:batch 1

# Analyze 5 tracks
npm run analyze:batch 5

# Use Anthropic Claude instead
npm run analyze:batch 1 --anthropic
```

## 🎵 What It Does

- **AI Analysis**: Uses OpenAI o3 reasoning model with web search for deep musical analysis
- **Curator Tags**: Assigns 10-15 sophisticated tags from a curated taxonomy for DJ use
- **Research Notes**: Provides detailed insights about track history, production, and DJ utility
- **Confidence Scoring**: Each analysis includes a confidence score (0-100%)
- **Metadata Integration**: Updates your music collection metadata automatically

## 🏷️ Example Output

```
✅ David Bowie - Conversation Piece (2019 Mix)
   Tags (12): remix, rock-classic, contemporary-classic, emotional-depth, 
             vocal-magic, textural-beauty, bridge-element, layer-friendly, 
             mood-shifter, provides-release, crisp-digital, energy-injector
   Confidence: 85%
   Research Notes: The 2019 mix revisits Bowie's classic rock roots in modern, 
                   digitally crisp production...
```

## 🔧 Available Commands

- `npm run generate:skeleton --force` - Generate fresh metadata skeleton from FLAC files
- `npm run analyze:batch [number]` - Analyze batch of tracks (default: OpenAI o3)
- `npm run analyze:batch [number] --anthropic` - Use Anthropic Claude instead
- `npm run build` - Compile TypeScript
- `npm run dev` - Development mode

## 🧠 AI Models

- **Default**: OpenAI o3 with reasoning + web search
- **Fallback**: Anthropic Claude Sonnet 4 with thinking
- **Features**: Extended reasoning, web research, structured JSON output