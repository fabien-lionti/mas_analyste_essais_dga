# Spécification — Catégorisation des manœuvres et clustering hiérarchique des fenêtres d’essais véhicule

## 1. Objectif

L’objectif est de structurer l’analyse de signaux d’essais véhicule par fenêtres temporelles afin de permettre une comparaison robuste des indicateurs de qualité, des résidus physiques et des comportements dynamiques.

La logique retenue est hiérarchique :

```text
fenêtres temporelles
→ catégorisation métier de la manœuvre
→ clustering de contexte dynamique / excitation
→ clustering de signatures résiduelles
→ visualisation temporelle, spatiale et par fichier
```

Le premier niveau, `maneuver_family`, n’est pas un clustering appris. Il s’agit d’une catégorisation heuristique fondée sur des règles métier simples et interprétables.

Les niveaux suivants peuvent utiliser du clustering non supervisé, par exemple DBSCAN ou HDBSCAN.

---

## 2. Principe général

Chaque fenêtre temporelle doit être décrite par trois familles d’informations :

1. **Contexte dynamique**

   * vitesse ;
   * accélération longitudinale ;
   * accélération latérale ;
   * yaw rate ;
   * angle volant ;
   * excitation longitudinale et latérale.

2. **Géométrie / localisation GPS**

   * longueur de trajectoire ;
   * déplacement net ;
   * variation de cap ;
   * courbure ;
   * tortuosité ;
   * localisation moyenne de la fenêtre.

3. **Qualité / résidus**

   * résidus cinématiques ;
   * résidus accélération ;
   * résidus GPS ;
   * bruit ;
   * dérive ;
   * biais ;
   * incohérences entre capteurs.

La catégorisation de manœuvre doit servir à éviter de comparer des fenêtres physiquement incomparables.

Par exemple, un résidu latéral élevé ne s’interprète pas de la même manière en virage dynamique, à basse vitesse ou en ligne droite stabilisée.

---

## 3. Niveaux de structuration

La structure recommandée est la suivante :

```text
Niveau 1 — maneuver_family
           catégorisation métier non apprise

Niveau 2 — context_cluster_id
           clustering appris du contexte dynamique / niveau d’excitation

Niveau 3 — residual_cluster_id
           clustering appris des signatures de résidus à contexte comparable

Niveau 4 — analyse temporelle / spatiale
           évolution par date, fichier, portion GPS, campagne
```

Le premier niveau doit rester simple, explicite et contrôlable.

---

## 4. Catégories `maneuver_family`

Les catégories recommandées sont :

```text
standstill
low_speed_maneuver
straight_constant_speed
straight_acceleration
straight_braking
cornering_left
cornering_right
combined_longitudinal_lateral
mixed_or_unknown
```

---

## 5. Description des catégories

### 5.1 `standstill`

Fenêtre où le véhicule est à l’arrêt ou quasi-arrêt.

Critères typiques :

```text
vitesse très faible
zero_speed_ratio élevé
déplacement GPS faible
```

Exemples :

```text
arrêt avant départ
attente
fin d’essai
immobilisation
```

Cette catégorie doit être séparée des autres car les dérivées, les ratios cinématiques et le GPS peuvent être instables à très basse vitesse.

---

### 5.2 `low_speed_maneuver`

Fenêtre de manœuvre à basse vitesse avec braquage ou rotation non négligeable.

Critères typiques :

```text
vitesse faible
braquage significatif
yaw rate significatif
déplacement GPS court
```

Exemples :

```text
parking
demi-tour lent
mise en position
manœuvre de départ ou d’arrivée
```

Cette catégorie ne doit pas être mélangée avec les virages dynamiques, car les relations du type :

```math
a_y \approx v_x \dot{\psi}
```

peuvent devenir fragiles à faible vitesse.

---

### 5.3 `straight_constant_speed`

Fenêtre de ligne droite ou quasi-ligne droite avec vitesse relativement stable.

Critères typiques :

```text
accélération latérale faible
yaw rate faible
braquage faible
accélération longitudinale faible
vitesse non nulle
```

Cette catégorie est utile pour analyser les cohérences longitudinales :

```math
r_{\text{long}} = a_x - \frac{d v_x}{dt}
```

