# App v2 - Modele

## Racine du modele

La table centrale est `analyses`.

Une analyse represente une campagne de travail :

- nom ;
- type ;
- statut ;
- dossier source DXD ;
- configuration JSON ;
- resume JSON.

Toutes les donnees metier sont rattachees a `analysis_id`.

## Entites principales

### analyses

Table : `analyses`

Role :

- racine de l'application ;
- porte la configuration globale ;
- permet de choisir l'analyse active dans l'UI.

Champs structurants :

- `analysis_id`
- `name`
- `kind`
- `status`
- `source_dxd_dir`
- `config_json`
- `summary_json`

### analysis_files

Table : `analysis_files`

Role :

- catalogue des DXD rattaches a une analyse ;
- lien entre DXD source et JSON resample ;
- support des filtres temporels via metadata fichier.

Champs structurants :

- `file_id`
- `analysis_id`
- `source_dxd_path`
- `source_dxd_name`
- `resampled_json_path`
- `resampled_json_name`
- `recorded_at`
- `duration_sec`
- `metadata_json`

`recorded_at` et `duration_sec` sont utilises pour l'exploration et les filtres
date. Ils ne doivent pas etre deduits seulement du nom de fichier.

### analysis_events

Table : `analysis_events`

Role :

- journal d'evenements d'une analyse ;
- suivi des taches et messages metier.

Champs structurants :

- `analysis_id`
- `task_id`
- `level`
- `event_type`
- `message`
- `payload_json`

## Modele canaux

### channel_structures

Role :

- resultat du scan de structure DXD ;
- canaux recurrents ;
- resume du scan.

Cette table decrit une structure calculee, pas forcement la structure retenue.

### channel_inventory

Role :

- inventaire des canaux presents dans chaque fichier ;
- nom source, nom canonique, unite, frequence.

Elle alimente la liste des canaux recurrents.

### channel_presence

Role :

- presence/absence d'un canal canonique par fichier ;
- historique plus oriente matrice de presence.

### channel_validated_structures

Role :

- structure active retenue par l'utilisateur ;
- liste des canaux selectionnes pour le sampling JSON.

Cette table est la source de coherence entre scan DXD et export JSON.

### channel_anomalies

Role :

- anomalies de canaux par fichier ;
- permet de voir les fichiers incomplets ou divergents.

## Modele annotations

### annotation_sets

Role :

- groupe logique d'annotations pour une analyse ;
- un set par defaut est cree si necessaire.

### annotations

Role :

- segment temporel annote dans un fichier d'analyse ;
- ne porte pas directement le label final ;
- pointe vers sa version courante.

Champs structurants :

- `annotation_id`
- `analysis_id`
- `file_id`
- `annotation_set_id`
- `start_time_sec`
- `end_time_sec`
- `current_version_id`

### annotation_versions

Role :

- versionnement du label et du commentaire ;
- conserve l'historique des modifications.

Champs structurants :

- `annotation_id`
- `version_number`
- `label`
- `confidence`
- `comment`
- `metadata_json`

### annotation_labels

Role :

- catalogue administre des labels autorises ;
- l'UI d'annotation doit choisir dans ce catalogue.

Une annotation ne peut etre creee que si son label existe dans `annotation_labels`.

## Modele analyse dynamique

### dynamic_analyses

Role :

- definition d'une analyse dynamique rattachee a une analyse ;
- contient le prompt systeme et les donnees pertinentes.

Champs structurants :

- `dynamic_analysis_id`
- `analysis_id`
- `name`
- `description`
- `system_prompt`
- `selected_channels_json`
- `selected_labels_json`
- `indicators_json`
- `label_category`
- `output_schema_json`

Regle fonctionnelle actuelle :

- `POST /dynamic-analysis` cree une definition si le nom est nouveau ;
- si le meme nom existe deja pour la meme analyse, l'ancienne definition est
  ecrasee par mise a jour applicative.

### dynamic_annotation_predictions

Role :

- prediction LLM rattachee a une analyse dynamique et a une annotation ;
- une seule prediction courante par couple `(dynamic_analysis_id, annotation_id)`.

Champs structurants :

- `prediction_id`
- `dynamic_analysis_id`
- `annotation_id`
- `provider`
- `model`
- `status`
- `input_context_json`
- `input_artifact_path`
- `response_json`
- `response_markdown`
- `analysis_text`
- `analysis_note`
- `summary_text`

Le chemin `input_artifact_path` pointe vers l'artefact visuel genere pour
l'annotation.

### dynamic_prediction_corrections

Role :

- correction humaine d'une prediction ;
- conserve texte corrige, synthese corrigee, note et statut de validation.

### Tables legacy analyse dynamique

Les tables suivantes existent encore :

- `dynamic_analysis_prompts`
- `dynamic_analysis_runs`
- `dynamic_analysis_versions`

Elles correspondent a une ancienne logique prompt/run/version globale. Elles
restent exposees par des routes de compatibilite, mais le workflow produit recent
utilise surtout `dynamic_analyses`, `dynamic_annotation_predictions` et
`dynamic_prediction_corrections`.

## Relations principales

```text
analyses
  -> analysis_files
  -> analysis_events
  -> channel_structures
  -> channel_inventory
  -> channel_presence
  -> channel_validated_structures
  -> channel_anomalies
  -> annotation_sets
       -> annotations
            -> annotation_versions
  -> annotation_labels
  -> dynamic_analyses
       -> dynamic_annotation_predictions
            -> dynamic_prediction_corrections
```

## Repositories

| Repository | Role |
| --- | --- |
| `analyses.py` | CRUD analyse, config, resume |
| `files.py` | decouverte DXD, catalogue fichiers, metadata temporelles, lien JSON |
| `channels.py` | structures, inventaire, presence, anomalies, structure validee |
| `annotations.py` | sets, labels administres, annotations, versions |
| `dynamic_analysis.py` | definitions analyse dynamique, predictions, corrections, compat prompts/runs |
| `events.py` | journal d'evenements |

## Services metier

| Service | Role |
| --- | --- |
| `channel_structure_service.py` | lit les DXD, calcule inventaire, presence et recurrence |
| `channel_validation_service.py` | sauvegarde la structure active et calcule les anomalies |
| `resampling_service.py` | exporte les DXD en JSON resample |
| `channel_analysis_tasks.py` | taches longues de scan canaux en memoire |
| `resampling_tasks.py` | taches longues d'export JSON en memoire |
| `domain/channels.py` | presets et normalisation/candidats de canaux |

## Migration

`connection.py` charge `schema.sql`, puis applique des migrations additives via
`_add_column_if_missing`.

Les migrations actuelles ajoutent notamment :

- `recorded_at`, `duration_sec` sur `analysis_files` ;
- champs recents de `dynamic_analyses` ;
- textes structures et corrections sur les predictions dynamiques.
