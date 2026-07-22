# Spécification — Interface unifiée MAS Essais

## 1. Objectif

L'objectif est de mettre en cohérence les vues HTML existantes dans une interface unique, sans modifier leur fonctionnement métier. <ok>

Le nom d'application proposé pour le bandeau est :

```text
MAS Essais
```

La refonte doit conserver les vues actuelles autant que possible :

- mêmes endpoints ;
- mêmes calculs ;
- mêmes graphiques principaux ;
- mêmes interactions métier ;
- mêmes données d'entrée et de sortie.

L'évolution attendue est une enveloppe commune : un bandeau permanent, des styles homogènes, une navigation stable, un état partagé et des filtres transversaux disponibles dans les vues qui visualisent des données.

## 2. Principe de non-régression

La première règle est de ne pas casser l'existant.

Les pages actuelles doivent continuer à fonctionner comme aujourd'hui :

- `static/index.html` reste l'explorateur DXD et le tableau de bord principal ;
- `static/vehicle_segment_annotator.html` reste l'annotateur actif de segments ;
- `static/drift_coherence.html` reste la vue d'exploration par labels et signaux ;
- les routes existantes `/`, `/annotator` et `/drift-coherence` restent disponibles.

Les changements doivent être ajoutés autour des vues, ou sous forme d'options désactivables. Le mode par défaut d'une vue doit reproduire le comportement actuel.

## 3. Structure commune cible

Toutes les vues doivent partager la même logique de page :

```text
┌──────────────────────────────────────────────────────────────┐
│ Bandeau MAS Essais : Validité | Données | Annotateur | Drift  │
├───────────────┬──────────────────────────────────────────────┤
│ Filtres       │ Vue existante conservée                       │
│ et contexte   │ Graphiques, tableaux, détails, actions         │
└───────────────┴──────────────────────────────────────────────┘
```

Le bandeau est toujours visible et contient les quatre entrées :

```text
Validité
Données d'essais
Annotateur
Drift
```

Chaque entrée doit afficher l'état actif. Les libellés, l'ordre et la position ne changent pas d'une vue à l'autre.

## 4. État partagé

Les vues doivent pouvoir partager un contexte minimal afin d'éviter de ressaisir les mêmes informations.

État cible :

```json
{
  "activeView": "validity",
  "selectedFile": null,
  "selectedChannels": [],
  "timeRange": null,
  "selectedWindow": null,
  "selectedSegment": null,
  "selectedRun": null,
  "segmentSource": "none",
  "selectedLabels": [],
  "showSegmentOverlays": true
}
```

Cet état peut être porté par les paramètres d'URL lorsque c'est utile :

```text
/?view=explorer&file=example.json&channels=vehicle.vx,vehicle.ay
/?view=annotator&file=example.json
/?view=drift&file=example.json&segmentSource=annotations_cnn
```

## 5. Filtre transversal annotations / CNN

Toutes les vues qui affichent des données temporelles, des fenêtres ou des segments doivent proposer le même contrôle de source de segmentation.

Modes attendus :

```text
Aucun filtre segment
Annotations uniquement
Prédictions CNN uniquement
Annotations + prédictions CNN
```

Ce contrôle doit être désactivable. En mode `Aucun filtre segment`, la vue doit se comporter comme aujourd'hui.

Le contrôle sert à deux choses :

- filtrer les lignes, fenêtres ou segments affichés ;
- ajouter des surcouches temporelles sur les graphiques compatibles.

### 5.1 Comportement attendu par mode

```text
Aucun filtre segment
  -> comportement actuel exact
  -> aucune contrainte liée aux annotations ou au CNN

Annotations uniquement
  -> afficher ou mettre en évidence les segments annotés
  -> colorer les plages temporelles selon le label manuel

Prédictions CNN uniquement
  -> afficher ou mettre en évidence les fenêtres prédites
  -> colorer les plages temporelles selon le label prédit

Annotations + prédictions CNN
  -> afficher les deux sources
  -> signaler les accords et désaccords
```

### 5.2 Sources existantes

