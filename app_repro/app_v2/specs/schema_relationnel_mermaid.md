# Schema relationnel app_v2

Ce document represente le schema relationnel actuel de `app_v2`, d'apres
`app_v2/app/db/schema.sql`.

## Vue complete

```mermaid
erDiagram
  analyses {
    TEXT analysis_id PK
    TEXT name
    TEXT kind
    TEXT status
    TEXT source_dxd_dir
    TEXT config_json
    TEXT summary_json
  }

  analysis_files {
    TEXT file_id PK
    TEXT analysis_id FK
    TEXT source_dxd_path
    TEXT source_dxd_name
    TEXT resampled_json_path
    TEXT resampled_json_name
    TEXT status
    TEXT recorded_at
    REAL duration_sec
    TEXT metadata_json
  }

  analysis_events {
    INTEGER event_id PK
    TEXT analysis_id FK
    TEXT task_id
    TEXT level
    TEXT event_type
    TEXT message
    TEXT payload_json
  }

  channel_structures {
    TEXT analysis_id PK, FK
    TEXT preset_name
    INTEGER normalize_names
    REAL min_frequency
    TEXT target_channels_json
    TEXT recurrent_channels_json
    TEXT summary_json
    TEXT status
  }

  channel_presence {
    TEXT analysis_id PK, FK
    TEXT file_id PK, FK
    TEXT canonical_name PK
    TEXT channel_name
    INTEGER present
    REAL sample_rate
    TEXT metadata_json
  }

  channel_inventory {
    TEXT analysis_id PK, FK
    TEXT file_id PK, FK
    TEXT canonical_name PK
    TEXT channel_name
    TEXT unit
    REAL sample_rate
    TEXT metadata_json
  }

  channel_validated_structures {
    TEXT analysis_id PK, FK
    INTEGER normalize_names
    TEXT selected_channels_json
    TEXT source_summary_json
    TEXT status
  }

  channel_anomalies {
    TEXT analysis_id PK, FK
    TEXT file_id PK, FK
    TEXT channel PK
    TEXT details
    TEXT metadata_json
  }

  annotation_sets {
    TEXT annotation_set_id PK
    TEXT analysis_id FK
    TEXT name
    TEXT description
    TEXT status
  }

  annotations {
    TEXT annotation_id PK
    TEXT analysis_id FK
    TEXT file_id FK
    TEXT annotation_set_id FK
    REAL start_time_sec
    REAL end_time_sec
    TEXT current_version_id
  }

  annotation_versions {
    TEXT annotation_version_id PK
    TEXT annotation_id FK
    INTEGER version_number
    TEXT label
    REAL confidence
    TEXT comment
    TEXT metadata_json
  }

  annotation_labels {
    TEXT label_id PK
    TEXT analysis_id FK
    TEXT name
    TEXT description
    TEXT color
  }

  dynamic_analysis_prompts {
    TEXT prompt_id PK
    TEXT analysis_id FK
    TEXT name
    TEXT description
    TEXT system_prompt
    TEXT user_prompt
    TEXT required_channels_json
    TEXT output_schema_json
    INTEGER version_number
  }

  dynamic_analysis_runs {
    TEXT run_id PK
    TEXT analysis_id FK
    TEXT prompt_id FK
    TEXT name
    TEXT provider
    TEXT model
    TEXT status
    TEXT request_json
    TEXT context_json
    TEXT response_markdown
  }

  dynamic_analysis_versions {
    TEXT version_id PK
    TEXT run_id FK
    INTEGER version_number
    TEXT response_markdown
    TEXT confidence
    TEXT note
    INTEGER validated_for_dataset
  }

  dynamic_analyses {
    TEXT dynamic_analysis_id PK
    TEXT analysis_id FK
    TEXT name
    TEXT protocol_name
    TEXT description
    TEXT system_prompt
    TEXT selected_channels_json
    TEXT selected_labels_json
    TEXT indicators_json
    TEXT label_category
    TEXT output_schema_json
  }

  dynamic_annotation_predictions {
    TEXT prediction_id PK
    TEXT dynamic_analysis_id FK
    TEXT annotation_id FK
    TEXT provider
    TEXT model
    TEXT status
    TEXT input_context_json
    TEXT input_artifact_path
    TEXT response_json
    TEXT response_markdown
    TEXT analysis_text
    TEXT analysis_note
    TEXT summary_text
    TEXT confidence
    TEXT error_message
  }

  dynamic_prediction_corrections {
    TEXT correction_id PK
    TEXT prediction_id FK
    TEXT corrected_response_json
    TEXT corrected_response_markdown
    TEXT corrected_analysis_text
    TEXT corrected_analysis_note
    TEXT corrected_summary_text
    TEXT corrected_confidence
    TEXT note
    INTEGER validated_for_dataset
  }

  analyses ||--o{ analysis_files : contient
  analyses ||--o{ analysis_events : trace
  analyses ||--o| channel_structures : structure_canaux
  analyses ||--o{ channel_presence : presence_canaux
  analyses ||--o{ channel_inventory : inventaire_canaux
  analyses ||--o| channel_validated_structures : structure_validee
  analyses ||--o{ channel_anomalies : anomalies_canaux

  analysis_files ||--o{ channel_presence : expose
  analysis_files ||--o{ channel_inventory : inventorie
  analysis_files ||--o{ channel_anomalies : porte

  analyses ||--o{ annotation_sets : groupes_annotations
  analyses ||--o{ annotation_labels : labels_administres
  analyses ||--o{ annotations : annotations
  analysis_files ||--o{ annotations : segments
  annotation_sets ||--o{ annotations : contient
  annotations ||--o{ annotation_versions : versions

  analyses ||--o{ dynamic_analysis_prompts : prompts
  analyses ||--o{ dynamic_analysis_runs : runs_legacy
  dynamic_analysis_prompts |o--o{ dynamic_analysis_runs : utilise
  dynamic_analysis_runs ||--o{ dynamic_analysis_versions : versions

  analyses ||--o{ dynamic_analyses : analyses_dynamiques
  dynamic_analyses ||--o{ dynamic_annotation_predictions : predictions
  annotations ||--o{ dynamic_annotation_predictions : cible
  dynamic_annotation_predictions ||--o{ dynamic_prediction_corrections : corrections
```

