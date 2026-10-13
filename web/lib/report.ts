// Data contract produced by `kozquloq report --json-out report.json`.
// Keep in sync with kozquloq/visualization/report_generator.py::report_payload.

export interface Health {
  frames: number;
  annotations: number;
  ghosts: number;
  kinematic_outliers: number;
  scale_unstable: number;
  underexposed_frames: number;
  drift_frames: number;
  flagged: number;
  failure_pct: number;
  grade: "A" | "B" | "C" | "D" | "F";
}

export interface Finding {
  kind: "ghost" | "kinematic" | "scale" | "underexposed" | "drift";
  title: string;
  count: number;
  pct: number;
  detail: string;
  why: string;
}

export interface SliceRow {
  weather: string;
  time_of_day: string;
  category: string;
  total_annotations: number;
  ghost_labels_count: number;
  kinematic_outliers_count: number;
  avg_lidar_points: number;
  failure_rate_pct: number;
}

export interface GalleryItem {
  sample_token: string;
  caption: string;
  plain: string;
  images: { full?: string; boxes?: string; flagged?: string };
}

export interface Report {
  generated_at: string;
  health: Health;
  verdict: string;
  findings: Finding[];
  charts: {
    severity_hist: { bucket: number; n: number }[];
    categories: { category: string; total: number; flagged: number }[];
    scenes: { name: string; total: number; flagged: number }[];
  };
  slices: SliceRow[];
  gallery: GalleryItem[];
  diagnostics: string;
}
