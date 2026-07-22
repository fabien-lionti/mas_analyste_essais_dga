# MAS Analyste Essais DGA

Outils Python pour analyser des essais vehicule issus d'acquisitions Dewesoft
`.dxd`. Le depot contient une chaine de traitement qui lit les fichiers bruts,
extrait les canaux utiles, re-echantillonne les signaux, calcule des indicateurs
de qualite et expose les resultats dans une petite interface FastAPI.

Le depot a ete nettoye pour ne garder que les sources, les donnees brutes et les
ressources necessaires. Les environnements virtuels, caches Python, exports JSON,
index CSV/JSON et rendus de visualisation sont regenerables et ignores par Git.

## Structure du depot

- `src/mas_essais/` : package Python principal.
  - `api/` : application FastAPI.
  - `db/` : acces SQLite et repositories bas niveau.
  - `domain/` : schemas, normalisation et logique metier.
  - `io/` : lecteurs de fichiers externes, dont Dewesoft.
  - `ml/` : modeles et entrainements.
- `scripts/` : commandes de pipeline et d'entrainement lancables directement.
- `app.py` : point d'entree de compatibilite pour lancer FastAPI avec
  `uvicorn app:app`.
- `data/` : acquisitions brutes `.dxd`. Ces fichiers sont volumineux et restent
  la source de verite locale.
- `DWDataReader_v5_0_4/` : SDK Dewesoft fourni avec le projet, dont les binaires
  natifs et exemples Python/C/Matlab.
- `scripts/scan_dxd_channel_presence.py` : pipeline principal. Il scanne `data/*.dxd`,
  verifie les canaux cibles, exporte les JSON re-echantillonnes et produit les
  index de suivi.
- `scripts/extract_features.py` : extraction de features univariees par fenetre
  depuis les JSON re-echantillonnes.
- `build_window_quality_index.py` : calcule les scores de qualite et de
  coherence physique par fenetre.
- `build_window_cluster_index.py` : regroupe les fenetres comparables par
  clustering DBSCAN sur des criteres dynamiques standardises.
- `build_speed_day_summary.py` : agrege les scores de qualite par jour et classe
  de vitesse.
- `build_drift_index.py` : construit un index compact des features globales pour
  les vues de derive.
- `build_correlation_anomaly_index.py` : detecte des ruptures de relation entre
  capteurs par type de piste.
- `scripts/migrate_pipeline_to_sqlite.py` : migration des artefacts CSV/JSON
  vers `pipeline.sqlite`.
- `static/index.html` : interface de consultation.
- `specs/` : notes/specifications fonctionnelles et techniques.

## Prerequis

- Python 3.10 ou plus recent.
- Acces au module Python `dwdatareader`.
- Acces au binaire natif Dewesoft `DWDataReaderLib64.so` sur Linux.

Les scripts chargent automatiquement le premier binaire trouve parmi :

```text
DWDataReaderLib64.so
DWDataReader_v5_0_4/examples/Python/DWDataReaderLib64.so
DWDataReader_v5_0_4/examples/C/DWDataReaderLib64.so
DWDataReader_v5_0_4/examples/Matlab/DWDataReaderLib64.so
```

Si le module `dwdatareader` n'est pas installe dans l'environnement Python, suivre
la procedure Dewesoft fournie avec le SDK ou ajouter le chemin du wrapper Python
a `PYTHONPATH`.

## Installation

Depuis la racine du depot :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Les dependances Python declarees sont volontairement courtes :

- `fastapi` et `uvicorn` pour l'application web.
- `numpy`, `pandas` et `tqdm` pour les traitements.
- `python-dotenv` pour charger une configuration locale si besoin.

## Chaine de traitement recommandee

1. Verifier que les fichiers `.dxd` sont presents dans `data/`.

2. Scanner et convertir les acquisitions :

```bash
python scripts/scan_dxd_channel_presence.py
```

Sorties principales :

- `channel_presence.csv`
- `dataset_index.json`
- `selected_dxd_json_resampled/*.json`

Les JSON contiennent les signaux re-echantillonnes a 100 Hz, les metadonnees de
fichier, le statut d'ouverture, les canaux manquants et des features glissantes
lorsqu'elles peuvent etre calculees.

3. Calculer l'index de qualite par fenetre :

```bash
python build_window_quality_index.py
```

Options utiles :

```bash
python build_window_quality_index.py --window-sec 4 --stride-sec 1
python build_window_quality_index.py --max-files 10
```

