# Architecture cible analyse-centrique

## Objectif

Repartir de zero dans une nouvelle application locale, sans migrer les donnees
courantes. L'application doit avoir une source de verite claire :

- les acquisitions source restent des fichiers `.dxd` ;
- les exports re-echantillonnes restent des fichiers `.json` ;
- tout le reste est stocke dans SQLite et rattache a une analyse ;
- les artefacts lourds de modeles, comme les poids, peuvent rester sur le systeme
  de fichiers local, mais ils doivent toujours etre indexes, versionnes et
  rattaches dans SQLite.

Un fichier ou artefact qui existe sur disque mais qui n'est pas reference dans la
base n'existe pas fonctionnellement pour l'application.

## Nouvelle arborescence proposee

```text
app_v2/
  README.md
  pyproject.toml
  .env.example

  app/
    __init__.py
    main.py
    config.py
    dependencies.py

    api/
      __init__.py
      routes/
        analyses.py
        files.py
        dxd_channels.py
        resampling.py
        exploration.py
        annotations.py
        business_tasks.py
        rollover.py
        models.py
        predictions.py
        events.py

    db/
      __init__.py
      connection.py
      schema.sql
      repositories/
        analyses.py
        files.py
        channels.py
        resampling.py
        annotations.py
        tasks.py
        rollover.py
        models.py
        predictions.py
        events.py

    domain/
      __init__.py
      dxd_schema.py
      channels.py
      annotations.py
      rollover.py
      models.py
      exploration.py

    services/
      __init__.py
      analysis_service.py
      dxd_discovery_service.py
      channel_structure_service.py
      resampling_service.py
      exploration_service.py
      annotation_service.py
      rollover_service.py
      model_training_service.py
      prediction_service.py

    workers/
      __init__.py
      jobs.py
      progress.py

    static/
      index.html
      annotator.html
      exploration_labels.html
      common.css

data/
  acquisitions/
      .gitkeep
  {analysis_name_slug}/
    resampled_json/
        *.json
  model_artifacts/
      .gitkeep

  specs/
    architecture_analyse_centrale.md

  tests/
    test_schema.py
    test_analysis_workflow.py
```

## Regles de stockage

### Autorise sur disque

```text
data/acquisitions/**/*.dxd
data/{analysis_name_slug}/resampled_json/**/*.json
data/model_artifacts/{analysis_id}/{model_version_id}/...
```

Les poids modeles sont autorises sur disque pour des raisons pragmatiques, mais
leur chemin, taille, hash et rattachement a une version de modele doivent etre en
base.

Les JSON re-echantillonnes doivent etre regroupes dans un dossier derive du nom
de l'analyse, par exemple :

```text
data/campagne-avril-2025/resampled_json/
  run_001.json
  run_002.json
```

Le nom du dossier est un slug stable du nom d'analyse. Si deux analyses ont le
meme nom, l'application doit ajouter un suffixe deterministe ou l'identifiant
d'analyse pour eviter toute collision. La base SQLite reste la source de verite :
le dossier rend seulement le stockage disque coherent et inspectable.

### Interdit comme source de verite

```text
*.csv
*_progress.json
*_summary.json
*_details.json
*.log
predictions.csv
annotations.csv
```

Ces donnees doivent etre representees dans SQLite. Les logs et progressions vont
dans `analysis_events`.

## Concepts metier

### Analyse

Une analyse est le conteneur principal. Elle represente une campagne ou un espace
de travail reproductible.

Exemples :

- `Campagne avril 2025 - structure canaux`
- `Campagne retournement charge GSD`
- `Analyse annotation segments dynamiques`

Une analyse contient :

- des fichiers `.dxd` ;
- leurs JSON re-echantillonnes ;
- une structure de canaux ;
- des indicateurs dynamiques selectionnes ;
- des annotations versionnees ;
- des taches metier ;
- des modeles et versions de modeles ;
- des predictions ;
- des evenements.

