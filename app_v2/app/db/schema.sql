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
  recorded_at TEXT,
  duration_sec REAL,
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

CREATE TABLE IF NOT EXISTS annotation_sets (
  annotation_set_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_annotation_sets_analysis_name
ON annotation_sets(analysis_id, name);

CREATE TABLE IF NOT EXISTS annotations (
  annotation_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  annotation_set_id TEXT NOT NULL,
  start_time_sec REAL NOT NULL,
  end_time_sec REAL NOT NULL,
  current_version_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE,
  FOREIGN KEY (annotation_set_id) REFERENCES annotation_sets(annotation_set_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_annotations_analysis_file
ON annotations(analysis_id, file_id, start_time_sec);

CREATE TABLE IF NOT EXISTS annotation_versions (
  annotation_version_id TEXT PRIMARY KEY,
  annotation_id TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  label TEXT NOT NULL,
  confidence REAL,
  comment TEXT,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (annotation_id) REFERENCES annotations(annotation_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_annotation_versions_annotation_number
ON annotation_versions(annotation_id, version_number);

CREATE TABLE IF NOT EXISTS annotation_labels (
  label_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  color TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_annotation_labels_analysis_name
ON annotation_labels(analysis_id, name);

CREATE TABLE IF NOT EXISTS dynamic_analysis_prompts (
  prompt_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  system_prompt TEXT NOT NULL,
  user_prompt TEXT NOT NULL,
  required_channels_json TEXT NOT NULL DEFAULT '[]',
  output_schema_json TEXT NOT NULL DEFAULT '{}',
  version_number INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dynamic_analysis_prompts_analysis
ON dynamic_analysis_prompts(analysis_id, updated_at);

CREATE TABLE IF NOT EXISTS dynamic_analysis_runs (
  run_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  prompt_id TEXT,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT,
  status TEXT NOT NULL,
  request_json TEXT NOT NULL,
  context_json TEXT NOT NULL,
  response_markdown TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (prompt_id) REFERENCES dynamic_analysis_prompts(prompt_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_dynamic_analysis_runs_analysis
ON dynamic_analysis_runs(analysis_id, created_at);

CREATE TABLE IF NOT EXISTS dynamic_analysis_versions (
  version_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  response_markdown TEXT NOT NULL,
  confidence TEXT,
  note TEXT,
  validated_for_dataset INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES dynamic_analysis_runs(run_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dynamic_analysis_versions_run_number
ON dynamic_analysis_versions(run_id, version_number);

CREATE TABLE IF NOT EXISTS dynamic_analyses (
  dynamic_analysis_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  name TEXT NOT NULL,
  protocol_name TEXT NOT NULL DEFAULT '',
  description TEXT,
  system_prompt TEXT NOT NULL,
  selected_channels_json TEXT NOT NULL,
  selected_labels_json TEXT NOT NULL DEFAULT '[]',
  indicators_json TEXT NOT NULL,
  label_category TEXT NOT NULL,
  output_schema_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dynamic_analyses_analysis
ON dynamic_analyses(analysis_id, updated_at);

CREATE TABLE IF NOT EXISTS dynamic_annotation_predictions (
  prediction_id TEXT PRIMARY KEY,
  dynamic_analysis_id TEXT NOT NULL,
  annotation_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT,
  status TEXT NOT NULL,
  input_context_json TEXT NOT NULL,
  input_artifact_path TEXT,
  response_json TEXT NOT NULL,
  response_markdown TEXT NOT NULL,
  analysis_text TEXT NOT NULL DEFAULT '',
  analysis_note TEXT NOT NULL DEFAULT '',
  summary_text TEXT NOT NULL DEFAULT '',
  confidence TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (dynamic_analysis_id) REFERENCES dynamic_analyses(dynamic_analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (annotation_id) REFERENCES annotations(annotation_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dynamic_predictions_unique_annotation
ON dynamic_annotation_predictions(dynamic_analysis_id, annotation_id);

CREATE INDEX IF NOT EXISTS idx_dynamic_predictions_dynamic_analysis
ON dynamic_annotation_predictions(dynamic_analysis_id, created_at);

CREATE TABLE IF NOT EXISTS dynamic_prediction_corrections (
  correction_id TEXT PRIMARY KEY,
  prediction_id TEXT NOT NULL,
  corrected_response_json TEXT NOT NULL,
  corrected_response_markdown TEXT NOT NULL,
  corrected_analysis_text TEXT NOT NULL DEFAULT '',
  corrected_analysis_note TEXT NOT NULL DEFAULT '',
  corrected_summary_text TEXT NOT NULL DEFAULT '',
  corrected_confidence TEXT,
  note TEXT,
  validated_for_dataset INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (prediction_id) REFERENCES dynamic_annotation_predictions(prediction_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dynamic_corrections_prediction
ON dynamic_prediction_corrections(prediction_id, created_at);
