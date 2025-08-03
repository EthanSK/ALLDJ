import Anthropic from "@anthropic-ai/sdk";
import * as fs from "fs";
import * as path from "path";
import {
  Track,
  MusicMetadata,
  AnalysisResult,
  TrackAnalysisResult,
} from "./types";

export class MusicTagAnalyzer {
  private client: Anthropic;
  private tagTaxonomy: string;

  constructor(apiKey?: string) {
    const key = apiKey || process.env.ANTHROPIC_API_KEY;
    if (!key) {
      throw new Error(
        "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable or pass apiKey parameter"
      );
    }

    this.client = new Anthropic({ apiKey: key });
    this.tagTaxonomy = this.loadTagTaxonomy();
  }

  private loadTagTaxonomy(): string {
    try {
      const taxonomyPath = path.resolve(__dirname, "../../tag taxonomy.txt");
      return fs.readFileSync(taxonomyPath, "utf-8");
    } catch (error) {
      throw new Error("tag taxonomy.txt not found in parent directory");
    }
  }

  private getValidTags(): string[] {
    // Extract all valid tags from the taxonomy
    const taxonomyLines = this.tagTaxonomy.split("\n");
    const validTags: string[] = [];

    for (const line of taxonomyLines) {
      const trimmed = line.trim();
      // Look for lines that start with a tag (word followed by " - ")
      const tagMatch = trimmed.match(/^([a-z-]+)\s*-/);
      if (tagMatch) {
        validTags.push(tagMatch[1]);
      }
    }

    return validTags;
  }

  private validateTags(tags: string[]): { valid: string[]; invalid: string[] } {
    const validTags = this.getValidTags();
    const valid: string[] = [];
    const invalid: string[] = [];

    for (const tag of tags) {
      if (validTags.includes(tag)) {
        valid.push(tag);
      } else {
        invalid.push(tag);
      }
    }

    return { valid, invalid };
  }

  private loadMusicMetadata(): MusicMetadata {
    try {
      const metadataPath = path.resolve(
        __dirname,
        "../../music_collection_metadata.json"
      );
      const data = fs.readFileSync(metadataPath, "utf-8");
      return JSON.parse(data);
    } catch (error) {
      throw new Error(
        "music_collection_metadata.json not found in parent directory"
      );
    }
  }

  findTrackByFilename(filename: string): Track | null {
    const metadata = this.loadMusicMetadata();

    for (const track of metadata.tracks) {
      if (
        track.filename === filename ||
        track.relative_path.endsWith(filename)
      ) {
        return track;
      }
    }
    return null;
  }

  findFirstUntaggedTrack(): Track | null {
    const metadata = this.loadMusicMetadata();

    for (const track of metadata.tracks) {
      const assignedTags = track.assigned_tags || [];
      if (assignedTags.length === 0) {
        return track;
      }
    }
    return null;
  }

