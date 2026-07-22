# Spécification — Page d'exploration par labels CNN sans entraînement

## 1. Objectif

L'objectif est de recentrer la page applicative sur l'exploration des signaux et des distributions glissantes, en supprimant tout ce qui concerne :

- l'entraînement du modèle CNN depuis l'interface ;
- les contrôles de lancement d'analyse de drift depuis la page ;
- la présentation orientée détection automatique d'anomalie ou de drift.

La logique à conserver est la suivante :

```text
labels de trajectoire produits ou utilisés par le CNN
    -> filtre par type de label / trajectoire
    -> filtre par capteur ou canal
    -> visualisation temporelle des signaux
    -> visualisation des distributions glissantes
```

La page doit donc devenir une interface de consultation et de comparaison, pas une interface d'entraînement.

---

## 2. Périmètre fonctionnel conservé

### 2.1 Labels CNN

Le CNN reste utile uniquement comme source de labels de segments ou comme source de suggestions déjà calculées.

La page doit permettre de filtrer les données par type de label, par exemple :

```text
ligne_droite
virage_gauche
virage_droite
slalom
freinage
acceleration
mixed_or_unknown
```

Les noms exacts doivent provenir des labels disponibles dans les annotations ou prédictions existantes, sans liste codée en dur lorsque l'API peut les fournir.

### 2.2 Signaux visualisables

Les signaux principaux à préserver dans l'interface sont :

```text
vehicle.vx
vehicle.vy
vehicle.ax
vehicle.ay ou vehicle.axy
steer_s1
steer_s2
```

Si le projet expose `vehicle.ay` mais pas `vehicle.axy`, l'interface doit afficher le nom réellement disponible. Si `vehicle.axy` correspond à une norme d'accélération ou à un canal dérivé, la spécification d'implémentation doit préciser sa formule avant ajout.

### 2.3 Filtres attendus

La page doit proposer au minimum :

- un filtre `label` : tous les labels ou un label précis ;
- un filtre `trajectoire` : type de trajectoire lorsque cette information est disponible ;
- un filtre `capteur / signal` : `vx`, `vy`, `ax`, `ay/axy`, `steer_s1`, `steer_s2` ;
- un filtre `fichier` : tous les fichiers filtrés ou un fichier précis ;
- un filtre temporel optionnel : intervalle de temps ou fenêtre glissante.

Le filtre par label doit être appliqué avant les agrégations, afin que les distributions glissantes représentent uniquement les segments appartenant au type de trajectoire sélectionné.

---

## 3. Éléments à retirer de la page

### 3.1 Entraînement CNN

L'interface ne doit plus afficher :

- bouton de lancement d'entraînement CNN ;
- paramètres d'entraînement CNN : fenêtre, stride, epochs, métriques train ;
- statut ou polling de progression d'entraînement CNN ;
- panneaux de résumé orientés entraînement du modèle.

Les routes backend peuvent rester disponibles dans un premier temps si d'autres pages les utilisent, mais elles ne doivent plus être appelées par cette page.

### 3.2 Détection de drift

La page ne doit plus présenter la fonctionnalité comme une détection de drift à entraîner ou déclencher.

À retirer ou renommer :

- bouton `Nouvelle analyse` ;
- panneau `trainPanel` ou équivalent ;
- endpoint appelé depuis l'UI `POST /api/drift-coherence/train` ;
- polling `GET /api/drift-coherence/train/progress` ;
- textes `drift`, `anomaly`, `score d'anomalie`, lorsqu'ils suggèrent une décision automatique.

Les métriques historiques peuvent rester affichées comme indicateurs descriptifs, par exemple `erreur`, `résidu`, `q95`, `distribution glissante`, mais sans décision `drift détecté`.

---

## 4. Interface cible

### 4.1 Structure recommandée

La page doit être organisée autour d'une barre de filtres globale et de plusieurs panels de visualisation synchronisés :

```text
Barre de filtres
    label CNN / trajectoire / capteur / fichier / phase ou période

Panel trajectoire filtrée
    portion GPS ou trajectoire reconstruite correspondant au label sélectionné

Panel série temporelle signal
    signal sélectionné sur les portions retenues par le filtre

Panel boîtes à moustaches temporelles
    distribution du signal par tranche horaire et/ou journée

Panel contexte
    fichiers, labels, nombre de points, couverture temporelle, métriques descriptives
```

