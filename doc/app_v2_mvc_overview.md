# App v2 - Lecture MVC

## Synthese

`app_v2` est une application FastAPI avec une UI statique HTML/CSS/JS.
Le decoupage ressemble a un MVC web :

- **Modele** : base SQLite, schema SQL, repositories, services metier.
- **Controleurs** : routes FastAPI sous `/api/...`.
- **Vue** : `index.html`, `styles.css`, `app.js`, avec Plotly cote navigateur.

La logique produit est **analyse-centrique** : une `analysis` est la racine.
Les fichiers DXD, JSON resamples, canaux, annotations et analyses dynamiques sont
rattaches a une analyse.

## Carte MVC

| Couche | Fichiers principaux | Responsabilite |
| --- | --- | --- |
| Modele persistant | `app_v2/app/db/schema.sql` | Tables, relations, contraintes SQLite |
| Acces donnees | `app_v2/app/db/repositories/*.py` | CRUD, conversions JSON, requetes specialisees |
| Services metier | `app_v2/app/services/*.py`, `app_v2/app/domain/*.py` | Scan DXD, structure canaux, export JSON, taches longues |
| Controleurs API | `app_v2/app/api/routes/*.py` | Validation HTTP, orchestration repositories/services |
| Vue | `app_v2/app/static/index.html` | Structure des onglets et formulaires |
| View model front | `app_v2/app/static/app.js` | Etat UI, appels API, rendu DOM/Plotly |
| Style | `app_v2/app/static/styles.css` | Charte claire, panels, tableaux, onglets |

## Flux principaux

### Creation analyse

1. L'UI cree une analyse via `POST /api/analyses`.
2. Les DXD sont rattaches via `POST /api/analyses/{analysis_id}/files/discover-dxd`.
3. Le scan canaux est lance via `POST /api/analyses/{analysis_id}/channels/analyze`.
4. Une structure de canaux validee est sauvegardee.
5. Les indicateurs dynamiques calculables sont choisis et sauvegardes.
6. Le sampling JSON exporte les fichiers resamples et les indicateurs retenus.

### Exploration

1. L'utilisateur choisit une analyse active dans `Choix analyse`.
2. L'UI charge les fichiers resamples disponibles.
3. La vision temporelle demande les series et la trajectoire.
4. La vision parametrique demande un nuage de points canal X / canal Y.

### Annotations

1. Les labels disponibles sont administres dans le catalogue.
2. L'utilisateur selectionne un fichier et des canaux.
3. Il selectionne un segment temporel sur le graphe.
4. Une annotation est creee, modifiee ou supprimee.

### Analyse dynamique

1. Une analyse dynamique est creee avec un nom, un prompt systeme, des canaux et labels pertinents.
2. Si le nom existe deja pour l'analyse active, le `POST` ecrase l'ancienne definition.
3. L'utilisateur choisit une analyse dynamique existante.
4. La generation se fait annotation par annotation.
5. Une prediction LLM dry-run ou provider est stockee, avec artefact visuel et synthese.

## Points d'attention

- Le front est une application mono-page sans framework.
- `app.js` combine etat, appels API et rendu DOM : c'est le view model principal.
- Les champs JSON SQLite portent beaucoup de configuration flexible.
- Les taches longues sont gerees en memoire par des task managers, avec polling API.
- Les exports/artefacts sont des fichiers sur disque references depuis la base.