Les données doivent être reprises depuis l'existant :

- annotations : `/api/annotations/segments` ;
- labels d'annotations : `/api/annotations/segments/labels` ;
- prédictions CNN par fichier : `/api/segment-model/file/{json_name}` ;
- résumé du modèle CNN : `/api/segment-model/summary` ;
- fichier global si disponible : `cnn_window_predictions.csv`.

La spec ne demande pas de relancer l'entraînement CNN depuis les vues de visualisation.

### 5.3 Modèle commun côté interface

Les annotations et prédictions doivent être normalisées côté interface vers une structure commune.

Annotation :

```json
{
  "source": "annotation",
  "file": "example.json",
  "start_s": 12.4,
  "end_s": 18.2,
  "label": "straight_constant_speed",
  "confidence": null,
  "status": "manual"
}
```

Prédiction CNN :

```json
{
  "source": "cnn",
  "file": "example.json",
  "start_s": 12.4,
  "end_s": 18.2,
  "label": "cornering_left",
  "confidence": 0.87,
  "status": "predicted"
}
```

## 6. Vue Validité des fichiers

### 6.1 Position dans l'application

La vue `Validité` est une nouvelle vue de synthèse. Elle peut être intégrée dans `static/index.html` comme onglet ou vue interne, sans retirer l'explorateur DXD existant.

Route cible recommandée :

```text
/?view=validity
```

La route `/` peut ouvrir `Validité` par défaut si l'équipe veut faire de la qualité le point d'entrée. Sinon, `/` peut continuer à ouvrir l'explorateur et le bandeau permet d'aller vers `Validité`.

### 6.2 Rôle

Cette vue répond à la question :

> Quels fichiers sont présents, lisibles, complets et exploitables ?

Elle doit agréger les informations déjà disponibles sur :

- fichiers `.dxd` présents ;
- exports JSON resamplés ;
- erreurs d'ouverture ;
- canaux manquants ;
- index de qualité ;
- disponibilité des annotations ;
- disponibilité des prédictions CNN ;
- disponibilité des analyses de drift.

### 6.3 Contenu attendu

KPI de synthèse :

```text
fichiers bruts
fichiers exportés
fichiers en erreur
fichiers incomplets
fenêtres exploitables
segments annotés
prédictions CNN disponibles
runs drift disponibles
```

Table principale :

```text
fichier
date
statut ouverture
statut export JSON
canaux manquants
score qualité global
segments annotés
prédictions CNN
runs drift liés
actions
```

Actions par ligne :

```text
Voir données
Annoter
Voir drift
```

Ces actions changent seulement de vue et propagent le fichier sélectionné.

### 6.4 Endpoints utiles

La vue peut utiliser :

- `/api/health` ;
- `/api/files` ;
- `/api/window-quality/summary` ;
- `/api/window-quality` ;
- `/api/annotations/segments` ;
- `/api/segment-model/summary` ;
- `/api/drift-coherence/runs`.

## 7. Vue Données d'essais

### 7.1 Vue existante concernée

Vue actuelle :

```text
static/index.html
route /
titre actuel : Explorateur DXD
```

Cette vue est le coeur de visualisation des acquisitions. Elle doit être conservée fonctionnellement.

Route cible recommandée :

```text
/?view=explorer
```

Une route explicite optionnelle peut être ajoutée :

```text
/explorer
```

### 7.2 Fonctionnement à conserver

La vue doit conserver :

- la sélection de fichier ;
- la liste des canaux ;
- les séries temporelles Plotly ;
- les features globales ;
- les features glissantes ;
- les vues de qualité et de dérive déjà présentes dans l'explorateur ;
- les endpoints `/api/file/{json_name}/...`.

Aucun renommage de données ou changement de calcul n'est attendu dans cette phase.

### 7.3 Mise en cohérence UI

À ajouter autour de l'existant :

- bandeau `MAS Essais` ;
- entrée active `Données d'essais` ;
- styles communs pour boutons, cartes, onglets et tables ;
- propagation du fichier sélectionné vers les autres vues ;
- lecture des paramètres d'URL `file`, `channels`, `timeStart`, `timeEnd`.

