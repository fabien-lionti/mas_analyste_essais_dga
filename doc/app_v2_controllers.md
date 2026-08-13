# App v2 - Controleurs API

## Principe

Les controleurs sont les routes FastAPI dans `app_v2/app/api/routes`.

Ils font principalement :

- validation HTTP et Pydantic ;
- verification de l'existence de `analysis_id` ;
- appel aux repositories ;
- lancement de services/taches longues ;
- conversion des erreurs metier en `HTTPException`.

## Montage de l'application

Fichier : `app_v2/app/main.py`

Routes montees :

- `/api/analyses`
- `/api/analyses/{analysis_id}/files`
- `/api/analyses/{analysis_id}/channels`
- `/api/analyses/{analysis_id}/resampling`
- `/api/analyses/{analysis_id}/exploration`
- `/api/analyses/{analysis_id}/...` pour annotations
- `/api/analyses/{analysis_id}/dynamic-analysis`

La racine `/` sert `app_v2/app/static/index.html`.

## Analyses

Fichier : `routes/analyses.py`

Endpoints :

- `POST /api/analyses`
- `GET /api/analyses`
- `GET /api/analyses/{analysis_id}`
- `PATCH /api/analyses/{analysis_id}/config`
- `DELETE /api/analyses/{analysis_id}`
- `GET /api/analyses/{analysis_id}/events`

Responsabilite :

- creer et choisir une analyse ;
- mettre a jour la configuration ;
- supprimer une analyse complete ;
- exposer le journal d'evenements.

## Fichiers

Fichier : `routes/files.py`

Endpoints :

- `POST /api/analyses/{analysis_id}/files/discover-dxd`
- `GET /api/analyses/{analysis_id}/files`
- `GET /api/analyses/{analysis_id}/files/{file_id}`

Responsabilite :

- decouvrir les `.dxd` ;
- remplir `analysis_files` ;
- exposer le catalogue des fichiers.

## Canaux

Fichier : `routes/channels.py`

Endpoints principaux :

- `GET /api/analyses/{analysis_id}/channels/presets`
- `POST /api/analyses/{analysis_id}/channels/analyze`
- `GET /api/analyses/{analysis_id}/channels/tasks/current`
- `GET /api/analyses/{analysis_id}/channels/tasks/{task_id}`
- `POST /api/analyses/{analysis_id}/channels/tasks/{task_id}/cancel`
- `GET /api/analyses/{analysis_id}/channels/status`
- `GET /api/analyses/{analysis_id}/channels/presence`
- `GET /api/analyses/{analysis_id}/channels/recurrent`
- `GET /api/analyses/{analysis_id}/channels/inventory`
- `GET /api/analyses/{analysis_id}/channels/validated-structure`
- `POST /api/analyses/{analysis_id}/channels/validated-structure`
- `GET /api/analyses/{analysis_id}/channels/anomalies/files`
- `GET /api/analyses/{analysis_id}/channels/anomalies`

Responsabilite :

- scanner les structures DXD ;
- suivre les taches longues ;
- exposer les canaux recurrents ;
- sauvegarder la structure active ;
- afficher les anomalies.

## Resampling

Fichier : `routes/resampling.py`

Endpoints :

- `POST /api/analyses/{analysis_id}/resampling/export-json`
- `GET /api/analyses/{analysis_id}/resampling/tasks/current`
- `GET /api/analyses/{analysis_id}/resampling/tasks/{task_id}`
- `POST /api/analyses/{analysis_id}/resampling/tasks/{task_id}/cancel`

Responsabilite :

- lancer l'export JSON des DXD avec les canaux selectionnes ;
- stocker les JSON dans un dossier coherent avec l'analyse ;
- exposer la progression.

## Exploration

Fichier : `routes/exploration.py`

Endpoints :