ou la cohérence entre GPS, vitesse et odométrie.

---

### 5.4 `straight_acceleration`

Fenêtre d’accélération principalement longitudinale.

Critères typiques :

```text
accélération longitudinale positive
accélération latérale faible
yaw rate faible
braquage faible
vitesse croissante
```

Exemples :

```text
relance
départ lancé
accélération en ligne droite
```

Cette catégorie est utile pour identifier des retards, biais ou incohérences entre accélération longitudinale, vitesse, GPS et odométrie.

---

### 5.5 `straight_braking`

Fenêtre de freinage principalement longitudinal.

Critères typiques :

```text
accélération longitudinale négative
accélération latérale faible
yaw rate faible
braquage faible
vitesse décroissante
```

Exemples :

```text
freinage droit
décélération avant virage
ralentissement
```

Cette catégorie doit être séparée de l’accélération, car les signatures de résidus peuvent changer en présence de transfert de masse, ABS, filtrage ou saturation.

---

### 5.6 `cornering_left`

Fenêtre de virage gauche principalement latéral.

Critères typiques :

```text
accélération latérale significative
yaw rate significatif
braquage significatif
accélération longitudinale modérée
signe du yaw rate ou de la courbure compatible avec un virage gauche
```

Cette catégorie est utile pour analyser les effets latéraux, les asymétries véhicule et les biais de capteurs.

---

### 5.7 `cornering_right`

Fenêtre de virage droit principalement latéral.

Critères typiques :

```text
accélération latérale significative
yaw rate significatif
braquage significatif
accélération longitudinale modérée
signe du yaw rate ou de la courbure compatible avec un virage droit
```

Il est préférable de séparer gauche et droite afin de détecter :

```text
offset volant
biais yaw rate
asymétrie gauche/droite
capteur mal centré
différence de comportement véhicule
```

---

### 5.8 `combined_longitudinal_lateral`

Fenêtre combinant une sollicitation longitudinale et latérale.

Critères typiques :

```text
accélération latérale significative
yaw rate significatif
braquage significatif
accélération longitudinale significative
```

Exemples :

```text
freinage en entrée de virage
accélération en sortie de virage
évitement
changement de voie dynamique
transition forte
```

Cette catégorie est importante car les résidus sont souvent plus difficiles à interpréter dans les phases combinées.

---

### 5.9 `mixed_or_unknown`

Catégorie de repli pour les fenêtres non clairement classifiables.

Critères typiques :

```text
signaux contradictoires
fenêtre trop courte
GPS mauvais
features insuffisantes
plusieurs phases dans la même fenêtre
manœuvre non claire
```

Il est préférable d’avoir une catégorie `mixed_or_unknown` plutôt que de forcer toutes les fenêtres dans des catégories faussement propres.

---

## 6. Features recommandées pour la catégorisation

Les features minimales recommandées sont :

```python
MANEUVER_FEATURES = [
    "mean_vx_kmh",
    "std_vx_kmh",
    "mean_ax",
    "rms_ax",
    "min_ax",
    "max_ax",
    "mean_ay",
    "mean_abs_ay",
    "rms_ay",
    "mean_yaw_rate",
    "mean_abs_yaw_rate",
    "rms_yaw_rate",
    "mean_steer",
    "mean_abs_steer",
    "rms_steer",
    "zero_speed_ratio",
    "low_speed_ratio",
]
```

Si les signaux de commande sont disponibles, ajouter :

```python
COMMAND_FEATURES = [
    "brake_ratio",
    "throttle_ratio",
]
```

Si le GPS est disponible, ajouter :

```python
GPS_FEATURES = [
    "gps_path_length_m",
    "gps_displacement_m",
    "gps_tortuosity",
    "gps_heading_change_abs",
    "gps_curvature_mean",
    "gps_curvature_std",
    "gps_curvature_max_abs",
    "gps_center_x",
    "gps_center_y",
]
```

---

## 7. Règles heuristiques de catégorisation

La catégorisation `maneuver_family` doit être fondée sur des règles simples.

Exemple de pseudo-code :

