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

    const prompt = `You are a world-class music curator, DJ, and musicologist with encyclopedic knowledge spanning all genres, eras, and cultures. Your expertise covers music theory, production techniques, cultural movements, and the art of DJing at the highest level.

<analysis_context>
 
TASK: Conduct a comprehensive musicological analysis for sophisticated DJ curation and music discovery
</analysis_context>

<track_to_analyze>
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
</track_to_analyze>

<available_tag_taxonomy>
${this.tagTaxonomy}
</available_tag_taxonomy>

<exemplary_analysis_reference>
Example of excellent analysis for "Boards of Canada - Roygbiv":
Tags: ["idm-classic", "nostalgic-electronica", "downtempo-sunrise", "analog-warmth", "childhood-memory-trigger", "harmonic-progression-masterclass", "70bpm-halfstep-potential", "documentary-soundtrack", "warp-records-golden-era", "modular-synthesis", "hauntological", "major-seventh-bliss", "tape-saturation-aesthetic", "millennial-childhood-soundtrack"]
Research Notes: "Seminal IDM track from 'Music Has The Right To Children' (1998). Features intentionally detuned analog synths`;

    try {
      const response = await this.client.messages.create({
        model: "claude-opus-4-20250514",
        max_tokens: 4000,
        temperature: 0.7,
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
        // Extract JSON from the response text, handling potential markdown formatting
        let jsonText = textContent.text.trim();

        // Remove markdown code block formatting if present
        if (jsonText.startsWith("```json")) {
          jsonText = jsonText.replace(/^```json\s*/, "").replace(/\s*```$/, "");
        } else if (jsonText.startsWith("```")) {
          jsonText = jsonText.replace(/^```\s*/, "").replace(/\s*```$/, "");
        }

        const result = JSON.parse(jsonText) as AnalysisResult;
        if (result.tags && Array.isArray(result.tags)) {
          return result;
        } else {
          console.warn("Response was not a valid object:", textContent.text);
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