Tous les panels doivent utiliser les mêmes filtres courants : label, source du label, signal, fichier et période.

### 4.2 Sélecteur de signaux

Le sélecteur doit proposer les libellés lisibles suivants :

| Libellé UI | Canal canonique |
| --- | --- |
| `vx` | `vehicle.vx` |
| `vy` | `vehicle.vy` |
| `ax` | `vehicle.ax` |
| `ay` ou `axy` | `vehicle.ay` ou canal dérivé confirmé |
| `steer S1` | `steer_s1` ou `WheelSteer_S1 (_)` selon le schéma disponible |
| `steer S2` | `steer_s2` ou `WheelSteer_S2 (_)` selon le schéma disponible |

La sélection d'un signal doit mettre à jour :

- la série temporelle ;
- les métriques par fichier ;
- la distribution glissante ;
- les éventuelles tables de quantiles.

### 4.3 Distribution glissante

La distribution glissante doit être calculée sur les segments filtrés.

Pour chaque fenêtre, les métriques recommandées sont :

```text
n_points
mean
std
min
q05
q25
q50
q75
q95
max
```

La visualisation minimale attendue :

- courbe `q50` ;
- bande `q25`-`q75` ;
- bande ou courbe `q05`-`q95` ;
- histogramme global du signal filtré, si le volume de données le permet.

### 4.4 Comparaison par type de trajectoire

Lorsqu'aucun label précis n'est sélectionné, la page peut afficher une comparaison par label :

```text
label -> distribution du signal sélectionné
```

Cette vue doit permettre d'identifier les différences de distribution entre types de trajectoires sans conclure automatiquement à une anomalie.

### 4.5 Panels UI attendus

#### 4.5.1 Panel trajectoire filtrée

Ce panel doit afficher la portion de trajectoire correspondant au label choisi.

Entrées :

```text
label
label_source = annotated | cnn_predicted | both
json_name
start_sec / end_sec
```

Affichage attendu :

- trace GPS ou trajectoire reconstruite ;
- surbrillance des segments correspondant au label filtré ;
- couleur ou style différent pour `annotated` et `cnn_predicted` si les deux sources sont affichées ;
- info-bulle indiquant fichier, label, source, début, fin et durée du segment ;
- option d'afficher le contexte avant/après segment, par exemple +/- 5 s ou +/- 30 s.

Ce panel répond à la question :

```text
où se situe physiquement la portion de trajectoire que je suis en train d'analyser ?
```

#### 4.5.2 Panel série temporelle du signal

Ce panel doit afficher le signal sélectionné sur les segments filtrés.

Affichage attendu :

- courbe du signal sélectionné ;
- bandes verticales ou zones colorées correspondant aux segments filtrés ;
- possibilité de superposer plusieurs signaux compatibles si utile, par exemple `steer_s1` et `steer_s2` ;
- axe temporel synchronisé avec le panel trajectoire lorsque l'utilisateur sélectionne un segment.

Ce panel répond à la question :

```text
comment évolue le capteur choisi pendant les portions annotées ou prédites ?
```

#### 4.5.3 Panel boîtes à moustaches temporelles

Ce panel doit afficher une série temporelle de boîtes à moustaches filtrées par label.

Agrégations minimales :

```text
par heure
par journée
par couple journée + heure
```

Affichage attendu :

- une boîte par tranche temporelle ;
- médiane, quartiles et moustaches calculés uniquement sur les segments du label sélectionné ;
- nombre de points ou nombre de segments visible au survol ;
- possibilité de comparer `annotated` vs `cnn_predicted` si les deux sources sont disponibles ;
- option de masquer les tranches dont `n_points` est insuffisant.

Ce panel répond à la question :

```text
la distribution du capteur sélectionné évolue-t-elle au fil des heures ou des journées pour ce type de trajectoire ?
```

#### 4.5.4 Panel résumé / couverture

Un panel compact de contexte est recommandé pour éviter d'interpréter une distribution sans connaître son support.

Indicateurs utiles :