```python
def assign_maneuver_family(row):
    vx = row["mean_vx_kmh"]
    ax = row["mean_ax"]
    ay_abs = row["mean_abs_ay"]
    yaw_abs = row["mean_abs_yaw_rate"]
    steer_abs = row["mean_abs_steer"]
    zero_speed = row["zero_speed_ratio"]
    low_speed = row["low_speed_ratio"]

    # Seuils à calibrer sur les données
    VX_STOP = 2.0          # km/h
    VX_LOW = 10.0          # km/h
    AX_THR = 0.4           # m/s²
    AY_THR = 0.5           # m/s²
    YAW_THR = 0.04         # rad/s
    STEER_THR = 2.0        # deg, à adapter selon unité

    is_stopped = vx < VX_STOP or zero_speed > 0.7
    is_low_speed = vx < VX_LOW or low_speed > 0.7

    is_longitudinal = abs(ax) > AX_THR
    is_lateral = ay_abs > AY_THR or yaw_abs > YAW_THR or steer_abs > STEER_THR

    if is_stopped:
        return "standstill"

    if is_low_speed and is_lateral:
        return "low_speed_maneuver"

    if is_lateral and is_longitudinal:
        return "combined_longitudinal_lateral"

    if is_lateral:
        if row.get("mean_yaw_rate", 0.0) > 0:
            return "cornering_left"
        return "cornering_right"

    if is_longitudinal:
        if ax > 0:
            return "straight_acceleration"
        return "straight_braking"

    if not is_lateral and not is_longitudinal:
        return "straight_constant_speed"

    return "mixed_or_unknown"
```

Les seuils doivent être calibrés sur les distributions réelles des campagnes d’essais. Ils ne doivent pas être considérés comme universels.

---

## 8. Utilisation du GPS dans la catégorisation

Le GPS peut servir à deux usages distincts.

### 8.1 Géométrie de trajectoire

Objectif :

```text
identifier la forme de la trajectoire
```

Features utiles :

```text
gps_path_length_m
gps_displacement_m
gps_tortuosity
gps_heading_change_abs
gps_curvature_mean
gps_curvature_max_abs
```

Exemples d’interprétation :

```text
faible heading change + faible tortuosité → ligne droite
heading change élevé + courbure stable → virage
tortuosité élevée + vitesse faible → manœuvre basse vitesse
courbure alternée → slalom ou trajectoire en S
```

### 8.2 Localisation spatiale

Objectif :

```text
identifier si plusieurs fenêtres correspondent au même endroit
```

Features utiles :

```text
gps_center_x
gps_center_y
gps_start_x
gps_start_y
gps_end_x
gps_end_y
```

Cette information ne doit pas forcément entrer dans le clustering dynamique principal, car elle peut dominer les groupes. Il est préférable de conserver un identifiant séparé :

```text
gps_location_cluster_id
```

---

## 9. Cohérence dynamique / GPS

Lorsque le GPS est disponible, il est utile de comparer la manœuvre déduite des signaux dynamiques avec celle déduite de la géométrie GPS.

Ajouter les colonnes suivantes :

```text
maneuver_source
is_gps_consistent
```

Valeurs possibles pour `maneuver_source` :

```text
dynamic_only
gps_only
dynamic_gps_consistent
dynamic_gps_conflict
```

Exemples :

```text
signaux dynamiques = virage, GPS = virage
→ dynamic_gps_consistent

signaux dynamiques = virage, GPS = ligne droite
→ dynamic_gps_conflict

GPS indisponible
→ dynamic_only

signaux dynamiques insuffisants mais GPS exploitable
→ gps_only
```

Les conflits dynamique/GPS ne doivent pas forcément être considérés comme des anomalies. Ils doivent d’abord être signalés comme des cas à inspecter.

---

## 10. Clustering de contexte dynamique

Une fois `maneuver_family` attribué, le clustering de contexte se fait séparément dans chaque famille.

Exemple :

```text
groupby maneuver_family
→ standardisation robuste
→ DBSCAN / HDBSCAN
→ context_cluster_id
```

Features génériques possibles :

```python
CONTEXT_FEATURES = [
    "mean_vx_kmh",
    "rms_ax",
    "rms_ay",
    "rms_yaw_rate",
    "rms_steer",
    "zero_speed_ratio",
    "low_speed_ratio",
    "lateral_excitation_score",
    "longitudinal_excitation_score",
]
```