Dans le workflow utilisateur courant, une analyse est creee comme un ensemble de
fichiers `.dxd` auquel on associe une structure de canaux validee et des
indicateurs dynamiques, puis des parametres de sampling. Le bouton final de
creation lance ensuite l'export des `.dxd` selectionnes en `.json`
re-echantillonnes dans le dossier de l'analyse.

### Tache metier

Une tache metier est une operation interpretable fonctionnellement dans une
analyse. Exemple : `rollover`.

Une tache metier peut avoir :

- une liste de canaux ;
- des indicateurs calcules ;
- un prompt system ;
- un template utilisateur ;
- des entrees explicites : fichier, segment, version d'annotation ;
- des resultats versionnables.

La vue actuelle appelee "Drift" ne doit pas etre modelisee comme une tache metier :
elle fait de l'exploration descriptive par labels/segments.

### Annotation

Une annotation est rattachee a :

- une analyse ;
- un fichier de cette analyse ;
- un jeu d'annotations ;
- une version d'annotation courante.

Les annotations sont versionnees afin de savoir exactement quelle version a ete
utilisee pour un modele, une prediction ou une tache metier.

### Modele

Un modele est rattache a une analyse. Chaque entrainement cree une version de
modele avec :

- configuration ;
- split train/validation/test ;
- metriques ;
- artefacts locaux indexes ;
- predictions rattachees.

## Schema SQLite cible

### analyses

```sql
CREATE TABLE analyses (
  analysis_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  source_dxd_dir TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  config_json TEXT NOT NULL,
  summary_json TEXT NOT NULL
);
```

Note implementation actuelle : la base SQLite contient encore une colonne
legacy `kind` sur `analyses`, renseignee en interne avec une valeur fixe. Elle ne
fait plus partie du modele produit expose a l'utilisateur.

### analysis_files

```sql
CREATE TABLE analysis_files (
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
```

`resampled_json_path` et `resampled_json_name` referencent le JSON exporte pour ce
fichier dans le contexte de l'analyse courante. Un meme `.dxd` peut donc etre
utilise dans plusieurs analyses avec des exports JSON differents.

`recorded_at` porte la date/heure metier de l'acquisition quand elle est connue.
Elle doit provenir des metadonnees du fichier ou d'une source d'import explicite,
pas du nom du fichier. `duration_sec` porte la duree exploitable du fichier,
alimentee notamment par l'export JSON resample. `metadata_json.modified_at`
reste une metadonnee filesystem. Tant qu'une date d'acquisition DXD plus fiable
n'est pas extraite, l'interface peut l'utiliser comme borne de filtrage explicite,
mais elle ne doit jamais deduire une date depuis le nom du fichier.

### channel_structures

