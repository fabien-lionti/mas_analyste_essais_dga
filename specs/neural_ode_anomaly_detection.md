# Cahier des charges — Détection d'anomalies par Neural ODE commandée

## 1. Objectif

L'objectif est de mettre en place une architecture de détection d'anomalies fondée sur une Neural Ordinary Differential Equation, ou Neural ODE, pour modéliser la dynamique temporelle des essais véhicule.

Le principe demandé est le suivant :

```text
mesures disponibles au cours du temps
    -> commandes / entrées exogènes u(t)
    -> dynamique apprise par Neural ODE
    -> état prédit x(t)
    -> comparaison avec le signal réel cible
    -> score d'anomalie
```

Le modèle ne doit pas seulement apprendre une correspondance statique entre une fenêtre passée et une valeur future. Il doit apprendre une dynamique continue :

```math
\frac{dx(t)}{dt} = f_\theta(x(t), u(t), t)
```

où :

- `x(t)` est l'état que l'on cherche à prédire ;
- `u(t)` regroupe les mesures observées utilisées comme commandes au cours du temps ;
- `f_theta` est une fonction neuronale apprise ;
- l'intégration temporelle de cette équation produit la trajectoire prédite de l'état.

L'anomalie est détectée lorsque la trajectoire réelle de l'état ne peut plus être expliquée correctement par la dynamique apprise à partir des commandes observées.

---

## 2. Interprétation de la demande

Le besoin exprimé est de remplacer ou compléter l'approche actuelle de prédiction directe par une approche plus structurelle :

1. Les signaux mesurés disponibles ne sont pas tous traités comme des cibles.
2. Une partie des signaux est utilisée comme commande temporelle `u(t)`.
3. Le signal que l'on veut surveiller est traité comme un état `x(t)`.
4. Le modèle apprend comment cet état évolue sous l'effet des commandes.
5. La détection d'anomalie repose sur l'écart entre l'état prédit et l'état mesuré.

Exemple conceptuel :

```text
u(t) = [vehicle.vx, vehicle.ax, vehicle.yaw_rate, steer_s1, steer_s2, ...]
x(t) = vehicle.ay
```

ou :

```text
u(t) = [vehicle.vx, vehicle.ax, vehicle.ay, vehicle.yaw_rate, ...]
x(t) = steer_s1
```

Le choix exact de `u(t)` et `x(t)` doit être paramétrable afin de tester plusieurs relations dynamiques.

---

## 3. Problème à résoudre

Le système doit apprendre une dynamique normale sur des trajectoires supposées valides ou majoritairement valides, puis identifier les trajectoires, fenêtres ou instants dont le comportement est incohérent avec cette dynamique.

La sortie attendue n'est pas seulement une prédiction. Elle doit fournir :

- une trajectoire prédite ;
- un résidu temporel ;
- un score d'anomalie ;
- des métriques par fichier, fenêtre, phase et cible ;
- des visualisations permettant de comprendre l'anomalie.

Le système doit permettre d'évaluer la généralisation sur un split jamais vu pendant l'entraînement.

---

## 4. Données d'entrée

### 4.1 Format attendu

Le modèle doit travailler sur les données déjà converties vers les canaux canoniques du projet, par exemple :

```text
vehicle.vx
vehicle.ax
vehicle.ay
vehicle.yaw_rate
steer_s1
steer_s2
```

Les fichiers d'entrée peuvent être les JSON resamplés déjà utilisés par les scripts actuels.

Chaque fichier doit fournir :

- une base temporelle ;
- les canaux canoniques disponibles ;
- les métadonnées utiles : nom du fichier, date, source, durée, éventuels labels d'annotation.

### 4.2 Base temporelle

Les données doivent être ramenées sur une base temporelle commune :

```math
t_0, t_1, \dots, t_{N-1}
```

avec un pas constant :

```math
\Delta t = t_{k+1} - t_k
```

La fréquence d'entraînement cible est fixée à :

```text
20 Hz
```

ce qui correspond à :

```math
\Delta t = 0.05\ \mathrm{s}
```

La première version ne doit pas gérer de pas de temps variables. Les signaux doivent être resamplés à 20 Hz en amont du modèle.

---

## 5. Définition des variables

### 5.1 Commandes `u(t)`