Le but est de regrouper des fenêtres comparables en régime dynamique et en niveau d’excitation.

---

## 11. Features par famille de manœuvre

Il peut être utile d’adapter les features de clustering selon la famille.

### Virage

```python
CORNERING_FEATURES = [
    "mean_vx_kmh",
    "rms_ay",
    "mean_abs_ay",
    "rms_yaw_rate",
    "mean_abs_yaw_rate",
    "rms_steer",
    "mean_abs_steer",
    "lateral_excitation_score",
    "gps_curvature_mean",
    "gps_curvature_max_abs",
]
```

### Freinage

```python
BRAKING_FEATURES = [
    "mean_vx_kmh",
    "mean_ax",
    "rms_ax",
    "min_ax",
    "brake_ratio",
    "longitudinal_excitation_score",
]
```

### Accélération

```python
ACCELERATION_FEATURES = [
    "mean_vx_kmh",
    "mean_ax",
    "rms_ax",
    "max_ax",
    "throttle_ratio",
    "longitudinal_excitation_score",
]
```

### Ligne droite stabilisée

```python
STRAIGHT_FEATURES = [
    "mean_vx_kmh",
    "std_vx_kmh",
    "rms_ax",
    "rms_ay",
    "rms_yaw_rate",
    "rms_steer",
    "gps_heading_change_abs",
    "gps_tortuosity",
]
```

### Manœuvre basse vitesse

```python
LOW_SPEED_FEATURES = [
    "mean_vx_kmh",
    "rms_steer",
    "rms_yaw_rate",
    "low_speed_ratio",
    "zero_speed_ratio",
    "gps_displacement_m",
    "gps_tortuosity",
]
```

---

## 12. Clustering de résidus

Le clustering de résidus doit être effectué après la catégorisation de manœuvre et le clustering de contexte.

Principe :

```text
à manœuvre comparable
et contexte dynamique comparable
→ analyser les signatures résiduelles
```

Features de résidus possibles :

```python
RESIDUAL_FEATURES = [
    "r_long_mean",
    "r_long_rms",
    "r_long_std",
    "r_long_p95_abs",
    "r_long_slope",

    "r_lat_mean",
    "r_lat_rms",
    "r_lat_std",
    "r_lat_p95_abs",
    "r_lat_slope",

    "r_yaw_mean",
    "r_yaw_rms",
    "r_yaw_std",
    "r_yaw_p95_abs",

    "gps_residual_rms",
    "gps_residual_p95_abs",
]
```

Le but n’est pas encore de produire un score d’anomalie, mais de créer une typologie descriptive des signatures de résidus.

Exemples de clusters résiduels :

```text
résidus faibles
biais longitudinal
fort résidu latéral
résidu GPS élevé
dérive lente
bruit haute fréquence
possible désynchronisation
```

---

## 13. Colonnes recommandées dans le CSV final

Le fichier final devrait contenir au minimum :

```text
window_id
json_name
date
start_time
end_time

maneuver_family
maneuver_source
maneuver_confidence
is_gps_consistent

gps_location_cluster_id
trajectory_shape_cluster_id

context_cluster_id
context_cluster_size
context_distance_to_center
context_is_noise

residual_cluster_id
residual_cluster_size
residual_distance_to_center
residual_is_noise
```

Les colonnes de features utilisées pour les décisions doivent également être conservées pour permettre l’audit.

---

## 14. Résumé JSON recommandé

Le résumé JSON doit contenir :

```json
{
  "schema_version": "window_hierarchical_cluster_index.v1",
  "n_windows": 0,
  "maneuver_families": [],
  "context_clusters": [],
  "residual_clusters": [],
  "config": {},
  "features": {
    "maneuver_features": [],
    "context_features": [],
    "residual_features": [],
    "gps_features": []
  }
}
```

Chaque cluster de contexte doit contenir :

```json
{
  "context_cluster_id": "cornering_left_ctx_003",
  "maneuver_family": "cornering_left",
  "n_windows": 145,
  "n_files": 8,
  "date_min": "2026-07-01",
  "date_max": "2026-07-03",
  "feature_medians": {},
  "feature_p25": {},
  "feature_p75": {}
}
```

