# DynaScope - version reproductible

Ce dossier est un snapshot isolable de la version courante de `app_v2`.

Il contient :

- `app_v2/` : application FastAPI + UI ;
- `src/mas_essais/domain` et `src/mas_essais/io` : modules locaux minimaux requis par `app_v2` ;
- `DWDataReader_v5_0_4/examples/Python` : SDK minimal de lecture des fichiers `.dxd` ;
- `requirements.txt` et `pyproject.toml` : dépendances Python du projet.

Il ne contient pas :

- les donnees `.dxd` ;
- les exports JSON resamples ;
- la base SQLite runtime ;
- les artefacts LLM/images generes ;
- les caches Python/tests.

## Installation

Depuis ce dossier :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copier `.env.example` vers `.env`, puis renseigner les valeurs utiles.

Par defaut, l'application peut fonctionner avec :

```bash
MAS_APP_V2_DATA_DIR=app_v2/data
MAS_APP_V2_DB_PATH=app_v2/pipeline_v2.sqlite
```

Les acquisitions `.dxd` peuvent etre placees dans :

```text
app_v2/data/acquisitions/
```

Les campagnes creeront ensuite leurs dossiers de sortie sous :

```text
app_v2/data/<nom_campagne>/resampled_json/
app_v2/data/<nom_campagne>/model_artifacts/
```

## Lancement

Depuis ce dossier :

```bash
python -m uvicorn app_v2.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Puis ouvrir :

```text
http://127.0.0.1:8000/login
```

En V1, la page de connexion accepte n'importe quel identifiant et mot de passe.

## Verification rapide

```bash
python -m pytest app_v2/tests
```

## Notes de reproductibilite

- Ne pas reutiliser la base SQLite de l'ancien repo si l'objectif est un essai propre.
- Ne pas pointer `MAS_APP_V2_DATA_DIR` vers un dossier partage avec une autre version.
- Ne pas commit la cle `GEMINI_API_KEY` dans `.env`.
- Si la lecture `.dxd` echoue, verifier que `DWDataReader_v5_0_4/examples/Python/DWDataReaderLib64.so` est present.