Les commandes sont les mesures données au modèle au cours du temps. Elles sont supposées observées pendant l'intervalle de prédiction.

Exemples :

```text
u(t) = [
  vehicle.vx,
  vehicle.ax,
  vehicle.yaw_rate,
  steer_s1,
  steer_s2
]
```

Ces commandes représentent le contexte dynamique qui force ou explique l'évolution de l'état.

### 5.2 État `x(t)`

L'état est le signal que le modèle doit prédire dynamiquement.

Exemples :

```text
x(t) = vehicle.ay
x(t) = vehicle.yaw_rate
x(t) = steer_s1
x(t) = steer_s2
```

L'état peut être scalaire ou vectoriel. La première version peut se limiter à un état scalaire par modèle pour faciliter l'interprétation et rester proche de l'interface actuelle par cible.

### 5.3 État initial

Pour chaque fenêtre ou trajectoire, l'intégration de la Neural ODE nécessite un état initial :

```math
x(t_0)
```

Cet état initial peut être :

- la première valeur mesurée de la cible ;
- une moyenne sur les premiers échantillons ;
- un état latent estimé par un encodeur si une version plus avancée est nécessaire.

La version initiale recommandée utilise directement la première valeur mesurée de la cible.

---

## 6. Architecture cible

### 6.1 Formulation

Le modèle apprend une fonction :

```math
f_\theta : (x(t), u(t), t) \rightarrow \frac{dx(t)}{dt}
```

L'état prédit est obtenu par intégration Euler discrète.

Pour le score d'anomalie principal, la première version utilise une prédiction locale one-step avec état mesuré au pas courant :

```math
\hat{x}_{k+1} = x_k + \Delta t\ f_\theta(x_k, u_k, t_k)
```

Cette formulation est volontairement différente d'une simulation libre longue depuis `x(t0)`. Elle évite que le score d'anomalie soit dominé par l'accumulation d'erreurs numériques ou par une dérive de trajectoire. Le résidu exporté mesure donc une incohérence dynamique locale :

```math
r_{k+1} = x_{k+1} - \hat{x}_{k+1}
```

Dans la première version, il n'y a pas d'interpolation de commande. Le modèle travaille uniquement sur la grille discrète resamplée à 20 Hz.

À chaque pas discret, la commande utilisée est directement la mesure du pas courant :

```math
u_k = u(t_k)
```

L'intégration se fait donc pas à pas sur la grille observée, sans requête du solveur à des temps intermédiaires.

### 6.2 Réseau de dynamique

Le réseau `f_theta` peut être un MLP léger :

```text
entrée  : concat[x(t), u(t), encodage temps optionnel]
sortie  : dx/dt
```

Configuration initiale recommandée :

```text
hidden_dim: 64 ou 128
num_layers: 2 ou 3
activation: tanh uniquement
dropout: optionnel
normalisation: standardisation entrée/sortie
```

L'activation `tanh` est imposée pour cette première version afin de conserver une dynamique bornée et régulière.

### 6.3 Gestion des commandes discrètes

Il n'y a pas d'interpolation dans la première version.

Les commandes sont utilisées telles qu'elles sont disponibles sur la grille 20 Hz :

```text
u_0, u_1, ..., u_N
```

La dynamique apprise est évaluée uniquement aux instants échantillonnés :

```math
f_\theta(x_k, u_k, t_k)
```

Conséquences :

- pas d'interpolation linéaire ;
- pas de zero-order hold explicite ;
- pas d'interpolation cubique ;
- pas d'interpolation différentiable de type CDE ;
- le prétraitement doit garantir que toutes les commandes et la cible sont alignées à 20 Hz avant l'entraînement.

Le temps peut être représenté implicitement par le pas fixe `dt = 0.05 s`. Un encodage explicite de `t_k` est optionnel, mais ne doit pas introduire de solveur à pas variable.

### 6.4 Solveur ODE

La première version doit rester simple et utiliser une intégration d'Euler explicite à pas fixe.

La mise à jour discrète est :

```math
\hat{x}_{k+1} = \hat{x}_k + \Delta t\ f_\theta(\hat{x}_k, u_k, t_k)
```

avec :

```text
dt = 0.05 s
fréquence = 20 Hz
```

Les solveurs adaptatifs ou plus complexes ne font pas partie de la première version :

