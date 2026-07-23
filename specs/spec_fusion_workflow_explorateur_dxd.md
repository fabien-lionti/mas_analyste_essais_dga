# Spec — Fusion des vues "Canaux DXD" et "Validité des fichiers" en workflow unique

## Contexte

L'Explorateur DXD expose aujourd'hui deux vues indépendantes qui portent en réalité sur le même pipeline de traitement d'une campagne d'essais :

- **`?view=channels`** — Analyse des canaux DXD : scan des 492 fichiers `.dxd`, vérification de présence des canaux cibles, identification de la structure récurrente de la campagne, export JSON rééchantillonné.
- **`?view=validity`** — Validité des fichiers : synthèse par fichier (Open / Resampled / Missing / Annotations), accès aux actions en aval (voir données, LTR, Annoter, voir drift).

Ces deux vues partagent le même référentiel de fichiers (492 fichiers, mêmes noms) mais sont navigées comme deux outils séparés, avec des URLs et des contextes distincts. L'utilisateur doit changer de vue mentalement pour comprendre "où en est" un fichier dans le pipeline complet (scan → validation canaux → resampling → export → contrôle qualité → annotation → drift).

## Problème à résoudre

Il n'existe pas aujourd'hui de représentation unique de l'état d'un fichier à travers tout le pipeline. Pour savoir si `rodage_2025_04_14_0001.dxd` est prêt à être utilisé pour l'entraînement du modèle, l'utilisateur doit :
1. Aller sur `channels` pour vérifier la présence des canaux,
2. Aller sur `validity` pour vérifier Open/Resampled/Missing/Annotations,
3. Naviguer encore ailleurs pour drift et annotations détaillées.

**Objectif** : fusionner ces vues en un **workflow séquentiel unique**, où chaque fichier progresse visiblement à travers des étapes, et où l'utilisateur peut agir sur un fichier ou un lot de fichiers sans changer de contexte.

## Principe directeur : un pipeline en étapes (stepper), pas deux tableaux

Modéliser le traitement de chaque fichier `.dxd` comme une progression à travers des **étapes nommées et ordonnées** :

```
1. Scan          → fichier détecté, ouvrable, lisible (Open)
2. Canaux        → présence des canaux cibles vérifiée (Canaux cibles présentes/manquantes)
3. Resampling    → rééchantillonnage effectué (Resampled)
4. Export        → export JSON/campagne généré
5. Contrôle      → Missing count, statut OK/problème
6. Annotation     → annotations manuelles (179 annotations aujourd'hui)
7. Drift          → surveillance/predictions du modèle CNN (runs drift)
```

Chaque fichier a un statut par étape (`ok`, `attention`, `erreur`, `non lancé`), et un statut global agrégé (les "10 problème(s)" actuels).

## Proposition d'écran unique

### 1. Bandeau de synthèse global (fusion des deux bandeaux actuels)
Combiner les deux barres de compteurs existantes en une seule :
- 492 fichiers
- 482 fichiers OK / 10 en problème
- 179 annotations
- Modèle CNN : ok
- 6 runs drift
- (nouveau) Canaux récurrents identifiés : 16

### 2. Table unique par fichier, avec colonnes = étapes du pipeline

Remplacer les deux tableaux ("Résultats" de `channels` et "Table de synthèse" de `validity`) par **une seule ligne par fichier**, avec une cellule par étape affichant une pastille de statut (✅ / ⚠️ / ❌ / — ), et non plus deux tableaux à corréler manuellement :

| Fichier | Date | Scan | Canaux | Resampled | Missing | Annotations | Drift | Actions |
|---|---|---|---|---|---|---|---|---|
| rodage_2025_04_14_0001.dxd | 2025_04_14 | ✅ | 40/40 | ✅ | 0 | 0 | Voir drift | ⋯ |

- Cliquer sur une pastille d'étape (ex. "Canaux") ouvre un panneau latéral (drawer) avec le détail de cette étape pour ce fichier (liste des canaux présents/manquants, fréquence d'échantillonnage), **sans quitter la table**.
- Le menu "Actions" (⋯) regroupe les actions actuellement dispersées : *Voir données*, *LTR*, *Annoter*, *Voir drift*, *Réexécuter cette étape*.