```sql
CREATE TABLE channel_structures (
  analysis_id TEXT PRIMARY KEY,
  preset_name TEXT,
  normalize_names INTEGER NOT NULL,
  min_frequency REAL,
  target_channels_json TEXT NOT NULL,
  recurrent_channels_json TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

Etat actuel de `app_v2` : la structure calculee et la structure validee sont
uniques par analyse. Cela correspond a l'usage "une analyse = un perimetre DXD +
une structure active de canaux + un sampling". Si le besoin de reproductibilite
augmente, ce modele pourra evoluer vers des versions de structure de canaux
referencees explicitement par les exports JSON, annotations, taches metier et
modeles.

### channel_presence

```sql
CREATE TABLE channel_presence (
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
```

### resampled_json_exports

```sql
CREATE TABLE resampled_json_exports (
  analysis_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  json_name TEXT NOT NULL,
  json_path TEXT NOT NULL,
  target_hz REAL NOT NULL,
  channels_json TEXT NOT NULL,
  missing_channels_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (analysis_id, file_id),
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE
);
```

Etat actuel de `app_v2` : les exports JSON sont d'abord references dans
`analysis_files.resampled_json_path` et `analysis_files.resampled_json_name`.
La table `resampled_json_exports` reste le modele cible pour historiser plus
finement les exports, leurs canaux, leurs canaux manquants et leurs metadonnees.

### annotation_sets

```sql
CREATE TABLE annotation_sets (
  annotation_set_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

### annotations

```sql
CREATE TABLE annotations (
  annotation_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  annotation_set_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (annotation_set_id) REFERENCES annotation_sets(annotation_set_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE
);
```

### annotation_versions

```sql
CREATE TABLE annotation_versions (
  annotation_version_id TEXT PRIMARY KEY,
  annotation_id TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  start_sec REAL NOT NULL,
  end_sec REAL NOT NULL,
  label TEXT NOT NULL,
  comment TEXT,
  source TEXT NOT NULL,
  created_by TEXT,
  is_current INTEGER NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (annotation_id) REFERENCES annotations(annotation_id) ON DELETE CASCADE
);
```

### business_tasks

```sql
CREATE TABLE business_tasks (
  task_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  config_json TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

Pour `rollover`, `config_json` contient notamment :

```json
{
  "channels": ["vehicle.vx", "vehicle.ay", "vehicle.roll_angle", "vehicle.ltr"],
  "indicators": ["ltr_max_abs", "roll_angle_max_deg", "oscillations"],
  "vlm_provider": "openai",
  "system_prompt": "...",
  "user_prompt_template": "...",
  "thresholds": {
    "ltr_warning": 0.7,
    "ltr_critical": 0.9
  }
}
```

### business_task_inputs

```sql
CREATE TABLE business_task_inputs (
  task_input_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  analysis_id TEXT NOT NULL,
  file_id TEXT,
  annotation_id TEXT,
  annotation_version_id TEXT,
  input_role TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES business_tasks(task_id) ON DELETE CASCADE,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

### business_task_results

```sql
CREATE TABLE business_task_results (
  result_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  analysis_id TEXT NOT NULL,
  file_id TEXT,
  annotation_id TEXT,
  annotation_version_id TEXT,
  status TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES business_tasks(task_id) ON DELETE CASCADE,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

### models

```sql
CREATE TABLE models (
  model_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  task TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

### model_versions

```sql
CREATE TABLE model_versions (
  model_version_id TEXT PRIMARY KEY,
  model_id TEXT NOT NULL,
  analysis_id TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  trained_at TEXT,
  config_json TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

### model_artifacts

```sql
CREATE TABLE model_artifacts (
  artifact_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  model_version_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  storage_kind TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT,
  size_bytes INTEGER,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE,
  FOREIGN KEY (model_version_id) REFERENCES model_versions(model_version_id) ON DELETE CASCADE
);
```

`storage_kind` vaut d'abord `local_file`.

### dataset_splits

```sql
CREATE TABLE dataset_splits (
  split_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  model_version_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  annotation_id TEXT,
  annotation_version_id TEXT,
  split_name TEXT NOT NULL,
  reason TEXT,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (model_version_id) REFERENCES model_versions(model_version_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE
);
```

### model_predictions

```sql
CREATE TABLE model_predictions (
  prediction_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  model_version_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  annotation_id TEXT,
  annotation_version_id TEXT,
  start_sec REAL,
  end_sec REAL,
  label TEXT,
  confidence REAL,
  scores_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY (model_version_id) REFERENCES model_versions(model_version_id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES analysis_files(file_id) ON DELETE CASCADE
);
```

### exploration_caches

Les resultats de boxplots ou agregats descriptifs peuvent etre caches, mais ils
restent derives et invalidables.

```sql
CREATE TABLE exploration_caches (
  cache_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  cache_kind TEXT NOT NULL,
  cache_key TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,
  FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);
```

### analysis_events

```sql
CREATE TABLE analysis_events (
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
```

## Endpoints cibles

Tous les endpoints de donnees doivent etre scopes par `analysis_id`.

### Analyses

```text
GET    /api/analyses
POST   /api/analyses
GET    /api/analyses/{analysis_id}
PATCH  /api/analyses/{analysis_id}
DELETE /api/analyses/{analysis_id}
GET    /api/analyses/{analysis_id}/events
```

### Fichiers et acquisitions

```text
GET  /api/analyses/{analysis_id}/files
POST /api/analyses/{analysis_id}/files/discover-dxd
GET  /api/analyses/{analysis_id}/files/{file_id}
```

### Structure canaux

```text
GET  /api/analyses/{analysis_id}/channels/presets
POST /api/analyses/{analysis_id}/channels/analyze
GET  /api/analyses/{analysis_id}/channels/status
GET  /api/analyses/{analysis_id}/channels/presence
GET  /api/analyses/{analysis_id}/channels/recurrent
```

### Resampling JSON

```text
POST /api/analyses/{analysis_id}/resampling/export-json
GET  /api/analyses/{analysis_id}/resampling/status
GET  /api/analyses/{analysis_id}/resampling/files
GET  /api/analyses/{analysis_id}/resampling/files/{file_id}
```

Etat actuel de `app_v2` :

```text
POST /api/analyses/{analysis_id}/resampling/export-json
GET  /api/analyses/{analysis_id}/resampling/tasks/current
GET  /api/analyses/{analysis_id}/resampling/tasks/{task_id}
POST /api/analyses/{analysis_id}/resampling/tasks/{task_id}/cancel
```

L'export est lance comme une tache asynchrone afin d'alimenter une barre de
progression dans l'interface. Les endpoints `status` et `files` restent des
endpoints cibles pour exposer l'etat consolide et la liste des JSON exportes.

### Exploration descriptive par labels

Cette famille remplace la vue actuellement appelee "Drift".

```text
GET /api/analyses/{analysis_id}/exploration/files
GET /api/analyses/{analysis_id}/exploration/labels
GET /api/analyses/{analysis_id}/exploration/signals/options
GET /api/analyses/{analysis_id}/exploration/segments
GET /api/analyses/{analysis_id}/exploration/signals/series
GET /api/analyses/{analysis_id}/exploration/signals/boxplot
```

### Annotations

```text
GET    /api/analyses/{analysis_id}/annotation-sets
POST   /api/analyses/{analysis_id}/annotation-sets
GET    /api/analyses/{analysis_id}/annotations
POST   /api/analyses/{analysis_id}/annotations
GET    /api/analyses/{analysis_id}/annotations/{annotation_id}
PATCH  /api/analyses/{analysis_id}/annotations/{annotation_id}
DELETE /api/analyses/{analysis_id}/annotations/{annotation_id}
GET    /api/analyses/{analysis_id}/annotations/{annotation_id}/versions
POST   /api/analyses/{analysis_id}/annotations/{annotation_id}/versions
```

`PATCH /annotations/{annotation_id}` ne modifie pas en place : il cree une
nouvelle version et la marque comme courante.

### Taches metier

```text
GET  /api/analyses/{analysis_id}/tasks
POST /api/analyses/{analysis_id}/tasks
GET  /api/analyses/{analysis_id}/tasks/{task_id}
GET  /api/analyses/{analysis_id}/tasks/{task_id}/inputs
GET  /api/analyses/{analysis_id}/tasks/{task_id}/results
```

### Retournement

`rollover` est une tache metier specialisee.

```text
POST   /api/analyses/{analysis_id}/rollover/analyze
GET    /api/analyses/{analysis_id}/rollover
GET    /api/analyses/{analysis_id}/rollover/{result_id}
DELETE /api/analyses/{analysis_id}/rollover/{result_id}
POST   /api/analyses/{analysis_id}/rollover/{result_id}/versions
GET    /api/analyses/{analysis_id}/files/{file_id}/rollover-ltr
```

### Modeles

```text
GET  /api/analyses/{analysis_id}/models
POST /api/analyses/{analysis_id}/models
GET  /api/analyses/{analysis_id}/models/{model_id}
POST /api/analyses/{analysis_id}/models/{model_id}/train
GET  /api/analyses/{analysis_id}/models/{model_id}/versions
GET  /api/analyses/{analysis_id}/model-versions/{model_version_id}
GET  /api/analyses/{analysis_id}/model-versions/{model_version_id}/splits
GET  /api/analyses/{analysis_id}/model-versions/{model_version_id}/artifacts
```

### Predictions

```text
POST /api/analyses/{analysis_id}/model-versions/{model_version_id}/predict
GET  /api/analyses/{analysis_id}/model-versions/{model_version_id}/predictions
GET  /api/analyses/{analysis_id}/model-versions/{model_version_id}/predictions/{file_id}
```

## Endpoints globaux a eviter

Les endpoints suivants ne doivent pas exister dans la nouvelle app comme source
principale :

```text
/api/files
/api/annotations/segments
/api/exploration/files
/api/exploration/signals/*
/api/file/{json_name}/*
/api/rollover/*
/api/segment-model/*
/api/dxd-channel-analysis/*
```

Ils pourront eventuellement exister temporairement pendant un developpement local,
mais uniquement comme adaptateurs qui exigent un `analysis_id`.

## Workflow cible depuis zero

1. Creer une analyse.
2. Declarer le dossier de campagne `.dxd`.
3. Scanner les acquisitions et remplir `analysis_files`.
4. Analyser la structure recurrente des canaux.
5. Choisir le sous-ensemble de canaux.
6. Choisir les indicateurs dynamiques calculables a partir des canaux retenus.
7. Choisir le sampling JSON : frequence cible, methode d'interpolation, dossier
   cible derive du nom de l'analyse.
8. Exporter les JSON re-echantillonnes dans le dossier de l'analyse.
9. Creer un jeu d'annotations.
10. Annoter des segments avec versionnage.
11. Lancer des taches metier comme `rollover` sur fichiers ou versions
   d'annotations.
12. Entrainer des modeles rattaches a l'analyse.
13. Stocker les poids sur disque, indexes par `model_artifacts`.
14. Generer des predictions rattachees a une version de modele.
15. Consulter exploration descriptive, annotations, predictions et resultats via
    des endpoints scopes par `analysis_id`.

## Interface actuelle app_v2

L'interface actuelle met en place le debut du workflow cible dans l'onglet
principal `Creer une analyse`.

Sous-onglets :

1. `Fichiers DXD` : nom de l'analyse, dossier source DXD, rattachement des
   fichiers et scan recursif optionnel.
2. `Canaux DXD` : scan de la structure DXD, selection des canaux recurrents,
   sauvegarde de la structure et affichage de la structure active.
3. `Indicateurs dynamiques` : selection des indicateurs calculables selon les
   canaux sauvegardes. Les indicateurs indisponibles restent visibles avec leurs
   canaux manquants.
4. `Sampling JSON` : frequence cible, methode d'interpolation, dossier JSON
   cible, bouton final de creation qui lance l'export JSON avec barre de
   progression.

Les anciens onglets principaux `Canaux DXD` et `Resampling` ont ete retires
pour eviter la redondance avec ce workflow sequentiel.

Un onglet principal `Choix analyse` liste les analyses disponibles. Le choix
d'une analyse charge un resume comprenant notamment :

- la frequence d'echantillonnage ;
- la methode d'interpolation ;
- le dossier JSON cible ;
- le nombre de fichiers DXD ;
- le nombre de JSON exportes ;
- le nombre de canaux selectionnes ;
- le nombre de canaux recurrents.

## Decisions actees

- Pas de migration des donnees courantes.
- Repartir de zero dans `app_v2`.
- SQLite est la source de verite metier.
- Les `.dxd`, les `.json` de resampling et les artefacts visuels d'analyse
  dynamique sont les donnees applicatives autorisees sur disque aujourd'hui.
- Les JSON de resampling sont stockes dans
  `app_v2/data/{nom_analyse_normalise}/resampled_json`.
- Les poids de modeles restent une cible future : s'ils sont ajoutes plus tard,
  ils devront rester localement sur disque et etre rattaches a une version de
  modele en base.
- Les annotations sont versionnees.
- Les splits train/validation/test sont rattaches a une version de modele.
- Les predictions sont accessibles par endpoints.
- La vue actuellement nommee "Drift" est une exploration descriptive par labels,
  pas une analyse metier et pas du monitoring de modele.