Sorties :

- `window_quality_index.csv`
- `window_quality_summary.json`

5. Construire les clusters de fenetres comparables :

```bash
python build_window_cluster_index.py
```

Sorties :

- `window_cluster_index.csv`
- `window_cluster_summary.json`

6. Agreger la qualite par jour et classe de vitesse :

```bash
python build_speed_day_summary.py
```

Sorties :

- `speed_day_summary.csv`
- `speed_day_summary.json`

7. Construire les index de consultation :

```bash
python build_drift_index.py
python build_correlation_anomaly_index.py
```

Sorties :

- `drift_index.json`
- `correlation_anomaly_index.json`

8. Migrer les artefacts vers SQLite, si l'on veut utiliser une base unique pour
   l'application :

```bash
python scripts/migrate_pipeline_to_sqlite.py
```

Sortie :

- `pipeline.sqlite`

Par defaut, le script importe les index JSON/CSV, les annotations et les exports
JSON re-echantillonnes. Pour ne migrer que les index et annotations, sans les
JSON volumineux :

```bash
python scripts/migrate_pipeline_to_sqlite.py --skip-resampled-json
```

L'application FastAPI utilise `pipeline.sqlite` en priorite quand la base existe
et retombe sur les fichiers CSV/JSON historiques sinon.

9. Lancer l'application :

```bash
uvicorn app:app --reload
```

Interface : `http://127.0.0.1:8000/`

## Application web et API

L'application lit les fichiers generes a la racine du depot et dans
`selected_dxd_json_resampled/`. Si un index manque, les endpoints concernes
renvoient un message indiquant la commande a lancer.

Endpoints principaux :

- `GET /` : interface web.
- `GET /api/health` : etat rapide de l'application et disponibilite des donnees.
- `GET /api/files` : liste des fichiers exportes ou references dans
  `dataset_index.json`.
- `GET /api/file/{json_name}/summary` : resume d'un export JSON.
- `GET /api/file/{json_name}/channels` : canaux disponibles.
- `GET /api/file/{json_name}/series` : series temporelles pour un ou plusieurs
  canaux.
- `GET /api/file/{json_name}/features/global` : features globales.
- `GET /api/file/{json_name}/features/sliding` : features glissantes.
- `GET /api/drift/options` et `GET /api/drift/global-feature` : vues de derive.
- `GET /api/window-quality/summary` et `GET /api/window-quality` : index qualite.
- `GET /api/speed-day-summary/summary` et `GET /api/speed-day-summary` :
  aggregation qualite/vitesse/jour.
- `GET /api/correlation-anomalies/summary` et
  `GET /api/correlation-anomalies` : anomalies relationnelles entre capteurs.
- `GET /api/correlation-baseline/{track_id}` : baseline d'une piste.

## Donnees et artefacts ignores

Les motifs suivants sont ignores par Git :

- environnements locaux : `.venv/`, `.venv312/`, `venv/`, `env/`
- caches : `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- configuration locale : `.env`
- donnees et sorties volumineuses : `*.dxd`, `*.json`, `*.csv`
- exports regenerables : `selected_dxd_json_resampled/`,
  `vehicle_windows_*/`, `viz_selected_windows/`, `agent_outputs/`

Consequence pratique : apres un clone propre, il faut disposer des `.dxd` locaux
et relancer la chaine de traitement pour reconstruire les JSON et index.

## Nettoyage effectue

Les elements suivants ont ete supprimes car ils etaient locaux ou regenerables :

- `.venv/`
- `.venv312/`
- `__pycache__/`
- `.env`
- `agent_outputs/`
- `viz_selected_windows/`
- `vehicle_windows_2025_04_24_vx40_50hz/`
- `selected_dxd_json_resampled/`
- `drift_index.json`
- `correlation_anomaly_index.json`
- `window_quality_index.csv`
- `window_quality_summary.json`
- `speed_day_summary.csv`
- `speed_day_summary.json`

## Notes de maintenance

- Les scripts supposent une execution depuis la racine du depot.
- `scripts/scan_dxd_channel_presence.py` est le point d'entree principal. Il remplace
  en pratique l'ancien couple scan/export separe.
- `src/mas_essais/domain/dxd_schema.py` centralise les conversions d'unites et noms canoniques. Ajouter
  un nouveau canal ici evite de dupliquer la logique dans l'application.
- Les fichiers `.dxd` occupent la majorite de l'espace disque. Ne les supprimer
  que si une copie source existe ailleurs.