### 3. Filtres et tri unifiés

Un seul jeu de filtres au-dessus de la table, applicable à toutes les étapes :
- Par statut global (OK / problème)
- Par étape en échec (ex. "Canaux manquants", "Resampling échoué")
- Par pattern de nom de fichier / famille d'essai (le filtre "Nom ou unité" actuel de `channels` est trop limité — il ne filtrait que les canaux, pas les fichiers)
- Par date de campagne

### 4. Actions de lot (batch), au niveau workflow et non plus par vue isolée

Aujourd'hui "Lancer l'analyse des canaux" et "Exporter la campagne JSON" sont deux boutons isolés sur la vue `channels`. Dans le workflow fusionné :
- Un bouton **"Exécuter le pipeline"** en haut de la table, avec un sélecteur d'étapes à lancer (checkbox : Scan / Canaux / Resampling / Export), applicable sur toute la campagne ou sur la sélection de fichiers filtrée.
- Barre de progression unique montrant l'étape en cours (remplace le journal `[373/492]` en cours de défilement) avec un résumé "Étape 3/6 — Resampling — 210/492 fichiers traités".
- Historique des runs (le "6 runs drift" existant devient un exemple d'un concept plus large : chaque étape a un historique de runs, consultable).

### 5. Panneau de détail par fichier (nouveau, transverse)

Cliquer sur le nom d'un fichier ouvre une vue détail unique regroupant :
- Statut de chaque étape du pipeline avec horodatage du dernier run
- Liste complète des canaux (présents, manquants, unité, échantillonnage)
- Annotations existantes pour ce fichier
- Résultat du run drift le plus récent
- Bouton "Relancer depuis l'étape X"

C'est la fusion concrète des deux vues au niveau fichier : plus besoin de changer d'URL pour croiser les informations `channels` et `validity`.

## Ce qui NE change pas (pour limiter le risque de régression)

- Les traitements backend existants (scan `.dxd`, calcul de présence des canaux, resampling, export JSON, modèle CNN, calcul de drift) restent des opérations indépendantes côté serveur. La fusion est **une fusion de présentation et de navigation**, pas une réécriture du pipeline de traitement.
- Les exports actuels (`channel_presence.csv`, export JSON campagne) restent disponibles tels quels, simplement déclenchables depuis un seul endroit.
- Les fonctionnalités "Annoter", "Voir drift", "LTR" restent des vues dédiées (elles ont probablement une complexité d'interaction propre qui justifie de rester des écrans séparés, ouverts en drawer ou nouvel onglet depuis la table unique).

## Vue de configuration du pipeline (nouveau)

Aujourd'hui, les règles qui définissent ce qu'est un fichier "valide" sont implicites ou dispersées (ex. "40/40 canaux cibles" apparaît comme un résultat, mais on ne voit nulle part où cette cible de 40 est définie et modifiable). Il manque un écran de configuration, en amont du pipeline, qui centralise les règles utilisées à chaque étape.

Cette vue serait accessible via un bouton "Configurer" à côté du bouton "Exécuter le pipeline", et couvrirait :

### 1. Canaux minimum requis
- Liste éditable des canaux obligatoires pour qu'un fichier soit considéré "valide" (ex. les 16 canaux récurrents déjà détectés : `VelX`, `VelY`, `Vel`, `VehYaw_W_Actl`, etc.).
- Possibilité de définir plusieurs presets de canaux minimum selon le type d'essai (ex. un preset "essais dynamiques" avec les canaux d'accélération/vitesse, un preset "essais statiques" plus restreint) — cela fait écho au "Sélectionner le preset" déjà présent dans l'export, mais qui devrait piloter aussi la validation, pas seulement l'export.
- Seuil configurable : "un fichier est valide si X% des canaux du preset sont présents" plutôt qu'un tout-ou-rien.

### 2. Standardisation des noms de canaux (mapping)
- Table de correspondance éditable **nom brut du capteur → nom standardisé** (ex. le tableau actuel montre déjà des noms bruts vs noms affichés — `AccX_body (m/s_)` où l'unité semble mal encodée, probablement `m/s²` corrompu à l'export PDF). Cette table doit être un objet de configuration explicite, pas un simple affichage.
- Gestion des synonymes/variantes historiques : si un canal a changé de nom entre deux campagnes (ex. capteur remplacé, convention renommée), le mapping permet de les traiter comme équivalents pour la comparaison inter-campagnes.
- Normalisation des unités en parallèle du nom (ex. forcer `m/s^2` partout, détecter et corriger les caractères mal encodés comme `_` à la place de `²`).
- Validation du mapping : détection des noms de canaux présents dans les fichiers mais absents du référentiel de standardisation ("canaux orphelins" à traiter avant export).

### 3. Fréquence d'échantillonnage
- Fréquence cible unique pour le rééchantillonnage (aujourd'hui invisible dans l'écran d'export — on voit "5000" comme fréquence native des fichiers mais pas la fréquence de sortie choisie).
- Méthode de rééchantillonnage configurable : décimation simple, interpolation linéaire, filtre anti-repliement + décimation — avec une méthode par défaut recommandée et une explication courte de l'impact de chaque choix.
- Tolérance de fréquence native : si un fichier a une fréquence d'acquisition différente des autres (ex. 2000 Hz au lieu de 5000 Hz), définir la règle appliquée (rejet, avertissement, resampling adapté).

### 4. Portée et versionnement de la configuration
- Cette configuration doit être versionnée et horodatée (ex. "config v3, appliquée le 23/07/2026"), car changer les canaux minimum ou la fréquence cible change potentiellement le statut de validité de tous les fichiers déjà traités.
- Un changement de configuration devrait proposer explicitement "Réappliquer cette configuration à tous les fichiers existants ?" plutôt que de laisser une incohérence silencieuse entre anciens et nouveaux runs.
- La configuration active doit être visible en permanence dans le bandeau de synthèse global (ex. "Config canaux : preset Dynamique v3 · Fréquence cible : 100 Hz"), pour qu'on sache toujours sous quelles règles les statuts affichés ont été calculés.

## Modèle de données requis (à confirmer côté backend)

Pour alimenter la table unique, il faut une structure par fichier qui agrège ce qui est aujourd'hui réparti entre les deux vues, par exemple :

```json
{
  "file": "rodage_2025_04_14_0001.dxd",
  "date": "2025_04_14",
  "config_version": "v3",
  "steps": {
    "scan": { "status": "ok", "last_run": "2026-07-23T13:52:00" },
    "channels": { "status": "ok", "present": 40, "total": 40, "missing": [] },
    "resampled": { "status": "ok" },
    "export": { "status": "ok" }
  },
  "missing_count": 0,
  "annotations_count": 0,
  "drift": { "status": "ok", "last_run_id": "run_6" }
}
```

Si cette agrégation n'existe pas encore côté backend, prévoir un endpoint (ou une vue matérialisée) `GET /api/pipeline-status` qui renvoie cette structure pour tous les fichiers, au lieu de deux endpoints séparés interrogés indépendamment par le frontend.

## Critères d'acceptation

1. Un utilisateur peut voir, sur un seul écran, l'état complet d'un fichier à travers toutes les étapes du pipeline (scan → canaux → resampling → export → annotations → drift).
2. Un utilisateur peut filtrer la liste des 492 fichiers par étape en échec sans changer de vue.
3. Un utilisateur peut relancer une étape spécifique (ex. resampling uniquement) sur un sous-ensemble de fichiers filtré, depuis le même écran.
4. Les deux vues actuelles (`?view=channels` et `?view=validity`) peuvent être supprimées ou redirigées vers la nouvelle vue unifiée sans perte de fonctionnalité.
5. Le temps pour diagnostiquer "pourquoi ce fichier n'est pas prêt" passe de 2 vues + navigation manuelle à 1 clic sur la ligne du fichier.
6. Un utilisateur peut modifier la liste des canaux minimum requis, le mapping de standardisation des noms, et la fréquence d'échantillonnage cible depuis un écran de configuration dédié, sans toucher au code.
7. Toute modification de configuration est versionnée, horodatée, et le statut de validité des fichiers reflète clairement sous quelle version de configuration il a été calculé.

## Suggestion de nommage de la nouvelle vue

`?view=pipeline` ou `?view=workflow`, en remplacement des deux vues `channels` et `validity`.

## Annexe — Correspondance avec l'API existante (`main.py`)

Cette section ancre la spec dans le code réel, pour éviter que Codex ne réinvente des mécanismes déjà présents côté backend. La fusion proposée est donc majoritairement un travail de **présentation/agrégation**, pas de nouveau backend from scratch.

### Ce qui existe déjà et couvre les besoins identifiés

| Besoin exprimé dans la spec | Implémentation existante |
|---|---|
| Presets de canaux minimum / par famille d'essai | `channel_export_presets()` → `minimum`, `recurrent`, `app_default`, `annotator`, `rollover`, `all_canonical`. `MINIMUM_DXD_CHANNELS` déjà défini. |
| Standardisation des noms de canaux | `canonical_name_for()`, `source_name_for()`, `SPEC_BY_SOURCE`, `CHANNEL_SPECS` (module `dxd_schema`). Le mapping nom brut ↔ nom canonique tourne déjà à l'analyse et à l'export. |
| Fréquence d'échantillonnage cible configurable | Paramètre `target_hz` sur `/api/dxd-channel-analysis/export-json`, défaut `DEFAULT_DXD_EXPORT_HZ = 100.0`, validé par `validate_export_hz` (borné à 1000 Hz). |
| Seuil de tolérance sur les canaux récurrents | `recurrent_campaign_channels(min_frequency=0.8)`, exposé via `GET /api/dxd-channel-analysis/recurrent-channels?min_frequency=...`. |
| Historique des runs / traçabilité des analyses | `create_pipeline_analysis`, `list_pipeline_analyses`, `get_pipeline_analysis` — table sqlite générique avec `kind` (`dxd_channel_structure`, `dxd_campaign_export`, `dxd_file_export`, ...), `config`, `summary`, horodatage. |
| Détail des canaux par fichier | `GET /api/dxd-channel-analysis/channels/{file_name}` — déjà présent/manquant, unité, canonical_name. |
| Export JSON (fichier ou campagne) | `POST /api/dxd-channel-analysis/export-json` — mode fichier unique ou campagne complète en tâche de fond, avec suivi via `/export-status`. |
| Annotations de segments | `GET/POST/DELETE /api/annotations/segments`, `/api/annotations/segments/labels`, rename de label. |
| Drift / modèle CNN | Toute la famille `/api/drift-coherence/*` (runs, summary, batch-metrics, metrics-by-file, metrics-by-timebin, prediction-series, annotation-label-metrics, plots) + `/api/segment-model/*` pour le modèle de segmentation. |
| Qualité de fenêtre / LTR retournement | `/api/window-quality/*` et `/api/file/{json_name}/rollover-ltr`, `/api/rollover/analyze`. |

### Ce qui manque réellement pour réaliser la fusion

1. **Pas d'endpoint d'agrégation par fichier.** Il n'existe aujourd'hui aucun `GET /api/pipeline-status` (ou équivalent) qui renvoie, pour chaque fichier, le statut combiné scan/canaux/resampling/export/annotations/drift en un seul objet JSON. C'est le seul vrai développement backend nécessaire pour alimenter la table unique proposée — le reste peut être assemblé côté frontend en agrégeant les endpoints existants (`/api/files`, `/api/dxd-channel-analysis/status`, `/api/annotations/segments`, `/api/drift-coherence/{run_id}/metrics-by-file`), au moins dans une V1 sans nouveau endpoint.

2. **Pas de configuration versionnée/persistée.** Les choix de preset, `min_frequency`, `target_hz` sont passés à chaque appel (`export-json`, `run`, `recurrent-channels`) mais ne sont jamais sauvegardés comme "configuration active de la campagne". Il n'y a pas de table `pipeline_config` avec un numéro de version. À ajouter si on veut le point "config versionnée" de la spec — sinon, la vue de configuration proposée resterait un simple formulaire par run, sans mémoire d'une config par défaut.

3. **Le lien fichier ↔ run de drift n'est pas direct.** Les runs drift (`dynamic_channel_coherence*`) sont indépendants des analyses de canaux (`dxd_channel_structure` / `dxd_campaign_export`) dans la table `pipeline_analyses` — pas de clé commune évidente pour dire "ce fichier, dans ce run drift, correspond à cette analyse de canaux". À vérifier avant de construire la colonne "Drift" de la table unifiée : il faudra probablement joindre par `json_name` uniquement (le run le plus récent contenant ce fichier), pas par `analysis_id`.

4. **`recurrent` preset a une liste de canaux vide par défaut** (`"channels": []` dans `channel_export_presets()`), remplie dynamiquement uniquement via `/api/dxd-channel-analysis/export-options` qui interroge `recurrent_campaign_channels()`. À garder en tête : ce preset n'est pas statique comme les autres, il dépend d'une analyse déjà lancée.

### Recommandation d'implémentation en V1 (sans nouveau endpoint lourd)

Pour livrer vite une première version de la vue fusionnée sans attendre un endpoint d'agrégation :
- Le frontend appelle en parallèle `GET /api/files`, `GET /api/dxd-channel-analysis/status`, `GET /api/annotations/segments` (par fichier ou en lot), et `GET /api/drift-coherence/{run_id}/metrics-by-file`.
- Il fusionne les résultats côté client par `json_name` / `file` pour construire les lignes de la table unique.
- Si la volumétrie (492 fichiers × plusieurs endpoints) rend cette approche trop lente, c'est le signal pour prioriser la création d'un vrai endpoint `GET /api/pipeline-status` côté backend qui fait cette jointure côté serveur.


## Cartographie des vues existantes (autres que channels/validity)

| Vue | Route | Rôle observé | Endpoints API mobilisés |
|---|---|---|---|
| Exploration signaux par labels | `/drift-coherence` | Filtre par label + source (annotations/CNN), signal, agrégation temporelle ; trajectoire GPS filtrée, série temporelle, boîtes à moustaches par tranche de temps | `/api/exploration/*` |
| Annotateur actif de segments | `/annotator` | Fichiers prioritaires (incertitude modèle), segment courant + métriques, gestion des labels, suggestions CNN | `/api/annotator/*`, `/api/annotations/segments*`, `/api/segment-model/*` |
| Retournement (rollover) | `?view=rollover` | Seuils d'encodage, provider IA, historique des analyses versionnées, courbe LTR + canaux, correction humaine | `/api/file/{json_name}/rollover-ltr`, `/api/rollover/*` |
| Données d'essais (explorer) | `?view=explorer` | Canaux rééchantillonnés (max 2), série temporelle + trajectoire GPS, filtre par segment | `/api/file/{json_name}/series`, `/api/file/{json_name}/channels`, `/api/exploration/files` |

Ces 4 vues sont de vrais outils d'interaction (sliders, provider IA, historique versionné, active learning) — elles restent des **destinations** atteignables depuis la table unifiée (menu Actions), pas des candidates à la fusion. Seules `channels` et `validity` sont fusionnées.

## Plan d'exécution étape par étape pour Codex

Chaque étape doit être livrée, testée et validée avant de passer à la suivante. Ne pas paralléliser : les étapes 1 et 2 changent la base sur laquelle tout le reste s'appuie. Donner ces étapes à Codex une par une, pas toute la spec d'un coup.

### Étape 0 — Nettoyage de la dette technique (risque nul, aucun changement de comportement)
- Supprimer les fonctions mortes identifiées : `parse_acquisition_timestamp`, `time_bucket_for_value`, `aggregate_series`, `raw_json_to_dataframe`, `quantile_row`.
- Supprimer les constantes non référencées : `RESIDUAL_DRIFT_FAMILIES`, `DRIFT_INDEX_PATH`, `WINDOW_CLUSTER_SUMMARY_PATH`.
- Supprimer l'import `os` inutilisé.
- Faire pointer `api_annotator_file` sur la constante `ANNOTATOR_DXD_CHANNELS` au lieu de la liste dupliquée en dur.
- **Validation avant de continuer** : lancer la suite de tests existante (ou, à défaut, démarrer l'app et vérifier que toutes les vues actuelles répondent normalement). Aucune fonctionnalité visible ne doit changer.

### Étape 1 — Endpoint d'agrégation par fichier (backend uniquement, pas de nouvel écran)
- Créer `GET /api/pipeline-status` qui renvoie, pour chaque fichier, un objet combinant : statut scan/canaux (déjà dans `channel_analysis_details.json` / `dxd_channel_analysis/status`), statut resampling/export, `missing_target_count`, nombre d'annotations (`segment_annotations`), lien vers le dernier run drift disponible pour ce `json_name`.
- Support d'un paramètre `limit`/pagination si besoin vu le volume (492 fichiers).
- **Validation avant de continuer** : tester l'endpoint isolément (curl ou tests unitaires) sur un sous-ensemble de fichiers connus (ex. `rodage_2025_04_14_0001.dxd`, `angle braquage_2025_04_14_0001.dxd`), vérifier que chaque champ correspond à ce qu'affichent aujourd'hui `channels` et `validity` séparément.

### Étape 2 — Configuration versionnée (backend uniquement)
- Ajouter une table `pipeline_config` (ou artefact JSON versionné) : preset de canaux actif, `min_frequency`, `target_hz`, méthode de resampling, horodatage, numéro de version.
- Endpoint `GET /api/pipeline-config` (config active) et `POST /api/pipeline-config` (créer une nouvelle version).
- **Validation avant de continuer** : créer 2-3 versions de config via l'API, vérifier qu'elles sont bien horodatées et que l'ancienne reste consultable par son numéro de version.

### Étape 3 — Vue de configuration (frontend, nouvel écran isolé)
- Construire l'écran "Configurer" (canaux minimum, standardisation des noms, fréquence cible, méthode de resampling) branché sur les endpoints de l'étape 2.
- Cet écran peut être livré et testé indépendamment de la fusion des tableaux.
- **Validation avant de continuer** : changer une config depuis l'écran, vérifier qu'elle est bien persistée et rechargée au retour sur l'écran.

### Étape 4 — Table unifiée (frontend, nouvel écran `?view=pipeline`)
- Construire le nouvel écran consommant `GET /api/pipeline-status` : une ligne par fichier, une colonne par étape (Scan, Canaux, Resampling, Export, Missing, Annotations, Drift), filtres, tri.
- Garder les anciennes vues `channels` et `validity` accessibles en parallèle pendant cette étape (aucune suppression).
- **Validation avant de continuer** : comparer manuellement quelques lignes de la nouvelle table avec les deux anciens tableaux pour les mêmes fichiers, s'assurer qu'il n'y a pas de divergence.

### Étape 5 — Panneau de détail par fichier + actions
- Ajouter le clic sur une ligne → drawer de détail (canaux présents/manquants, annotations, dernier run drift).
- Ajouter le menu "Actions" par ligne (Voir données, LTR, Annoter, Voir drift) qui renvoie vers les 4 vues existantes cartographiées ci-dessus, sans les modifier.
- **Validation avant de continuer** : vérifier que chaque lien Action ouvre bien la bonne vue existante avec le bon fichier pré-sélectionné.

### Étape 6 — Actions de lot et exécution du pipeline
- Bouton "Exécuter le pipeline" avec sélection d'étapes, branché sur les endpoints déjà existants (`/api/dxd-channel-analysis/run`, `/api/dxd-channel-analysis/export-json` en mode campagne).
- Barre de progression unique agrégeant les statuts déjà exposés par `/api/dxd-channel-analysis/status` et `/api/dxd-channel-analysis/export-status`.
- **Validation avant de continuer** : lancer un run sur un sous-ensemble limité de fichiers (`limit`), vérifier que la progression s'affiche correctement de bout en bout.

### Étape 7 — Bascule et dépréciation des anciennes vues
- Une fois les étapes 1 à 6 validées en usage réel, rediriger `?view=channels` et `?view=validity` vers `?view=pipeline`.
- Ne supprimer le code des anciennes vues qu'après une période d'observation (garder la possibilité de rollback rapide).
- **Validation finale** : critères d'acceptation listés plus haut dans la spec, tous cochés.
