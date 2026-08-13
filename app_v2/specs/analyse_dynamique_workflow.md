# Specification - Analyse dynamique

## Objectif du document

Ce document sert de base editable pour guider l'evolution de l'onglet
`Analyse dynamique` dans `app_v2`.

Il doit clarifier :

- le modele de donnees attendu ;
- le workflow utilisateur ;
- les sous-onglets a afficher ;
- les champs visibles ou caches ;
- les comportements attendus ;
- les points encore a arbitrer.

## Contexte produit

Une analyse dynamique est rattachee a une analyse existante.

Une analyse dynamique decrit une methode d'interpretation de segments annotees :

- un prompt systeme ;
- une liste de canaux a utiliser ;
- une liste d'indicateurs calcules ou attendus ;
- une liste de labels pertinents ;
- des predictions LLM multimodales produites pour les annotations de cette
  selection ;
- des corrections humaines possibles sur chaque prediction.

L'objectif n'est pas de faire un chat generaliste avec les signaux, mais de
produire des interpretations tracees, comparables et corrigibles.

## Modele cible

### Entites

```text
analysis
  └─ dynamic_analyses
      └─ dynamic_annotation_predictions
          └─ dynamic_prediction_corrections
```

### `dynamic_analyses`

Une ligne represente une configuration d'analyse dynamique rattachee a une
analyse globale.

Champs principaux :

- `dynamic_analysis_id`
- `analysis_id`
- `name`
- `system_prompt`
- `selected_channels_json`
- `selected_labels_json`
- `indicators_json`
- `created_at`
- `updated_at`

### `dynamic_annotation_predictions`

Une ligne represente une prediction LLM pour une annotation donnee et une
analyse dynamique donnee.

Champs principaux :

- `prediction_id`
- `dynamic_analysis_id`
- `annotation_id`
- `provider`
- `model`
- `status`
- `input_context_json`
- `input_artifact_path`
- `analysis_text`
- `analysis_note`
- `summary_text`
- `error_message`
- `created_at`
- `updated_at`

### `dynamic_prediction_corrections`

Une ligne represente une correction humaine d'une prediction.

Champs principaux :

- `correction_id`
- `prediction_id`
- `corrected_analysis_text`
- `corrected_analysis_note`
- `corrected_summary_text`
- `note`
- `validated_for_dataset`
- `created_at`

## Workflow UI cible

L'onglet principal `Analyse dynamique` doit contenir trois sous-onglets.

```text
Analyse dynamique -> Choix analyse dynamique -> Generation / validation
```

## Sous-onglet 1 - Analyse dynamique

Objectif : creer une analyse dynamique et definir les elements qui seront
utilises par la generation LLM.

Si une analyse dynamique porte deja le meme nom pour l'analyse active, la
creation ecrase l'ancienne definition par mise a jour applicative.

Champs visibles :

- nom de l'analyse dynamique ;
- description courte ;
- prompt systeme ;
- tableau des canaux resamples avec cases a cocher ;
- tableau des labels disponibles avec cases a cocher ;
- tableau des indicateurs disponibles avec cases a cocher, si l'UI les expose.

Actions :

- `Creer l'analyse dynamique`

Comportement attendu :

- creer l'analyse dynamique sauvegarde la configuration dans `dynamic_analyses` ;
- apres creation, l'analyse dynamique apparait dans la liste du sous-onglet
  `Choix analyse dynamique` ;
- ce sous-onglet ne doit pas lancer directement les predictions ;
- le lancement des predictions se fait depuis `Generation / validation`.

Champs a ne pas afficher ici :

- provider ;
- modele ;
- resultats.

Notes :

- le provider et le modele seront ajoutes plus tard quand l'appel LLM reel sera
  branche.

## Sous-onglet 2 - Choix analyse dynamique

Objectif : choisir une analyse dynamique existante rattachee a l'analyse active.