- nombre de fichiers retenus ;
- nombre de segments retenus ;
- durée totale couverte ;
- nombre de points utilisés ;
- répartition `annotated` / `cnn_predicted` ;
- liste des fichiers les plus représentés ;
- canaux absents ou partiellement disponibles.

Ce panel doit rester descriptif et ne doit pas produire de conclusion automatique.

#### 4.5.5 Panel comparaison par labels

En complément, un panel optionnel peut comparer plusieurs labels pour un même signal.

Exemples :

```text
vehicle.vx par label
steer_s1 par label
vehicle.ax par label
```

Affichage possible :

- boxplots par label ;
- histogrammes superposés ;
- tableau de quantiles par label.

Ce panel est utile lorsque l'utilisateur n'a pas encore choisi un label précis ou veut vérifier que les labels CNN séparent bien des comportements différents.

### 4.6 Interactions entre panels

Les panels doivent être coordonnés :

- un clic sur une boîte temporelle filtre ou met en évidence les segments de cette tranche dans la trajectoire ;
- un clic sur un segment de trajectoire charge la série temporelle correspondante ;
- un changement de signal met à jour les séries, boxplots et métriques ;
- un changement de label met à jour tous les panels ;
- un changement de source de label permet de comparer annotations validées et prédictions CNN.

Le comportement par défaut doit être :

```text
label = tous
label_source = annotated si disponible, sinon cnn_predicted
signal = vehicle.vx si disponible
time_grouping = day_hour
```

---

## 5. Données et API

### 5.1 APIs existantes réutilisables

Les endpoints existants orientés lecture peuvent être conservés si leurs réponses répondent au besoin :

```text
GET /api/drift-coherence/runs
GET /api/drift-coherence/{run_id}/summary
GET /api/drift-coherence/{run_id}/batch-metrics
GET /api/drift-coherence/{run_id}/metrics-by-file
GET /api/drift-coherence/{run_id}/metrics-by-timebin
GET /api/drift-coherence/{run_id}/prediction-files
GET /api/drift-coherence/{run_id}/prediction-series
GET /api/drift-coherence/{run_id}/annotation-label-metrics
GET /api/annotations/segments/labels
```

La page ne doit plus appeler les endpoints de lancement d'entraînement.

### 5.2 API optionnelle à ajouter

Pour clarifier le nouveau besoin, une route dédiée peut être ajoutée :

```text
GET /api/exploration/signals/distribution
```

Paramètres :

```text
label
trajectory_type
signal
json_name
window_sec
stride_sec
start_sec
end_sec
limit
```

Réponse :

```json
{
  "items": [
    {
      "json_name": "example.json",
      "label": "ligne_droite",
      "signal": "vehicle.vx",
      "window_start_sec": 10.0,
      "window_end_sec": 15.0,
      "n_points": 250,
      "mean": 12.4,
      "std": 0.8,
      "q05": 11.1,
      "q25": 11.9,
      "q50": 12.3,
      "q75": 12.9,
      "q95": 13.8
    }
  ],
  "filters": {
    "label": "ligne_droite",
    "signal": "vehicle.vx"
  }
}
```

Cette API doit rester descriptive : elle retourne des statistiques, pas une décision de drift.

### 5.3 Agrégations temporelles pour boîtes à moustaches

L'API de distribution doit aussi pouvoir retourner une structure adaptée à une visualisation de type boîte à moustaches au cours du temps.

Cette vue sert à comparer la distribution d'un signal filtré par label, par tranche horaire et par journée, sans conclure automatiquement à une dérive.

Paramètres complémentaires recommandés :

```text
time_grouping = hour | day | day_hour
label_source = annotated | cnn_predicted | both
```

Réponse attendue pour une boîte à moustaches :

```json
{
  "items": [
    {
      "date": "2025-04-17",
      "hour": 14,
      "time_bucket": "2025-04-17T14:00:00",
      "label": "ligne_droite",
      "label_source": "annotated",
      "signal": "vehicle.vx",
      "n_points": 4200,
      "min": 10.2,
      "q05": 11.1,
      "q25": 11.9,
      "q50": 12.3,
      "q75": 12.9,
      "q95": 13.8,
      "max": 14.6
    }
  ],
  "filters": {
    "label": "ligne_droite",
    "label_source": "annotated",
    "signal": "vehicle.vx",
    "time_grouping": "day_hour"
  }
}
```

