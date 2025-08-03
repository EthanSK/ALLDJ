import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";
import { AnalysisResult } from "./types";

const AnalysisResultSchema = z.object({
  tags: z.array(z.string()),
  confidence: z.number().min(0).max(100),
  research_notes: z.string(),
  detected_key: z.string().nullable(),
});

export class OpenAIService {
  private openai: OpenAI;

  constructor(apiKey: string) {
    this.openai = new OpenAI({ apiKey });
  }

  async analyzeTrackTags(prompt: string): Promise<AnalysisResult> {
    try {
      const response = await this.openai.responses.create({
        model: "o3",
        input: [
          {
            role: "user" as const,
            content: prompt,
          },
        ],
        reasoning: {
          effort: "medium",
        },
        tools: [
          {
            type: "web_search",
          },
        ],
        text: {
          format: zodTextFormat(AnalysisResultSchema, "track_analysis"),
        },
        store: false, // Zero Data Retention
      } as any);

      if (response.status !== "completed") {
        throw new Error(
          `OpenAI request failed with status: ${response.status}`
        );
      }

      if (!response.output_text) {
        throw new Error("No output text in OpenAI response");
      }

      // Parse the structured output directly
      const parsed = JSON.parse(response.output_text);
      return AnalysisResultSchema.parse(parsed);
    } catch (error) {
      console.error("OpenAI API error:", error);
      throw new Error(`Failed to analyze track tags: ${error}`);
    }
  }
}