Ce sous-onglet ne sert pas a modifier une analyse dynamique. Toute creation ou
remplacement par nom se fait uniquement dans `Analyse dynamique`.

Contenu attendu :

- liste des analyses dynamiques disponibles ;
- resume de l'analyse dynamique selectionnee :
  - nom ;
  - labels selectionnes ;
  - canaux ;
  - indicateurs ;
  - nombre de predictions existantes.

Actions possibles :

- selectionner une analyse dynamique ;
- supprimer une analyse dynamique ;
- ouvrir la vue de generation trajectoire par trajectoire.

Comportement attendu :

- ce sous-onglet ne lance pas directement le LLM ;
- le choix determine quelle analyse dynamique sera utilisee dans le sous-onglet
  suivant ;
- apres selection, le sous-onglet de generation affiche les trajectoires et
  segments correspondant aux labels selectionnes dans l'analyse dynamique.

Decision a confirmer :

- faut-il afficher uniquement les analyses dynamiques ayant deja des
  predictions ?
- faut-il afficher un statut indiquant si les predictions sont a jour ?

## Sous-onglet 3 - Generation / validation

Objectif : generer l'analyse dynamique trajectoire par trajectoire, label par
label, a partir de l'analyse dynamique selectionnee.

C'est dans ce sous-onglet que le LLM travaille.

Contenu attendu :

- liste ou navigation des trajectoires/annotations correspondant aux labels
  selectionnes ;
- label courant ;
- annotation courante ;
- canaux selectionnes par l'analyse dynamique ;
- indicateurs calcules pour le segment courant ;
- trajectoire GPS avec le segment courant mis en evidence ;
- graphes des canaux selectionnes sur la fenetre du segment ;
- contexte utilise pour la prediction ;
- bouton de lancement de la prediction LLM ;
- analyse LLM produite ;
- synthese affichee ;
- correction humaine editable ;
- validation dataset.

Actions :

- choisir une trajectoire ou annotation ;
- afficher le segment courant ;
- lancer la prediction LLM pour le segment courant ;
- relancer la prediction si besoin ;
- sauvegarder une correction ;
- marquer comme valide pour dataset.

Comportement attendu :

- la generation se fait au niveau d'une annotation/trajectoire courante, pas en
  masse sans controle utilisateur ;
- le bouton de prediction appelle le LLM multimodal, ou un dry-run tant que le
  provider reel n'est pas branche ;
- la prediction est sauvegardee dans `dynamic_annotation_predictions` ;
- la correction humaine est sauvegardee dans `dynamic_prediction_corrections` ;
- l'utilisateur doit toujours voir les donnees ayant servi a produire la
  prediction : canaux, indicateurs, trajectoire et segment mis en evidence.

## Sortie LLM attendue en V1

En V1, le LLM fait une analyse du segment courant, puis l'application affiche une
synthese.

Il n'y a pas de format JSON detaille a demander au LLM dans un premier temps. En
revanche, la reponse peut etre structuree avec des balises simples afin que
l'application puisse separer les parties affichees.

Format texte attendu :

```text
<analyse>
Analyse affichable du segment courant.
Elle explique ce que le modele observe dans les signaux, les indicateurs, la
trajectoire et la zone segmentee.
</analyse>

<note_analyse>
Note courte expliquant les points importants retenus pour construire la synthese.
Cette note doit rester factuelle et affichable. Elle ne doit pas contenir de
chaine de pensee interne brute.
</note_analyse>

<synthese>
Synthese courte destinee a l'UI.
</synthese>
```

La partie `<analyse>` peut etre longue et structuree en paragraphes.

La partie `<note_analyse>` sert a expliciter les elements visibles qui ont pese
dans l'analyse, sans demander au modele d'exposer sa chaine de pensee interne.

La partie `<synthese>` est celle qui est affichee en premier dans l'UI.

Le LLM ne doit pas fournir de niveau de confiance. Il fait une analyse, puis une
synthese, et c'est tout. L'eventuelle validation qualite vient ensuite de
l'analyste humain.

