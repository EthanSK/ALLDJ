import { MusicTagAnalyzer } from "./src/tag-analyzer";

async function testAnalyzer() {
  try {
    console.log("Creating analyzer...");
    const analyzer = new MusicTagAnalyzer();

    console.log("Finding first untagged track...");
    const firstTrack = analyzer.findFirstUntaggedTrack();

    if (!firstTrack) {
      console.log("No untagged tracks found!");
      return;
    }

    console.log(`\nFound track: ${firstTrack.artist} - ${firstTrack.title}`);
    console.log(`Album: ${firstTrack.album}`);
    console.log(`Genre: ${firstTrack.genre}`);
    console.log(`Year: ${firstTrack.date}`);

    console.log("\nRunning AI analysis...");
    const result = await analyzer.analyzeAndUpdateTrack();

    console.log("\n=== ANALYSIS RESULT ===");
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error("Error:", error.message);
    console.error("Stack:", error.stack);
  }
}

testAnalyzer();