### 7.4 Ajout annotations / CNN

Cette vue doit intégrer le contrôle transversal :

```text
Source segments
  - Aucun filtre segment
  - Annotations uniquement
  - Prédictions CNN uniquement
  - Annotations + prédictions CNN
```

Effets attendus :

- sur les séries temporelles : afficher des bandes ou marqueurs de segments ;
- sur les tables de fenêtres : filtrer ou signaler les lignes concernées ;
- sur les features glissantes : permettre une lecture par label manuel ou prédit ;
- sur le résumé fichier : indiquer le nombre de segments annotés et prédits.

Le mode par défaut reste `Aucun filtre segment`.

## 8. Vue Annotateur

### 8.1 Vue existante concernée

Vue actuelle :

```text
static/vehicle_segment_annotator.html
route /annotator
titre actuel : Annotateur Actif de Segments
```

Cette vue reste l'espace d'annotation manuel. Elle ne doit pas être transformée en explorateur généraliste.

Route cible compatible :

```text
/annotator
/?view=annotator
```

### 8.2 Fonctionnement à conserver

La vue doit conserver :

- la file de fichiers prioritaires ;
- le segment courant ;
- les graphes utilisés pour juger le segment ;
- l'enregistrement d'annotation ;
- la gestion des labels ;
- les suggestions du modèle ;
- les annotations enregistrées ;
- les endpoints `/api/annotator/...`, `/api/annotations/...`, `/api/segment-model/...`.

Les actions d'annotation restent prioritaires sur tout ajout d'interface.

### 8.3 Mise en cohérence UI

À ajouter autour de l'existant :

- bandeau `MAS Essais` ;
- entrée active `Annotateur` ;
- lien stable vers `Données d'essais` avec le fichier courant ;
- lien stable vers `Drift` avec le fichier courant ;
- styles communs pour cartes, boutons, états et tables ;
- lecture du paramètre `file` pour ouvrir directement un fichier depuis une autre vue.

### 8.4 Ajout annotations / CNN

L'annotateur possède déjà une logique annotations + modèle. La mise en cohérence doit surtout clarifier les sources :

```text
Label manuel
Prédiction CNN
Confiance CNN
Accord / désaccord
```

Comportements attendus :

- afficher la prédiction CNN du segment courant lorsqu'elle existe ;
- ne jamais remplacer automatiquement le label manuel par le label CNN ;
- permettre de filtrer la file ou la table par label manuel, label CNN ou désaccord ;
- conserver la possibilité de voir tous les segments comme aujourd'hui.

## 9. Vue Drift

### 9.1 Vue existante concernée

Vue actuelle :

```text
static/drift_coherence.html
route /drift-coherence
titre actuel : Exploration signaux par labels
```

Cette vue doit être rattachée au module `Drift`, même si elle contient aujourd'hui une exploration par labels et signaux.

Routes cibles compatibles :

```text
/drift-coherence
/?view=drift
```

### 9.2 Fonctionnement à conserver

La vue doit conserver :

- les filtres existants ;
- la sélection de fichier ;
- la sélection de signal ;
- la sélection de label ;
- la portion de trajectoire filtrée ;
- la série temporelle du signal ;
- la série de boîtes à moustaches ;
- la comparaison par labels ;
- la table de segments filtrés ;
- les endpoints `/api/exploration/...`.

Les analyses de drift déjà exposées par les autres endpoints `/api/drift-coherence/...` peuvent être ajoutées progressivement, mais ne doivent pas bloquer l'unification.

### 9.3 Mise en cohérence UI

À ajouter autour de l'existant :

- bandeau `MAS Essais` ;
- entrée active `Drift` ;
- retour stable vers `Données d'essais` avec le fichier courant ;
- accès stable vers `Annotateur` avec le fichier courant ;
- vocabulaire cohérent avec les autres vues pour fichier, signal, label et segment ;
- styles communs pour tables, cartes, statuts et filtres.