## Multimodal

- generation d'un artefact visuel par annotation ;
- stockage du chemin dans `input_artifact_path` ;
- appel provider LLM multimodal depuis le sous-onglet `Generation / validation` ;
- extraction des balises `<analyse>`, `<note_analyse>` et `<synthese>` ;
- sauvegarde de l'analyse texte, de la note d'analyse et de la synthese.

### Interface provider Gemini

L'ancienne app appelle Gemini dans `src/mas_essais/analysis/retournement.py`.
Le principe a reprendre est :

- lire la cle API depuis `GEMINI_API_KEY` ;
- lire le modele depuis une variable d'environnement, avec une valeur par defaut ;
- encoder l'artefact visuel en base64 ;
- envoyer l'image via `inline_data` avec son `mime_type` ;
- envoyer le prompt dans une partie texte separee ;
- appeler l'endpoint Gemini `generateContent` ;
- lire la reponse dans `candidates[0].content.parts[*].text`.

Pour l'analyse dynamique, la reponse ne doit pas etre forcee en JSON Gemini dans
un premier temps. Le prompt doit demander une reponse texte balisee :

```text
<analyse>...</analyse>
<note_analyse>...</note_analyse>
<synthese>...</synthese>
```

## Points ouverts

### Indicateurs

A definir :

- liste des indicateurs disponibles ;
- indicateurs calcules automatiquement ;
- indicateurs choisis par l'utilisateur ;
- affichage ou non des indicateurs dans l'UI.

Exemples possibles :

- amplitude ;
- pic absolu ;
- instant du pic ;
- delta debut/fin ;
- pente ;
- moyenne ;
- ecart-type.

### Labels inclus

A confirmer :

- faut-il imposer au moins un label selectionne ?
- faut-il permettre des groupes de labels plus tard ?

Hypothese actuelle :

- une analyse dynamique cible une liste de labels ;
- les predictions sont generees sur les annotations correspondant a ces labels.

### Correction humaine

A confirmer :

- une prediction peut-elle avoir plusieurs corrections ?
- faut-il afficher uniquement la derniere correction ?
- faut-il comparer prediction initiale et correction ?

Hypothese actuelle :

- plusieurs corrections sont autorisees ;
- elles servent a construire un historique et un futur dataset.

## Criteres d'acceptation

- l'onglet `Analyse dynamique` contient trois sous-onglets ;
- le sous-onglet `Analyse dynamique` permet de creer une analyse dynamique ;
- si le nom existe deja, la creation ecrase la definition existante ;
- le sous-onglet `Choix analyse dynamique` permet de selectionner une analyse
  dynamique existante ;
- le sous-onglet `Choix analyse dynamique` ne permet ni creation ni modification
  d'une analyse dynamique ;
- le sous-onglet `Generation / validation` permet de parcourir les trajectoires
  et annotations ciblees ;
- le sous-onglet `Generation / validation` affiche les indicateurs, les canaux
  selectionnes et la trajectoire avec le segment mis en evidence ;
- le lancement de la prediction LLM se fait depuis `Generation / validation`,
  pour l'annotation courante ;
- la prediction LLM produit une analyse texte et une synthese ;
- une analyse dynamique est toujours rattachee a une analyse globale ;
- une prediction est toujours rattachee a une annotation ;
- une correction est toujours rattachee a une prediction ;
- les tests API couvrent creation analyse dynamique, prediction et correction ;
- l'UI reste coherente avec la charte claire de `app_v2`.

## Decisions utilisateur a renseigner

Editable :

```text
Nom final des sous-onglets :

Champs exacts du sous-onglet Analyse dynamique :

Contenu exact du sous-onglet Choix analyse dynamique :

Contenu exact du sous-onglet Generation / validation :

Liste des indicateurs a supporter :

Regles de selection des labels :

Forme attendue de l'analyse et de la synthese LLM :

Regles de validation dataset :
```
