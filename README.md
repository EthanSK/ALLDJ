# Music Tag Analyzer

AI-powered music tagging system using OpenAI o3 reasoning models to analyze tracks and assign sophisticated curator-quality tags for DJ and music library management.

## 🚀 Quick Start

**Start from the project root directory** (where this README is located):

### Step 1: Install Dependencies

```bash
# Navigate to the TypeScript analyzer directory
cd tag-analyzer-ts

# Install required packages
npm install
```

### Step 2: Set Up API Keys

Create a `.env` file in the `tag-analyzer-ts/` directory:

```bash
# Create the .env file
touch tag-analyzer-ts/.env
```

Add your API keys to `tag-analyzer-ts/.env`:

```env
# Required: OpenAI API key (for o3 reasoning model)
OPENAI_API_KEY=sk-proj-your_openai_key_here

# Optional: Anthropic API key (fallback)
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here
```

### Step 3: Generate Fresh Metadata (First Time Setup)

If you're starting fresh or want to clear existing tags:

```bash
# Generate skeleton metadata from your FLAC files
cd tag-analyzer-ts
npm run generate:skeleton --force

# This will:
# ✅ Scan your ../flac directory for all .flac files  
# ✅ Create ../music_collection_metadata.json with empty tags
# ⚠️  OVERWRITES existing metadata file (use --force flag)
```

### Step 4: Run Batch Analysis

```bash
# Make sure you're in the tag-analyzer-ts directory
cd tag-analyzer-ts

# Analyze 1 track (default: OpenAI o3 with reasoning)
npm run analyze:batch 1

# Analyze 5 tracks
npm run analyze:batch 5

# Analyze 10 tracks (good for moderate sessions)
npm run analyze:batch 10

# Analyze 25 tracks (larger batch - takes longer)
npm run analyze:batch 25

# Use Anthropic Claude instead of OpenAI
npm run analyze:batch 5 --anthropic
```

**📏 Batch Size Guidelines:**
- **1-5 tracks**: Quick testing, single songs
- **10-20 tracks**: Standard daily tagging session
- **25-50 tracks**: Large batch processing (plan for longer runtime)
- **50+ tracks**: Extended analysis session (several hours)

**⏱️ Time Estimates:**
- ~2-3 minutes per track with OpenAI o3 reasoning
- ~1-2 minutes per track with Anthropic Claude
- Includes 2-second delays between tracks to avoid rate limits

## 🎵 What It Does

- **AI Analysis**: Uses OpenAI o3 reasoning model with web search for deep musical analysis
- **Curator Tags**: Assigns 10-15 sophisticated tags from a curated taxonomy for DJ use
- **Key Detection**: Automatically detects and fills in missing musical keys (e.g., "C Major", "F# Minor")
- **Research Notes**: Provides detailed insights about track history, production, and DJ utility
- **Confidence Scoring**: Each analysis includes a confidence score (0-100%)
- **Metadata Integration**: Updates your music collection metadata automatically

## 🏷️ Example Output

```
✅ MIKA - Grace Kelly
   Tags (13): euphoric-melody, vocal-magic, harmonic-surprise, crowd-pleaser, 
             sing-along-potential, instant-impact, warm-up, mainstream-crossover, 
             pop-sophisticated, dense-production, mashup-ready, vocal-prominent, 
             nostalgic-hit
   Confidence: 87%
   🎹 Detected key: G Major
   Research Notes: Producer Greg Wells gives the track a glossy, brick-walled sheen 
                   with stacked piano, handclaps and multitracked choir-style backing 
                   that evokes Freddie Mercury...
```

## 🔧 Available Commands

**All commands should be run from the `tag-analyzer-ts/` directory** (after `cd tag-analyzer-ts` from project root):

**🏗️ Setup & Generation:**
- `npm run generate:skeleton --force` - Generate fresh metadata skeleton from FLAC files

**🎵 Analysis Commands:**
- `npm run analyze:batch [number]` - Analyze batch of tracks (default: OpenAI o3)
- `npm run analyze:batch [number] --anthropic` - Use Anthropic Claude instead
- `npm run analyze:batch 1` - Quick single track analysis
- `npm run analyze:batch 10` - Standard batch (10 tracks)
- `npm run analyze:batch 50` - Large batch processing

**🛠️ Development:**
- `npm run build` - Compile TypeScript
- `npm run dev` - Development mode

**💡 Pro Tips:**
- Start with small batches (1-5) to test your setup
- Use Ctrl+C to gracefully stop after current track
- Check your API key balance before large batches
- The system automatically finds untagged tracks to analyze

## 🧠 AI Models

- **Default**: OpenAI o3 with reasoning + web search
- **Fallback**: Anthropic Claude Sonnet 4 with thinking
- **Features**: Extended reasoning, web research, structured JSON output

## 📁 Project Structure

```
ALLDJ/
├── README.md                    # This file
├── flac/                       # Your FLAC music files
├── music_collection_metadata.json # Generated metadata with AI tags
├── tag taxonomy.txt            # Curated tag taxonomy
└── tag-analyzer-ts/           # TypeScript analyzer
    ├── src/                   # Source code
    ├── package.json          # Dependencies
    └── .env                  # API keys (create this)
```