Chaque cluster résiduel doit contenir :

```json
{
  "residual_cluster_id": "cornering_left_ctx_003_res_001",
  "context_cluster_id": "cornering_left_ctx_003",
  "maneuver_family": "cornering_left",
  "n_windows": 17,
  "n_files": 3,
  "date_min": "2026-07-01",
  "date_max": "2026-07-03",
  "residual_feature_medians": {},
  "residual_feature_p25": {},
  "residual_feature_p75": {}
}
```

---

## 15. Visualisations recommandées

L’application de visualisation devrait permettre :

### Vue temporelle

```text
proportion de maneuver_family par jour
proportion de context_cluster_id par jour
proportion de residual_cluster_id par jour
évolution des médianes de résidus par date
```

### Vue par fichier

```text
distribution des fenêtres par fichier
clusters dominants par fichier
fenêtres noise par fichier
```

### Vue GPS

```text
carte des fenêtres colorées par maneuver_family
carte des fenêtres colorées par context_cluster_id
carte des fenêtres colorées par residual_cluster_id
```

### Vue cluster

```text
prototype de cluster
médiane et quantiles des signaux
médiane et quantiles des résidus
exemples de fenêtres représentatives
pires fenêtres selon distance au centre
```

---

## 16. Stratégie d’implémentation

### Étape 1 — Features par fenêtre

Créer ou enrichir :

```text
window_quality_index.csv
```

avec les features dynamiques, GPS et résiduelles.

### Étape 2 — Catégorisation de manœuvre

Ajouter :

```text
maneuver_family
maneuver_source
maneuver_confidence
is_gps_consistent
```

### Étape 3 — Clustering de contexte

Produire :

```text
context_cluster_id
context_cluster_size
context_distance_to_center
context_is_noise
```

### Étape 4 — Clustering de résidus

Produire :

```text
residual_cluster_id
residual_cluster_size
residual_distance_to_center
residual_is_noise
```

### Étape 5 — Export

Produire :

```text
window_hierarchical_cluster_index.csv
window_hierarchical_cluster_summary.json
```

---

## 17. Tests recommandés

Une structure de tests `pytest` doit être prévue.

Tests minimaux :

```text
test_assign_maneuver_family_standstill
test_assign_maneuver_family_straight_constant_speed
test_assign_maneuver_family_acceleration
test_assign_maneuver_family_braking
test_assign_maneuver_family_cornering_left
test_assign_maneuver_family_cornering_right
test_assign_maneuver_family_combined
test_assign_maneuver_family_mixed
```

Tests sur le clustering :

```text
test_context_clustering_runs_with_minimal_features
test_context_clustering_skips_small_groups
test_context_cluster_ids_are_unique
test_noise_windows_are_preserved
test_summary_json_is_serializable
```

Tests sur le GPS :

```text
test_gps_straight_geometry
test_gps_cornering_geometry
test_dynamic_gps_consistency
test_dynamic_gps_conflict
```

---

## 18. Points d’attention

Les seuils ne doivent pas être considérés comme universels. Ils doivent être calibrés sur les données réelles.

Le GPS ne doit pas être utilisé aveuglément. Il faut tenir compte de sa qualité :

```text
gps_nan_ratio
gps_jump_count
gps_sampling_rate
gps_path_smoothness
gps_speed_consistency
```

Le clustering global sur toutes les fenêtres est à éviter, car il risque de regrouper principalement selon la vitesse ou l’énergie du signal, au lieu de produire des groupes métier interprétables.

La catégorie `mixed_or_unknown` est nécessaire et ne doit pas être vue comme un échec. Elle permet de préserver la qualité d’interprétation des autres catégories.

---

## 19. Résumé conceptuel

La structure proposée est :

```text
manœuvre métier
→ sous-régime dynamique
→ signature résiduelle
→ évolution temporelle et spatiale
```

La phrase directrice est :

```text
On ne cherche pas directement à détecter des anomalies.
On cherche d’abord à rendre les fenêtres comparables, puis à observer les familles de résidus qui apparaissent dans chaque contexte comparable.
```