### 9.4 Ajout annotations / CNN

La vue Drift est une bonne candidate pour le filtre transversal, car elle affiche déjà des labels, segments et séries.

Effets attendus :

- filtrer les segments par annotation manuelle ;
- filtrer les segments par prédiction CNN ;
- comparer les distributions par label manuel ou label prédit ;
- afficher les désaccords annotation / CNN dans la table de segments ;
- superposer les plages annotées ou prédites sur les séries temporelles.

Le mode par défaut doit conserver le comportement actuel basé sur les filtres existants.

## 10. Composants communs à factoriser

Les composants suivants doivent devenir communs ou strictement homogènes :

- bandeau global ;
- navigation des quatre vues ;
- panneau de filtres ;
- cartes KPI ;
- table filtrable ;
- bloc de statut ;
- conteneur Plotly ;
- état vide avec message d'action ;
- contrôle `Source segments` ;
- légende annotations / CNN.

Variables CSS recommandées :

```css
:root {
  --bg: #0b0f14;
  --surface: #111722;
  --panel: #151b24;
  --panel-2: #101620;
  --border: #273244;
  --text: #edf2f7;
  --muted: #9aa7b7;
  --accent: #3b82f6;
  --ok: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
}
```

## 11. Routage recommandé

Étape compatible avec l'existant :

```text
/                  -> page actuelle avec bandeau, vue par défaut à décider
/annotator         -> annotateur actuel avec bandeau
/drift-coherence   -> vue drift actuelle avec bandeau
/explorer          -> optionnel, alias vers /?view=explorer
```

Cible progressive :

```text
/?view=validity
/?view=explorer
/?view=annotator
/?view=drift
```

Les anciennes routes doivent rester compatibles pour ne pas casser les liens existants.

## 12. Priorités d'implémentation

### Phase 1 — Enveloppe commune

- Ajouter le bandeau `MAS Essais` aux trois pages existantes.
- Harmoniser les libellés `Validité`, `Données d'essais`, `Annotateur`, `Drift`.
- Conserver les comportements actuels.
- Ajouter la classe ou l'état actif du module courant.

### Phase 2 — Vue Validité

- Ajouter la vue de synthèse qualité.
- Lier chaque ligne vers `Données d'essais`, `Annotateur` et `Drift`.
- Ne pas retirer l'explorateur DXD.

### Phase 3 — Contexte partagé

- Propager `file`, `channels`, `timeRange` et `selectedSegment` par URL.
- Lire ces paramètres dans chaque vue compatible.
- Conserver les filtres déjà présents.

### Phase 4 — Annotations / CNN partout où c'est pertinent

- Ajouter le contrôle `Source segments`.
- Ajouter les surcouches temporelles dans les graphes Plotly compatibles.
- Ajouter les filtres par label manuel, label CNN et désaccord.
- Garder `Aucun filtre segment` comme mode par défaut.

### Phase 5 — Factorisation optionnelle

- Extraire les styles communs.
- Extraire le bandeau commun.
- Fusionner les pages seulement si cela simplifie réellement la maintenance.

## 13. Critères d'acceptation

L'unification est satisfaisante lorsque :

- les vues existantes fonctionnent toujours comme avant en mode par défaut ;
- les quatre vues sont accessibles depuis le même bandeau ;
- l'utilisateur sait toujours dans quelle vue il se trouve ;
- les styles de base sont cohérents ;
- un fichier sélectionné peut être transmis d'une vue à l'autre ;
- les annotations et prédictions CNN peuvent être utilisées dans les vues de visualisation compatibles ;
- les désaccords annotation / CNN sont identifiables lorsque les deux sources existent ;
- les anciennes routes restent utilisables.

## 14. Hors périmètre initial

La première itération ne doit pas inclure :

- refonte complète du backend ;
- changement des calculs métier ;
- remplacement de Plotly ;
- réentraînement automatique du CNN depuis toutes les vues ;
- suppression des pages HTML existantes ;
- modification des formats d'annotations existants ;
- modification des endpoints existants sauf ajout compatible.