```text
pas de dopri5
pas de rk4
pas de solveur adaptatif
```

Le choix d'Euler est volontaire : il rend l'implémentation, le debug et l'interprétation des résidus plus simples.

---

## 7. Pipeline d'entraînement

### 7.1 Découpage des données

Le découpage doit permettre d'évaluer la généralisation :

```text
train
validation
holdout jamais vu
```

Le holdout ne doit pas être utilisé :

- pour entraîner le modèle ;
- pour ajuster la normalisation ;
- pour choisir les hyperparamètres ;
- pour adapter le modèle.

Il sert uniquement à estimer la capacité de généralisation.

### 7.2 Fenêtrage

Chaque trajectoire est découpée en fenêtres temporelles :

```text
history_sec
horizon_sec
stride_sec
```

Pour l'anomalie, la version recommandée est :

```text
pendant l'entraînement, dérouler Euler sur un horizon court H pas depuis x(k),
avec les commandes observées u(k), ..., u(k+H-1),
puis comparer toute la trajectoire x_hat(k+1...k+H) à x(k+1...k+H).
```

Pour l'export du score d'anomalie, on conserve un résidu one-step local afin d'éviter l'accumulation de dérive numérique dans le score. Une simulation libre depuis `x(t0)` pourra être ajoutée plus tard pour visualiser la stabilité du modèle, mais elle ne doit pas être le score principal d'anomalie de la première version.

Paramètre recommandé :

```text
rollout_steps = 10
rollout_sec = 0.5 s à 20 Hz
```

### 7.3 Fonction de perte

La perte principale est une erreur de trajectoire :

```math
L_\mathrm{pred} =
\frac{1}{N}\sum_k \left|\hat{x}(t_k) - x(t_k)\right|
```

ou :

```math
L_\mathrm{pred} =
\frac{1}{N}\sum_k \left(\hat{x}(t_k) - x(t_k)\right)^2
```

Termes optionnels :

- régularisation de `dx/dt` ;
- pénalisation des dérivées trop bruitées ;
- robust loss de type Huber ;
- pondération par vitesse ou par contexte dynamique.

### 7.4 Normalisation

La normalisation doit être apprise uniquement sur le train.

Elle doit être sauvegardée avec le modèle :

```text
mean/std des commandes
mean/std des états
éventuellement min/max ou quantiles robustes
```

---

## 8. Détection d'anomalie

### 8.1 Résidu instantané

Le résidu de base est :

```math
r(t_k) = x(t_k) - \hat{x}(t_k)
```

Scores instantanés possibles :

```math
|r(t_k)|
```

```math
\frac{|r(t_k)|}{q_{95}(|x|) + \epsilon}
```

ou un score normalisé par l'incertitude si un ensemble de modèles est utilisé :

```math
\frac{|r(t_k)|}{\sigma_\mathrm{ensemble}(t_k) + \epsilon}
```

### 8.2 Score fenêtre

Chaque fenêtre doit produire des métriques agrégées :

```text
mae
rmse
q95_abs_error
max_abs_error
mean_score
q95_score
duration_above_threshold
```

### 8.3 Seuils

Les seuils doivent être calibrés sur le train ou la validation, pas sur le holdout.

Approches possibles :

```text
seuil q95 ou q99 des résidus normaux
seuil par cible
seuil par famille de manoeuvre
seuil par régime dynamique
```

### 8.4 Sorties attendues

Le système doit produire :

```text
predictions.csv
metrics_by_file.csv
metrics_by_window.csv
metrics_by_timebin.csv
anomaly_events.csv
summary.json
model.pt
standardizer.json
config.json
```

---

## 9. Visualisations attendues

L'interface doit permettre d'afficher, pour une cible donnée :

1. la trajectoire réelle `x(t)` ;
2. la trajectoire prédite `x_hat(t)` ;
3. le résidu `r(t)` ;
4. le score d'anomalie ;
5. les seuils de décision ;
6. les zones détectées comme anormales ;
7. les commandes `u(t)` utilisées par le modèle.

Pour l'évaluation de généralisation, l'interface doit permettre de comparer :

```text
train / validation
holdout jamais vu
pré-adaptation si applicable
post-adaptation si applicable
```

Dans le cas Neural ODE, la comparaison essentielle est :

```text
réel holdout
prédit holdout
résidu holdout
score anomalie holdout
```