## Vue metier simplifiee

```mermaid
erDiagram
  analyses ||--o{ analysis_files : fichiers_DXD
  analyses ||--o| channel_structures : structure_scannee
  analyses ||--o| channel_validated_structures : canaux_selectionnes
  analysis_files ||--o{ channel_inventory : canaux_disponibles
  analysis_files ||--o{ channel_presence : presence_canaux
  analysis_files ||--o{ channel_anomalies : anomalies

  analyses ||--o{ annotation_sets : jeux_annotations
  analyses ||--o{ annotation_labels : catalogue_labels
  analysis_files ||--o{ annotations : annotations
  annotations ||--o{ annotation_versions : historique

  analyses ||--o{ dynamic_analyses : analyses_dynamiques
  dynamic_analyses ||--o{ dynamic_annotation_predictions : predictions_LLM
  annotations ||--o{ dynamic_annotation_predictions : annotation_cible
  dynamic_annotation_predictions ||--o{ dynamic_prediction_corrections : corrections_analyste
```

## Extension future capteurs

```mermaid
erDiagram
  sensors {
    TEXT sensor_id PK
    TEXT name
    TEXT sensor_type
    TEXT manufacturer
    TEXT model
    TEXT serial_number
    TEXT description
    TEXT metadata_json
  }

  analysis_sensors {
    TEXT analysis_sensor_id PK
    TEXT analysis_id FK
    TEXT sensor_id FK
    TEXT vehicle_position
    TEXT mounting_description
    TEXT metadata_json
  }

  analysis_sensor_channels {
    TEXT analysis_sensor_channel_id PK
    TEXT analysis_sensor_id FK
    TEXT analysis_id FK
    TEXT canonical_channel_name
    TEXT dxd_channel_name
    TEXT unit
    TEXT metadata_json
  }

  sensors ||--o{ analysis_sensors : utilise_dans
  analyses ||--o{ analysis_sensors : instrumentation
  analysis_sensors ||--o{ analysis_sensor_channels : mappe_canaux
  channel_inventory }o--o{ analysis_sensor_channels : reference_logique
```