- `GET /api/analyses/{analysis_id}/exploration/files`
- `GET /api/analyses/{analysis_id}/exploration/labels`
- `GET /api/analyses/{analysis_id}/exploration/date-range`
- `GET /api/analyses/{analysis_id}/exploration/parametric`
- `GET /api/analyses/{analysis_id}/exploration/files/{file_id}/signals/options`
- `GET /api/analyses/{analysis_id}/exploration/files/{file_id}/series`
- `GET /api/analyses/{analysis_id}/exploration/files/{file_id}/trajectory`

Responsabilite :

- lister les fichiers resamples explorables ;
- fournir les plages de dates depuis les metadonnees ;
- fournir les canaux disponibles ;
- fournir les series temporelles ;
- fournir la trajectoire GPS ;
- fournir les points de vision parametrique.

## Annotations

Fichier : `routes/annotations.py`

Endpoints :

- `GET /api/analyses/{analysis_id}/annotation-sets`
- `POST /api/analyses/{analysis_id}/annotation-sets`
- `GET /api/analyses/{analysis_id}/annotations`
- `POST /api/analyses/{analysis_id}/annotations`
- `GET /api/analyses/{analysis_id}/annotations/labels`
- `GET /api/analyses/{analysis_id}/annotation-labels`
- `POST /api/analyses/{analysis_id}/annotation-labels`
- `PATCH /api/analyses/{analysis_id}/annotation-labels/{label_id}`
- `DELETE /api/analyses/{analysis_id}/annotation-labels/{label_id}`
- `GET /api/analyses/{analysis_id}/annotations/summary`
- `PATCH /api/analyses/{analysis_id}/annotations/labels/{label}`
- `DELETE /api/analyses/{analysis_id}/annotations/labels/{label}`
- `GET /api/analyses/{analysis_id}/annotations/{annotation_id}`
- `PATCH /api/analyses/{analysis_id}/annotations/{annotation_id}`
- `DELETE /api/analyses/{analysis_id}/annotations/{annotation_id}`
- `GET /api/analyses/{analysis_id}/annotations/{annotation_id}/versions`

Responsabilite :

- administrer les labels ;
- creer, modifier et supprimer des annotations ;
- versionner les changements ;
- produire une synthese/catalogue.

## Analyse dynamique

Fichier : `routes/dynamic_analysis.py`

Endpoints produit recents :

- `GET /api/analyses/{analysis_id}/dynamic-analysis`
- `POST /api/analyses/{analysis_id}/dynamic-analysis`
- `PATCH /api/analyses/{analysis_id}/dynamic-analysis/{dynamic_analysis_id}`
- `DELETE /api/analyses/{analysis_id}/dynamic-analysis/{dynamic_analysis_id}`
- `GET /api/analyses/{analysis_id}/dynamic-analysis/{dynamic_analysis_id}/predictions`
- `POST /api/analyses/{analysis_id}/dynamic-analysis/{dynamic_analysis_id}/predictions`
- `POST /api/analyses/{analysis_id}/dynamic-analysis/{dynamic_analysis_id}/predictions/{annotation_id}`
- `GET /api/analyses/{analysis_id}/dynamic-analysis/predictions/{prediction_id}/corrections`
- `POST /api/analyses/{analysis_id}/dynamic-analysis/predictions/{prediction_id}/corrections`
- `POST /api/analyses/{analysis_id}/dynamic-analysis/context`

Endpoints de compatibilite :

- `/prompts`
- `/run`
- `/runs`
- `/runs/{run_id}/versions`

Responsabilite :

- definir une analyse dynamique rattachee a une analyse ;
- construire le contexte a partir des annotations et canaux selectionnes ;
- generer un artefact visuel par annotation ;
- appeler un provider multimodal si configure ;
- extraire `<analyse>`, `<note_analyse>` et `<synthese>` ;
- sauvegarder prediction et corrections.

## Regles transverses

- La plupart des endpoints appellent `require_analysis`.
- Les endpoints de fichier/verrouillage verifient aussi `file_id`.
- Les labels d'annotation doivent exister avant creation d'annotation.
- Les taches longues retournent un snapshot et sont suivies par polling.
- Les suppressions principales s'appuient sur les `FOREIGN KEY ... ON DELETE CASCADE`.