  async analyzeTrackTags(track: Track): Promise<AnalysisResult> {
    const trackInfo = {
      artist: track.artist || "Unknown",
      title: track.title || "Unknown",
      album: track.album || "Unknown",
      genre: track.genre || "Unknown",
      date: track.date || "Unknown",
      duration: track.duration_formatted || "Unknown",
      bpm: track.bpm || "Unknown",
      key: track.key || "Unknown",
      composer: track.composer || "Unknown",
      currentTags: track.assigned_tags || [],
    };

    // Print track info before analysis
    console.log("\n=== TRACK INFO ===");
    console.log(`Artist: ${trackInfo.artist}`);
    console.log(`Title: ${trackInfo.title}`);
    console.log(`Album: ${trackInfo.album}`);
    console.log(`Genre: ${trackInfo.genre}`);
    console.log(`Year: ${trackInfo.date}`);
    console.log(`Duration: ${trackInfo.duration}`);
    console.log(`BPM: ${trackInfo.bpm}`);
    console.log(`Key: ${trackInfo.key}`);
    console.log(`Composer: ${trackInfo.composer}`);
    console.log(
      `Current Tags: ${
        trackInfo.currentTags.length > 0
          ? trackInfo.currentTags.join(", ")
          : "None"
      }`
    );
    console.log("==================\n");

    const prompt = `You are a world-class music curator, DJ, and music historian with encyclopedic knowledge spanning all genres, eras, and cultures. Your expertise includes music theory, production techniques, cultural movements, and the subtle art of reading dancefloors.

Your task: Conduct a scholarly analysis of this track and select 10-15 tags EXCLUSIVELY from the provided taxonomy below.

🚨 CRITICAL CONSTRAINT: You can ONLY use tags that appear EXACTLY as written in the taxonomy below. Do NOT create any new tags, modify existing tags, or use any tags not explicitly listed. Any response containing tags not in the taxonomy will be rejected.

<track_details>
Artist: ${trackInfo.artist}
Title: ${trackInfo.title}
Album: ${trackInfo.album}
Genre: ${trackInfo.genre}
Year: ${trackInfo.date}
Duration: ${trackInfo.duration}
BPM: ${trackInfo.bpm}
Key: ${trackInfo.key}
Composer: ${trackInfo.composer}
Current Tags: ${
      trackInfo.currentTags.length > 0
        ? trackInfo.currentTags.join(", ")
        : "None"
    }
</track_details>

<available_tags>
${this.tagTaxonomy}
</available_tags>

<analysis_methodology>
PHASE 1: IMMEDIATE SONIC ASSESSMENT
- Identify the primary genre, subgenre, and micro-genre
- Determine the energy level, mood, and emotional arc
- Assess the production era and techniques used
- Note the BPM range and rhythmic feel (straight/swung/syncopated)

PHASE 2: DEEP MUSICOLOGICAL ANALYSIS
- Harmonic Analysis: chord progressions, key modulations, tension/release patterns
- Rhythmic Architecture: groove patterns, polyrhythms, tempo feel
- Sonic Palette: instrumentation, synthesis methods, sampling sources
- Production Techniques: mixing style, effects usage, dynamic range
- Structural Elements: arrangement, build-ups, breakdowns, hooks

PHASE 3: CULTURAL & HISTORICAL CONTEXT
- Place within artist's career arc and discography
- Movement/scene affiliation and influence
- Sampling history (both sampled from and sampled by)
- Cultural impact and legacy
- Underground vs. mainstream positioning

PHASE 4: DJ UTILITY ASSESSMENT
- Mixing compatibility (intro/outro quality, rhythmic stability)
- Energy trajectory (floor-filler, warm-up, peak-time, comedown)
- Harmonic mixing potential (compatible keys and modes)
- Layering possibilities (sparse/dense, frequency distribution)
- Crowd psychology impact (nostalgic triggers, surprise elements)

PHASE 5: EMOTIONAL & NEUROLOGICAL MAPPING
- Emotional journey and psychological triggers
- Nostalgic or futuristic elements
- Dopaminergic peak moments and pleasure principles
- Transcendent or meditative qualities
- Social bonding and collective experience potential
</analysis_methodology>

<exemplar_analyses>
EXAMPLE 1 - Electronic/IDM:
Track: "Boards of Canada - Roygbiv"
Tags: ["electronic-experimental", "nostalgic-hit", "slow-burn", "warm-analog", "psychedelic-journey", "atmospheric-wash", "mind-expanding", "hypnotic-builder", "textural-beauty", "rhythmic-foundation", "layer-friendly", "loop-gold"]
Research Notes: "Seminal track from 'Music Has The Right To Children' (1998). Pioneered the nostalgic electronica aesthetic through analog synthesis. The track creates hypnotic patterns perfect for layering and builds slowly with warm analog textures that bridge generational gaps."

EXAMPLE 2 - Classic House:
Track: "Marshall Jefferson - Move Your Body"
Tags: ["electronic-dance", "instant-dancefloor", "rhythmic-foundation", "peak-time", "timeless-classic", "euphoric-melody", "crowd-pleaser", "hands-up-moment", "energy-injector", "beatmatched-friendly", "long-intro", "smooth-transitions"]
Research Notes: "1986 release that defined house music's commercial viability. Features piano as lead instrument with four-on-the-floor rhythm. Perfect peak-time track with extended intro for mixing and guaranteed crowd response."

EXAMPLE 3 - Experimental/Ambient:
Track: "Tim Hecker - Virginal II"
Tags: ["electronic-ambient", "atmospheric-wash", "textural-beauty", "meditation-inducer", "experimental", "intricate", "mind-expanding", "non-danceable-standalone", "background-perfect", "subtle-nuance", "spacious-mix", "reality-bending"]
Research Notes: "Explores digital decay through processed piano and synthesis. Creates immersive environments perfect for background atmosphere or deep listening. Works well as atmospheric wash in sophisticated DJ sets."
</exemplar_analyses>

<tag_selection_criteria>
🚨 ABSOLUTE REQUIREMENT: Use ONLY tags from the taxonomy above. Each tag must be copied EXACTLY as written.

SELECTION STRATEGY:
1. Review the provided taxonomy categories carefully
2. Select tags that best describe the track's characteristics
3. Aim for diversity across different categories (dopamine source, mixing role, energy dynamics, etc.)
4. Choose 10-15 tags total
5. Double-check that every selected tag appears in the taxonomy above

FORBIDDEN:
❌ Creating new tags not in the taxonomy
❌ Modifying existing tags (e.g., "folk-jazz-fusion" when only "jazz-influenced" exists)
❌ Using BPM numbers as tags (not in taxonomy)
❌ Using artist/producer names as tags (not in taxonomy)
❌ Using year/era numbers as tags (not in taxonomy)

ENCOURAGED:
✅ Use tags from multiple categories for diversity
✅ Focus on DJ utility and emotional impact
✅ Consider the track's role in sophisticated mixing
✅ Think about crowd response and energy management
</tag_selection_criteria>

<edge_case_handling>
For tracks that defy easy categorization:
- Identify the primary tradition it emerges from, then note departures
- Use hybrid descriptors ("jazz-inflected-dnb", "classical-techno-fusion")
- Note if it's genuinely genre-defying with tags like "unclassifiable-experimental"
- Focus more on sonic characteristics and DJ utility than genre boxing

For very new tracks (post-2020):
- Identify connections to established movements
- Note emerging micro-genre affiliations
- Focus on sonic DNA and production techniques
- Consider TikTok/social media virality if relevant

For obscure/underground tracks:
- Research the label, scene, and contemporaries
- Note rarity/collectibility factors
- Identify why it might have been overlooked
- Focus on rediscovery potential
</edge_case_handling>

<output_format>
Return ONLY a valid JSON object:
{
  "tags": [
    "primary-genre-tag",
    "subgenre-specifier",
    "energy-descriptor",
    "era-movement-tag",
    "technical-dj-tag",
    "unique-sonic-element",
    "cultural-significance",
    "mood-journey-tag",
    "production-technique",
    "crowd-impact-tag",
    "additional-relevant-tags"
  ],
  "confidence": 85,
  "research_notes": "Specific insights about this track including: production history, cultural context, DJ utility observations, and any unique elements that influenced tag selection. Mention specific mixing points, cultural movements, or technical details that make this track significant. 2-3 detailed sentences."
}

CRITICAL REQUIREMENTS:
- Use ONLY tags that appear in the provided taxonomy - NO EXCEPTIONS
- Tags must be copied EXACTLY as written in the taxonomy
- Base analysis on deep musical knowledge, not assumptions
- Research using web search for tracks you're less familiar with
- Confidence score should reflect actual knowledge (0-100 scale)
- Provide 10-15 tags, no more, no less
- Research notes must contain specific, verifiable insights
- If you use ANY tag not in the taxonomy, the response will be rejected

Begin your analysis now. Think deeply about this track's place in music history, its technical construction, and its utility for sophisticated DJs and curators.
</output_format>`;

    try {
      const response = await this.client.messages.create({
        model: "claude-sonnet-4-20250514",
        max_tokens: 4000,
        temperature: 1,
        thinking: {
          type: "enabled",
          budget_tokens: 3000,
        },
        tools: [
          {
            type: "web_search_20250305",
            name: "web_search",
            max_uses: 5,
          } as any,
        ],
        messages: [
          {
            role: "user",
            content: prompt,
          },
        ],
      } as any);

      // Find the text content in the response
      let textContent = null;
      for (const block of response.content) {
        if (block.type === "text") {
          textContent = block;
          break;
        }
      }

      if (!textContent) {
        console.warn(
          "No text content found in response. Content blocks:",
          response.content.map((c) => c.type)
        );
        return {
          tags: [],
          confidence: 0,
          research_notes: "No text content found in response",
        };
      }

      try {
        // Extract JSON from the response text with improved parsing
        let jsonText = textContent.text.trim();
        
        console.log("Raw API response length:", jsonText.length);
        console.log("Raw API response preview:", jsonText.substring(0, 500) + "...");

        let result = null;

        // Strategy 1: Look for JSON object in the response
        const jsonMatch = jsonText.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          try {
            result = JSON.parse(jsonMatch[0]);
            console.log("Successfully parsed JSON using strategy 1");
          } catch (e) {
            console.log("Strategy 1 failed, trying strategy 2");
          }
        }

        // Strategy 2: Remove markdown code block formatting if present
        if (!result) {
          if (jsonText.includes("```json")) {
            const jsonStart = jsonText.indexOf("```json") + 7;
            const jsonEnd = jsonText.indexOf("```", jsonStart);
            if (jsonEnd !== -1) {
              jsonText = jsonText.substring(jsonStart, jsonEnd).trim();
            }
          } else if (jsonText.includes("```")) {
            const jsonStart = jsonText.indexOf("```") + 3;
            const jsonEnd = jsonText.indexOf("```", jsonStart);
            if (jsonEnd !== -1) {
              jsonText = jsonText.substring(jsonStart, jsonEnd).trim();
            }
          }
          
          try {
            result = JSON.parse(jsonText);
            console.log("Successfully parsed JSON using strategy 2");
          } catch (e) {
            console.log("Strategy 2 failed, trying strategy 3");
          }
        }

        // Strategy 3: Find last complete JSON object in response
        if (!result) {
          const lines = jsonText.split('\n');
          let braceCount = 0;
          let jsonStart = -1;
          let jsonLines = [];
          
          for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (line.trim().startsWith('{') && jsonStart === -1) {
              jsonStart = i;
              braceCount = 0;
            }
            
            if (jsonStart !== -1) {
              jsonLines.push(line);
              for (const char of line) {
                if (char === '{') braceCount++;
                if (char === '}') braceCount--;
              }
              
              if (braceCount === 0) {
                try {
                  result = JSON.parse(jsonLines.join('\n'));
                  console.log("Successfully parsed JSON using strategy 3");
                  break;
                } catch (e) {
                  // Continue looking for another JSON object
                  jsonStart = -1;
                  jsonLines = [];
                }
              }
            }
          }
        }

        if (!result) {
          console.error("All JSON parsing strategies failed. Raw response:", jsonText);
          return {
            tags: [],
            confidence: 0,
            research_notes: "Failed to parse JSON response",
          };
        }

        const analysisResult = result as AnalysisResult;
        
        console.log("Parsed JSON result:", analysisResult);

        if (analysisResult.tags && Array.isArray(analysisResult.tags)) {
          // Validate that all tags are from the taxonomy
          const validation = this.validateTags(analysisResult.tags);

          if (validation.invalid.length > 0) {
            console.warn(
              `⚠️  Invalid tags detected (not in taxonomy): ${validation.invalid.join(
                ", "
              )}`
            );
            console.warn(`✅ Valid tags: ${validation.valid.join(", ")}`);

            // Return only valid tags
            return {
              tags: validation.valid,
              confidence: Math.max(0, analysisResult.confidence - 20), // Reduce confidence for invalid tags
              research_notes:
                analysisResult.research_notes +
                ` (Note: ${validation.invalid.length} invalid tags were filtered out)`,
            };
          }

          return analysisResult;
        } else {
          console.warn("Response was not a valid object:", result);
          return {
            tags: [],
            confidence: 0,
            research_notes: "Failed to parse response",
          };
        }
      } catch (parseError) {
        console.warn("Could not parse JSON response:", textContent.text);
        return {
          tags: [],
          confidence: 0,
          research_notes: "Invalid JSON response",
        };
      }
    } catch (error) {
      console.error("Error calling Anthropic API:", error);
      return { tags: [], confidence: 0, research_notes: `API Error: ${error}` };
    }
  }

  updateTrackTags(filename: string, analysisResult: AnalysisResult): boolean {
    try {
      const metadata = this.loadMusicMetadata();

      for (const track of metadata.tracks) {
        if (
          track.filename === filename ||
          track.relative_path.endsWith(filename)
        ) {
          track.assigned_tags = analysisResult.tags;
          track.tag_confidence = analysisResult.confidence;
          track.research_notes = analysisResult.research_notes;

          const metadataPath = path.resolve(
            __dirname,
            "../../music_collection_metadata.json"
          );
          fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
          return true;
        }
      }

      console.log(`Track '${filename}' not found in metadata`);
      return false;
    } catch (error) {
      console.error("Error updating metadata:", error);
      return false;
    }
  }

  async analyzeAndUpdateTrack(
    filename?: string
  ): Promise<TrackAnalysisResult | { error: string }> {
    let track: Track | null;
    let actualFilename: string;

    if (filename) {
      track = this.findTrackByFilename(filename);
      if (!track) {
        return { error: `Track '${filename}' not found` };
      }
      actualFilename = filename;
    } else {
      track = this.findFirstUntaggedTrack();
      if (!track) {
        return { error: "No untagged tracks found" };
      }
      actualFilename = track.filename;
    }

    console.log(`Analyzing: ${track.artist} - ${track.title}`);

    const analysisResult = await this.analyzeTrackTags(track);
    if (analysisResult.tags.length === 0) {
      return { error: "Failed to analyze track tags" };
    }

    console.log(`Suggested tags: ${analysisResult.tags.join(", ")}`);
    console.log(`Confidence: ${analysisResult.confidence}%`);
    console.log(`Research notes: ${analysisResult.research_notes}`);

    const success = this.updateTrackTags(actualFilename, analysisResult);

    return {
      track: `${track.artist} - ${track.title}`,
      filename: actualFilename,
      old_tags: track.assigned_tags || [],
      new_tags: analysisResult.tags,
      confidence: analysisResult.confidence,
      research_notes: analysisResult.research_notes,
      updated: success,
    };
  }
}