---

## 10. Contraintes importantes

### 10.1 Pas de fuite de cible

Si une cible est prédite, elle ne doit pas être utilisée comme commande sur le même intervalle, sauf uniquement pour fournir l'état initial `x(t0)`.

Exemple :

```text
cible = steer_s1
commandes interdites = steer_s1
commandes possibles = steer_s2, vehicle.vx, vehicle.ax, vehicle.ay, vehicle.yaw_rate
```

### 10.2 Holdout réellement non vu

Le holdout doit rester strictement non vu pendant :

- la standardisation ;
- l'entraînement ;
- l'adaptation ;
- le choix de seuils ;
- la sélection de modèle.

### 10.3 Traçabilité

Chaque prédiction doit conserver :

```text
run_id
json_name
target_name
phase
time
y_true
y_pred
residual
score
command_channels
model_version
```

### 10.4 Robustesse aux canaux manquants

Le pipeline doit gérer les canaux absents :

- exclure les fichiers non exploitables pour une cible donnée ;
- tracer les canaux manquants dans un résumé ;
- éviter les remplissages silencieux qui masquent une absence réelle de mesure.

---

## 11. Intégration avec l'existant

Le projet contient déjà une logique de :

- chargement de fichiers JSON resamplés ;
- mapping vers canaux canoniques ;
- entraînement par cible ;
- séparation train / holdout ;
- export de prédictions ;
- visualisation dans l'interface Drift TCN.

La Neural ODE doit être ajoutée comme une nouvelle famille de modèle, sans supprimer le TCN existant.

Proposition d'organisation :

```text
train_neural_ode_anomaly.py
models/neural_ode.py
static/neural_ode_anomaly.html ou extension de drift_coherence.html
outputs_neural_ode_anomaly/
```

Les premiers exports doivent rester compatibles avec les visualisations existantes autant que possible :

```text
predictions.csv
batch_metrics.csv
metrics_by_file.csv
metrics_by_timebin.csv
summary.json
```

---

## 12. Critères d'acceptation

Une première version est considérée comme valide si :

1. elle permet de choisir une cible `x(t)` et une liste de commandes `u(t)` ;
2. elle entraîne une Neural ODE sur un split train sans utiliser le holdout ;
3. elle prédit des trajectoires complètes sur le holdout ;
4. elle exporte les prédictions et résidus dans des fichiers exploitables ;
5. elle produit des métriques par fichier et par phase ;
6. elle permet de visualiser réel, prédit, résidu et score d'anomalie ;
7. elle empêche explicitement la fuite de cible dans les commandes ;
8. elle sauvegarde la configuration, les normalisations et les poids du modèle ;
9. elle permet de reproduire un run à partir de sa configuration.

---

## 13. Questions ouvertes

Les points suivants doivent être tranchés avant ou pendant l'implémentation :

1. L'état `x(t)` doit-il être scalaire par modèle ou vectoriel multi-cibles ?
2. Les commandes `u(t)` doivent-elles être supposées connues sur tout l'horizon futur ?
3. Le score d'anomalie doit-il être global ou conditionné par type de manoeuvre ?
4. Faut-il intégrer une incertitude par ensemble de Neural ODE ?
5. Les labels manuels existants doivent-ils servir à calibrer ou seulement à analyser les anomalies ?

---

## 14. Version minimale recommandée

Pour démarrer sans complexifier inutilement :

```text
modèle : Neural ODE scalaire par cible
commandes : liste paramétrable de canaux canoniques
état initial : première valeur réelle de la cible dans la fenêtre
fréquence : 20 Hz
interpolation u(t) : aucune
solveur : Euler explicite à pas fixe
loss entraînement : rollout Euler multi-step court
rollout entraînement : 10 pas, soit 0.5 s à 20 Hz
score exporté : résidu one-step local
activation : tanh uniquement
loss : Huber ou MSE sur trajectoire complète
split : train / validation / holdout chronologique
score anomalie : q95_abs_error et score normalisé par quantile train
visualisation : réel, prédit, résidu, seuil, commandes
```

Cette version doit d'abord démontrer que le modèle généralise sur des trajectoires holdout jamais vues avant d'ajouter des raffinements comme l'incertitude, l'adaptation incrémentale ou les états latents encodés.
