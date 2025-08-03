export interface Track {
  relative_path: string;
  filename: string;
  file_size_mb: number;
  duration_seconds: number;
  duration_formatted: string;
  artist: string;
  title: string;
  album: string;
  albumartist: string;
  date: string;
  genre: string;
  track: string;
  tracktotal: string;
  disc: string;
  disctotal: string;
  composer: string;
  label: string;
  isrc: string;
  bpm: string;
  key: string;
  key_was_guessed?: boolean;
  comment: string;
  grouping: string;
  bitrate: number;
  sample_rate: number;
  channels: number;
  bits_per_sample: number;
  assigned_tags: string[];
  tag_confidence?: number;
  research_notes?: string;
}

export interface MusicMetadata {
  metadata: {
    total_files: number;
    successful_extractions: number;
    failed_extractions: number;
    scan_date: string;
    scan_time: string;
    directory_path: string;
    collection_duration_hours: number;
    total_size_gb: number;
  };
  tracks: Track[];
}

export interface AnalysisResult {
  tags: string[];
  confidence: number;
  research_notes: string;
  detected_key?: string | null;
}

export interface TrackAnalysisResult {
  track: string;
  filename: string;
  old_tags: string[];
  new_tags: string[];
  confidence: number;
  research_notes: string;
  updated: boolean;
}