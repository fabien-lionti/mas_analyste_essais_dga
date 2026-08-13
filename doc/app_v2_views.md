# App v2 - Vue et View Model

## Vue statique

Fichiers :

- `app_v2/app/static/index.html`
- `app_v2/app/static/styles.css`
- `app_v2/app/static/app.js`

L'application est une single-page app sans framework. FastAPI sert `index.html`
sur `/`, puis le navigateur charge le CSS et le JS.

## Etat front

Dans `app.js`, l'objet global `state` contient l'etat UI :

- analyses disponibles et analyse active ;
- fichiers et evenements ;
- statut canaux, canaux recurrents, structure validee ;
- etat des taches longues ;
- fichiers/canaux d'exploration ;
- annotations, labels, catalogue ;
- definitions, predictions et contexte d'analyse dynamique.

`api(path, options)` est le wrapper unique pour les appels `fetch`.

## Onglets principaux

### Creer une analyse

Vue : `#view-overview`

Sous-onglets :

- `Fichiers DXD`
- `Canaux DXD`
- `Indicateurs dynamiques`
- `Sampling JSON`

Responsabilite UI :

- creer l'analyse ;
- identifier les DXD ;
- scanner les canaux ;
- choisir les canaux valides ;
- choisir les indicateurs dynamiques disponibles ;
- configurer frequence/methode/dossier ;
- lancer l'export JSON avec barre de progression.

Fonctions JS principales :

- `showWorkflowStep`
- `createAnalysis`
- `loadChannels`
- `renderChannels`
- `renderDynamicIndicators`
- `saveDynamicIndicators`
- `finalizeAnalysis`
- `pollChannelAnalysis`
- `pollResampling`

### Choix analyse

Vue : `#view-choice`

Responsabilite UI :

- lister les analyses existantes ;
- choisir l'analyse active ;
- afficher un resume ;
- supprimer une analyse.

Fonctions JS principales :

- `loadAnalyses`
- `loadAnalysis`
- `renderAnalysisChoice`
- `deleteAnalysisById`

### Exploration

Vue : `#view-exploration`

Sous-onglets :

- `Vision temporelle`
- `Vision parametrique`

Responsabilite UI :

- filtrer les fichiers par dates et annotations ;
- selectionner fichier et canaux ;
- afficher series temporelles ;
- afficher trajectoire GPS ;
- afficher nuage de points parametrique fichier courant ou fichiers filtres.

Fonctions JS principales :

- `loadExplorationFiles`
- `loadExplorationDateRange`
- `loadExplorationChannels`
- `refreshExplorationPlots`
- `loadParametricFiles`
- `loadParametricChannels`
- `refreshParametricPlot`

### Annotations

Vue : `#view-annotations`

Sous-onglets :

- `Annoter`
- `Catalogue des annotations`

Responsabilite UI :

- choisir fichier et canaux ;
- selectionner un segment dans le graphe ;
- choisir un label administre ;
- creer/modifier/supprimer une annotation ;
- administrer labels ;
- consulter et filtrer le catalogue.

Fonctions JS principales :

- `loadAnnotationFiles`
- `loadAnnotationChannels`
- `loadAnnotationLabels`
- `refreshAnnotationPlots`
- `saveAnnotation`
- `renderAnnotationsTable`
- `renderAnnotationCatalog`
- `createAnnotationLabel`
- `renameAnnotationLabel`
- `deleteSelectedAnnotationLabel`

### Analyse dynamique

Vue : `#view-dynamic-analysis`

Sous-onglets :

- `Analyse dynamique`
- `Choix analyse dynamique`
- `Generation / validation`

Comportement actuel :

- le formulaire cree une analyse dynamique ;
- si le nom existe deja, l'API ecrase l'ancienne definition ;
- les canaux et labels pertinents sont selectionnes dans des tableaux ;
- le sous-onglet choix permet de selectionner ou supprimer une analyse dynamique ;
- la generation se fait annotation par annotation ;
- une prediction peut etre sauvegardee puis corrigee.

Fonctions JS principales :

- `loadDynamicAnalysis`
- `saveDynamicPrompt`
- `renderDynamicChannelOptions`
- `renderDynamicLabelOptions`
- `renderDynamicPromptOptions`
- `openDynamicGeneration`
- `runDynamicAnalysis`
- `deleteSelectedDynamicAnalysis`
- `saveDynamicAnalysisVersion`

## Composants UI recurrents

### Tables

`renderTable(containerId, columns, rows, emptyText)` produit les tableaux HTML.
Il est utilise pour les listes de canaux, fichiers, annotations, analyses
dynamiques et catalogues.

### Sous-onglets

Les sous-onglets sont geres par classes CSS et attributs `data-*` :

- `data-workflow-step`
- `data-exploration-step`
- `data-annotation-step`
- `data-dynamic-step`

Chaque fonction `show...Step` active le bon bloc et desactive les autres.

### Graphiques

Plotly est utilise pour :

- series temporelles ;
- signal annotable ;
- trajectoire GPS ;
- vision parametrique.

Les donnees viennent des endpoints exploration, pas directement des fichiers
cote navigateur.

## Limites de la vue actuelle

- `app.js` porte beaucoup de responsabilites : etat, controle UI, rendu et API.
- Il n'y a pas encore de separation en modules front.
- Les formulaires sont relies aux ids DOM, donc les renommages HTML doivent etre
  synchronises avec `app.js` et les tests UI.
- Les raccourcis de selection de canaux dependent du comportement natif des
  listes/selects et de handlers front dedies selon les vues.