Règles :

- le filtre par label doit être appliqué avant le calcul des quantiles ;
- les labels annotés et les labels prédits par CNN doivent pouvoir être distingués ;
- si `label_source = both`, la réponse doit contenir une colonne `label_source` permettant de séparer les séries dans le graphe ;
- les tranches sans assez de points doivent être exclues ou marquées avec `n_points` insuffisant ;
- les quantiles retournés doivent suffire à construire une boîte à moustaches sans renvoyer toutes les valeurs brutes.

---

## 6. Contraintes d'implémentation

### 6.1 Compatibilité

La modification doit conserver la lecture des résultats déjà présents sur disque.

Les routes d'entraînement peuvent être gardées côté backend pour compatibilité temporaire, mais la page cible ne doit pas les exposer.

### 6.2 Nommage

Le vocabulaire UI doit privilégier :

```text
exploration
signal
distribution
fenêtre glissante
label
trajectoire
capteur
résidu descriptif
```

Le vocabulaire à éviter dans cette page :

```text
entraînement
train
détection de drift
anomalie détectée
score anomalie
```

### 6.3 Source des labels

La source prioritaire des labels est :

1. annotations validées par l'utilisateur ;
2. suggestions CNN déjà calculées, si elles sont explicitement disponibles ;
3. labels agrégés dans les sorties de runs existants.

L'interface doit distinguer visuellement les labels validés et les suggestions CNN si les deux sources sont affichées simultanément.

---

## 7. Critères d'acceptation

La modification est acceptée si :

1. La page ne contient plus de bouton ni panneau permettant d'entraîner un CNN ou une analyse de drift.
2. Aucun appel réseau de la page ne cible `POST /api/segment-model/train` ou `POST /api/drift-coherence/train`.
3. L'utilisateur peut choisir un label CNN ou annotation et filtrer les vues avec ce label.
4. L'utilisateur peut choisir au moins les signaux `vx`, `vy`, `ax`, `ay/axy`, `steer_s1`, `steer_s2` lorsque les données sont disponibles.
5. Les séries temporelles et distributions glissantes se mettent à jour après changement de label, capteur ou fichier.
6. Les métriques affichées sont descriptives et ne concluent pas automatiquement à un drift ou à une anomalie.
7. L'interface reste utilisable lorsqu'aucun label n'est sélectionné, avec une vue globale.
8. L'interface gère proprement les canaux absents en désactivant ou masquant les options indisponibles.
9. Un panel affiche la portion de trajectoire filtrée par annotation ou prédiction CNN.
10. Un panel affiche une série temporelle de boîtes à moustaches par tranche horaire et/ou journée.
11. Un panel de contexte indique au minimum le nombre de fichiers, segments, points et la couverture temporelle utilisés par les visualisations.
12. Les interactions entre trajectoire, série temporelle et boîtes à moustaches restent synchronisées avec les filtres actifs.

---

## 8. Étapes de migration proposées

1. Supprimer ou masquer les panneaux d'entraînement dans les pages concernées.
2. Retirer les handlers JavaScript qui appellent les endpoints d'entraînement.
3. Renommer la page ou les titres UI pour passer de `Drift TCN` à `Exploration signaux par labels`.
4. Conserver le chargement des runs et métriques existantes uniquement pour la lecture.
5. Ajouter le sélecteur de signaux centré sur `vx`, `vy`, `ax`, `ay/axy`, `steer_s1`, `steer_s2`.
6. Connecter le filtre label aux séries, aux métriques et aux distributions glissantes.
7. Ajouter une route dédiée de distribution glissante si les endpoints existants ne suffisent pas.
8. Vérifier que la page ne contient plus de wording ou workflow d'entraînement.

---

## 9. Hors périmètre

Cette modification ne couvre pas :

- le réentraînement du CNN ;
- la calibration de seuils d'anomalie ;
- la décision automatique de drift ;
- la suppression définitive des scripts d'entraînement du dépôt.

Ces éléments peuvent être conservés dans le projet pour des usages offline, mais ne doivent plus être exposés dans cette page applicative.
