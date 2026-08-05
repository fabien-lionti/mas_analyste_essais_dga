PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
  analysis_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  source_dxd_dir TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  config_json TEXT NOT NULL,
  summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_files (
  file_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  source_dxd_path TEXT NOT NULL,
  source_dxd_name TEXT NOT NULL,
  resampled_json_path TEXT,
  resampled_json_name TEXT,
  status TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_files_analysis_path
ON analysis_files(analysis_id, source_dxd_path);

CREATE INDEX IF NOT EXISTS idx_analysis_files_analysis_id
ON analysis_files(analysis_id);

CREATE TABLE IF NOT EXISTS analysis_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id TEXT NOT NULL,
  task_id TEXT,
  level TEXT NOT NULL,
  event_type TEXT NOT NULL,
  message TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analysis_events_analysis_id
ON analysis_events(analysis_id, created_at);

CREATE TABLE IF NOT EXISTS channel_structures (
  analysis_id TEXT PRIMARY KEY,
  preset_name TEXT,
  normalize_names INTEGER NOT NULL,
  min_frequency REAL NOT NULL,
  target_channels_json TEXT NOT NULL,
  recurrent_channels_json TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS channel_presence (
  analysis_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  channel_name TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  present INTEGER NOT NULL,
  sample_rate REAL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (analysis_id, file_id, canonical_name),
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_channel_presence_analysis_channel
ON channel_presence(analysis_id, canonical_name, present);

CREATE TABLE IF NOT EXISTS channel_inventory (
  analysis_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  channel_name TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  unit TEXT,
  sample_rate REAL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (analysis_id, file_id, canonical_name),
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_channel_inventory_analysis_channel
ON channel_inventory(analysis_id, canonical_name);

CREATE TABLE IF NOT EXISTS channel_validated_structures (
  analysis_id TEXT PRIMARY KEY,
  normalize_names INTEGER NOT NULL,
  selected_channels_json TEXT NOT NULL,
  source_summary_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS channel_anomalies (
  analysis_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  details TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (analysis_id, file_id, channel),
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_channel_anomalies_analysis_file
ON channel_anomalies(analysis_id, file_id);
