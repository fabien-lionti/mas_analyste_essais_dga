# Spécification — Qualification de données d'essais véhicule

## 0. Objectif général

Ce document spécifie un pipeline de qualification de données d'essais véhicule destiné à produire des données propres, calibrées et exploitables pour :

- l'identification de système ;
- l'estimation de paramètres ;
- le calcul d'indicateurs ;
- la comparaison entre trajectoires similaires.

L'objectif n'est pas seulement de vérifier que les fichiers sont lisibles. L'objectif est de répondre à la question suivante :

> Est-ce que cette acquisition, ou cette fenêtre temporelle, est exploitable pour estimer une relation dynamique fiable ?

Le pipeline doit donc évaluer :

1. l'exploitabilité du fichier ;
2. la qualité univariée des signaux ;
3. la cohérence multivariée physique ;
4. la cohérence GPS / trajectoire intégrée ;
5. la structure des trajectoires similaires ;
6. l'exploitabilité pour les tâches finales.

---

## 1. Organisation générale du pipeline

Le pipeline cible suit l'ordre suivant :

```text
fichiers Dewesoft bruts
    ↓
inspection des canaux disponibles
    ↓
contrôle de propreté minimale
    ↓
mapping vers noms canoniques
    ↓
conversion unités SI et conventions de repère
    ↓
resampling sur base temporelle commune
    ↓
contrôle qualité univarié local
    ↓
contrôle qualité multivarié par familles de résidus
    ↓
segmentation / fenêtrage
    ↓
structuration des trajectoires similaires
    ↓
qualification pour identification, paramètres, indicateurs
```

Une règle importante est imposée :

> À partir de l'étape de resampling, aucun calcul aval ne doit utiliser les noms Dewesoft bruts. Tous les calculs utilisent uniquement les noms canoniques.

---

## 2. Notations générales

On considère une acquisition véhicule contenant une base temporelle commune après resampling :

$$
\mathcal{T} = \{t_0, t_1, \dots, t_{N-1}\}
$$

avec un pas d'échantillonnage constant :

$$
\Delta t = t_{k+1} - t_k
$$

et une fréquence cible :

$$
f_s = \frac{1}{\Delta t}
$$

Dans le pipeline actuel, la fréquence cible est typiquement :

$$
f_s = 100\ \mathrm{Hz}
$$

ce qui correspond à :

$$
\Delta t = 0.01\ \mathrm{s}
$$

Pour chaque canal canonique $c$, on note le signal resamplé :

$$
y_c(t_k), \quad k = 0, \dots, N-1
$$

Une fenêtre temporelle locale $w$ est définie par deux indices :

$$
w = [k_s, k_e]
$$

avec :

$$
t_{k_s} \leq t \leq t_{k_e}
$$

La durée de la fenêtre est :

$$
T_w = t_{k_e} - t_{k_s}
$$

et le nombre d'échantillons est :

$$
N_w = k_e - k_s + 1
$$

---

## 3. Standard de nommage canonique

### 3.1. Principe

Chaque canal doit conserver son nom brut Dewesoft, mais le pipeline doit travailler avec un nom canonique.

Exemple de représentation attendue :

```json
{
  "canonical_name": "vehicle.vx",
  "source_name": "VelX (km/h)",
  "raw_unit": "km/h",
  "unit": "m/s",
  "scale_applied": 0.2777777778,
  "frame": "vehicle_body",
  "values": []
}
```

Le nom brut sert à la traçabilité. Le nom canonique sert aux calculs.

---

### 3.2. Convention générale de nommage

Le schéma recommandé est :

```text
domain.component.quantity
```

Exemples :

```text
vehicle.vx
vehicle.vy
vehicle.speed
vehicle.ax
vehicle.ay
vehicle.az
vehicle.roll_rate
vehicle.pitch_rate
vehicle.yaw_rate

imu.ax_body
imu.ay_body
imu.az_body
imu.wx_body
imu.wy_body
imu.wz_body

gps.latitude
gps.longitude
gps.altitude
gps.heading
gps.pitch
gps.roll
gps.distance
gps.radius
gps.track
gps.time_of_week
gps.timestamp

wheel.fl.omega
wheel.fr.omega
wheel.rl.omega
wheel.rr.omega

wheel.fl.fx
wheel.fl.fy
wheel.fl.fz
wheel.fr.fx
wheel.fr.fy
wheel.fr.fz
wheel.rl.fx
wheel.rl.fy
wheel.rl.fz
wheel.rr.fx
wheel.rr.fy
wheel.rr.fz
```

Les unités doivent être séparées des noms. On évite donc les noms du type `vehicle.vx_kmh`. Le canal doit plutôt être :

```json
{
  "canonical_name": "vehicle.vx",
  "unit": "m/s"
}
```

---

### 3.3. Table de mapping minimale

| Nom Dewesoft brut | Nom canonique | Unité brute | Unité interne | Conversion |
|---|---:|---:|---:|---:|
| `VelX (km/h)` | `vehicle.vx` | km/h | m/s | $x/3.6$ |
| `VelY (km/h)` | `vehicle.vy` | km/h | m/s | $x/3.6$ |
| `Vel (km/h)` | `vehicle.speed` | km/h | m/s | $x/3.6$ |
| `VehYaw_W_Actl (rad/s)` | `vehicle.yaw_rate` | rad/s | rad/s | $x$ |
| `VehPtch_W_Actl (rad/s)` | `vehicle.pitch_rate` | rad/s | rad/s | $x$ |
| `VehRol_W_Actl (rad/s)` | `vehicle.roll_rate` | rad/s | rad/s | $x$ |
| `VehLong_A_Actl (m/s^2)` | `vehicle.ax` | m/s² | m/s² | $x$ |
| `VehLat_A_Actl (m/s^2)` | `vehicle.ay` | m/s² | m/s² | $x$ |
| `VehVert_A_Actl (m/s^2)` | `vehicle.az` | m/s² | m/s² | $x$ |
| `Latitude (_)` | `gps.latitude` | deg | deg | $x$ |
| `Longitude (_)` | `gps.longitude` | deg | deg | $x$ |
| `WhlFl_W_Meas (rad/s)` | `wheel.fl.omega` | rad/s | rad/s | $x$ |
| `WhlFr_W_Meas (rad/s)` | `wheel.fr.omega` | rad/s | rad/s | $x$ |
| `WhlRl_W_Meas (rad/s)` | `wheel.rl.omega` | rad/s | rad/s | $x$ |
| `WhlRr_W_Meas (rad/s)` | `wheel.rr.omega` | rad/s | rad/s | $x$ |
| `Camber_S1 (_)` | `wheel.s1.camber` | `_` | rad | à confirmer |
| `WheelSteer_S1 (_)` | `wheel.s1.steer` | `_` | rad | à confirmer |
| `Camber_S2 (_)` | `wheel.s2.camber` | `_` | rad | à confirmer |
| `WheelSteer_S2 (_)` | `wheel.s2.steer` | `_` | rad | à confirmer |

Les conversions des canaux angulaires dont l'unité brute vaut `_`, notamment `Camber_S1/S2` et `WheelSteer_S1/S2`, doivent être confirmées parce que l'unité `_` est ambiguë.

---

## 4. Variables physiques principales

Après mapping canonique et conversion SI, on définit :

$$
V_x(t) = \texttt{vehicle.vx}(t)
$$

$$
V_y(t) = \texttt{vehicle.vy}(t)
$$

$$
V(t) = \texttt{vehicle.speed}(t)
$$

$$
A_x(t) = \texttt{vehicle.ax}(t)
$$

$$
A_y(t) = \texttt{vehicle.ay}(t)
$$

$$
A_z(t) = \texttt{vehicle.az}(t)
$$

$$
r(t) = \dot{\psi}(t) = \texttt{vehicle.yaw\_rate}(t)
$$

$$
q(t) = \dot{\theta}(t) = \texttt{vehicle.pitch\_rate}(t)
$$

$$
p(t) = \dot{\phi}(t) = \texttt{vehicle.roll\_rate}(t)
$$

Pour les roues :

$$
\omega_{FL}(t) = \texttt{wheel.fl.omega}(t)
$$

$$
\omega_{FR}(t) = \texttt{wheel.fr.omega}(t)
$$

$$
\omega_{RL}(t) = \texttt{wheel.rl.omega}(t)
$$

$$
\omega_{RR}(t) = \texttt{wheel.rr.omega}(t)
$$

La vitesse roue moyenne est :

$$
\bar{\omega}(t) = \frac{1}{4}\left(\omega_{FL}(t) + \omega_{FR}(t) + \omega_{RL}(t) + \omega_{RR}(t)\right)
$$

Si $R$ est le rayon effectif de roue :

$$
V_{x,wheel}(t) = R\bar{\omega}(t)
$$

Pour les efforts :

$$
F_x^{\Sigma}(t) = F_{x,FL}(t) + F_{x,FR}(t) + F_{x,RL}(t) + F_{x,RR}(t)
$$

$$
F_y^{\Sigma}(t) = F_{y,FL}(t) + F_{y,FR}(t) + F_{y,RL}(t) + F_{y,RR}(t)
$$

$$
F_z^{\Sigma}(t) = F_{z,FL}(t) + F_{z,FR}(t) + F_{z,RL}(t) + F_{z,RR}(t)
$$

Pour la géométrie roue S1/S2 :

$$
\gamma_{S1}(t) = 	exttt{wheel.s1.camber}(t)
$$

$$
\delta_{S1}(t) = 	exttt{wheel.s1.steer}(t)
$$

$$
\gamma_{S2}(t) = 	exttt{wheel.s2.camber}(t)
$$

$$
\delta_{S2}(t) = 	exttt{wheel.s2.steer}(t)
$$

où $\gamma$ désigne le carrossage et $\delta$ l'angle de braquage roue. Les indices `S1` et `S2` peuvent représenter deux sources, deux côtés, deux essieux ou deux capteurs. Cette interprétation doit être validée avant toute fusion.

---

## 5. Paramètres véhicule nécessaires

Certains indicateurs nécessitent des paramètres de calibration.

```json
{
  "vehicle_params": {
    "mass_kg": null,
    "wheel_radius_m": null,
    "gravity_m_s2": 9.81,
    "wheelbase_m": null,
    "track_front_m": null,
    "track_rear_m": null
  }
}
```

On note :

$$
m = \text{masse du véhicule}
$$

$$
R = \text{rayon effectif de roue}
$$

$$
g = 9.81\ \mathrm{m.s^{-2}}
$$

Sans $m$ et $R$, les résidus de force et de vitesse roue peuvent être calculés seulement de manière indicative.

---

## 6. Exploitabilité du fichier

Cette étape répond à la question :

> Le fichier est-il techniquement exploitable ?

Un fichier est exploitable si les conditions suivantes sont satisfaites :

$$
\mathrm{can\_open} = 1
$$

$$
\mathrm{has\_required\_channels} = 1
$$

$$
\mathrm{has\_valid\_timebase} = 1
$$

$$
\mathrm{has\_valid\_time\_intersection} = 1
$$

$$
\mathrm{has\_resampled\_data} = 1
$$

et :

$$
T_{file} \geq T_{min}
$$

avec :

$$
T_{file} = t_{N-1} - t_0
$$

Le statut fichier est :

$$
\mathrm{status}_{file} =
\begin{cases}
\mathrm{usable}, & \text{si toutes les conditions critiques sont satisfaites} \\
\mathrm{usable\_with\_warnings}, & \text{si le fichier est exploitable mais certains canaux sont douteux} \\
\mathrm{not\_usable}, & \text{si une condition critique échoue}
\end{cases}
$$

---

## 7. Qualité univariée locale du signal

Cette étape travaille au niveau :

$$
\text{fichier} \times \text{fenêtre} \times \text{canal}
$$

Pour une fenêtre $w = [k_s,k_e]$ et un canal $c$, on analyse :

$$
\{y_c(t_k)\}_{k=k_s}^{k_e}
$$

---

### 7.1. Ratio de valeurs finies

$$
\mathrm{finite\_ratio}_{c,w}
= \frac{1}{N_w}\sum_{k=k_s}^{k_e} \mathbf{1}_{finite}\left(y_c(t_k)\right)
$$

Le ratio de valeurs manquantes est :

$$
\mathrm{nan\_ratio}_{c,w} = 1 - \mathrm{finite\_ratio}_{c,w}
$$

Règle indicative :

$$
\mathrm{quality}_{NaN} =
\begin{cases}
\mathrm{ok}, & \mathrm{finite\_ratio} \geq 0.95 \\
\mathrm{warning}, & 0.80 \leq \mathrm{finite\_ratio} < 0.95 \\
\mathrm{reject}, & \mathrm{finite\_ratio} < 0.80
\end{cases}
$$

---

### 7.2. Statistiques locales

Pour les valeurs valides de la fenêtre :

$$
\mu_{c,w} = \frac{1}{N_v}\sum_{k \in \mathcal{I}_v} y_c(t_k)
$$

$$
\sigma_{c,w} = \sqrt{\frac{1}{N_v}\sum_{k \in \mathcal{I}_v}\left(y_c(t_k)-\mu_{c,w}\right)^2}
$$

$$
\mathrm{RMS}_{c,w} = \sqrt{\frac{1}{N_v}\sum_{k \in \mathcal{I}_v} y_c(t_k)^2}
$$

avec $\mathcal{I}_v$ l'ensemble des indices valides de la fenêtre et $N_v = |\mathcal{I}_v|$.

---

### 7.3. Bruit local et variation rapide

On définit une différence discrète :

$$
\Delta y_c(t_k) = y_c(t_k) - y_c(t_{k-1})
$$

L'écart-type des différences est :

$$
\sigma_{\Delta,c,w} = \mathrm{std}\left(\Delta y_c(t_k)\right)
$$

Le saut maximal absolu est :

$$
\Delta y^{max}_{c,w} = \max_{k \in w}\left|\Delta y_c(t_k)\right|
$$

Un score de spike simple peut être :

$$
\mathrm{spike\_count}_{c,w}
= \sum_{k \in w} \mathbf{1}\left(\left|\Delta y_c(t_k)\right| > \lambda_c \sigma_{\Delta,c}\right)
$$

avec $\lambda_c$ un seuil dépendant du canal.

---

### 7.4. Zone de zéro ou basse vitesse sur $V_x$

Pour l'identification dynamique, les zones à vitesse quasi nulle doivent être identifiées.

$$
\mathrm{zero\_speed\_ratio}_{w}
= \frac{1}{N_w}\sum_{k=k_s}^{k_e}\mathbf{1}\left(|V_x(t_k)| < V_{\epsilon}\right)
$$

avec par exemple :

$$
V_{\epsilon} = \frac{1}{3.6}\ \mathrm{m.s^{-1}}
$$

ce qui correspond à $1\ \mathrm{km.h^{-1}}$.

On peut aussi définir un ratio basse vitesse :

$$
\mathrm{low\_speed\_ratio}_{w}
= \frac{1}{N_w}\sum_{k=k_s}^{k_e}\mathbf{1}\left(|V_x(t_k)| < V_{low}\right)
$$

avec :

$$
V_{low} = \frac{5}{3.6}\ \mathrm{m.s^{-1}}
$$

---

## 8. Contrôle qualité multivarié par familles de résidus

Cette section est le cœur de la qualification physique. Les résidus sont séparés par catégorie pour éviter de mélanger des problèmes de nature différente.

L'unité d'analyse est :

$$
\text{fichier} \times \text{fenêtre}
$$

Pour chaque résidu $r_j(t_k)$, on calcule des statistiques locales :

$$
\mu_{r_j,w} = \frac{1}{N_w}\sum_{k \in w} r_j(t_k)
$$

$$
\mathrm{RMS}_{r_j,w} = \sqrt{\frac{1}{N_w}\sum_{k \in w} r_j(t_k)^2}
$$

$$
\max |r_j|_w = \max_{k \in w}|r_j(t_k)|
$$

$$
Q_{95}(|r_j|)_w = \mathrm{quantile}_{0.95}\left(|r_j(t_k)|\right)
$$

Chaque résidu doit aussi porter un statut :

```text
computed
not_computable_missing_channel
not_computable_missing_parameter
not_computable_low_speed
warning_unit_or_frame_uncertain
```

---

## 8.1. Résidus cinématiques

Les résidus cinématiques vérifient la cohérence entre positions, vitesses, angles et dérivées temporelles. Ils ne nécessitent pas de masse ni de modèle de force.

### 8.1.1. Résidu distance / vitesse

Si la distance curviligne $D(t)$ est disponible via `gps.distance`, alors :

$$
r_{dist}(t) = \frac{dD}{dt}(t) - V(t)
$$

En discret :

$$
r_{dist}(t_k) = \frac{D(t_{k+1}) - D(t_{k-1})}{2\Delta t} - V(t_k)
$$

Ce résidu vérifie que la distance cumulée est cohérente avec la vitesse véhicule.

---

### 8.1.2. Résidu yaw rate / angle de lacet

Si un angle de lacet $\psi(t)$ ou un cap véhicule fiable est disponible :

$$
r_{yaw}(t) = r(t) - \frac{d\psi}{dt}(t)
$$

En discret :

$$
r_{yaw}(t_k) = r(t_k) - \frac{\psi(t_{k+1}) - \psi(t_{k-1})}{2\Delta t}
$$

Si l'angle n'est pas disponible, ce résidu est marqué :

```text
not_computable_missing_yaw_angle
```

---

### 8.1.3. Résidu de courbure véhicule

La courbure cinématique estimée par les signaux véhicule est :

$$
\kappa_{veh}(t) = \frac{r(t)}{\max(V(t), \epsilon)}
$$

Si un rayon GPS est disponible :

$$
\kappa_{gps}(t) = \frac{1}{R_{gps}(t)}
$$

Le résidu de courbure est :

$$
r_{\kappa}(t) = \kappa_{gps}(t) - \kappa_{veh}(t)
$$

Ce résidu doit être ignoré ou fortement pondéré à la baisse à basse vitesse.

---

## 8.2. Résidus d'accélération

Les résidus d'accélération vérifient la cohérence entre les accélérations mesurées et les dérivées des vitesses dans le repère véhicule.

### 8.2.1. Résidu longitudinal accélération / vitesse

$$
r_{ax}(t) = A_x(t) - \frac{dV_x}{dt}(t)
$$

En discret :

$$
r_{ax}(t_k) = A_x(t_k) - \frac{V_x(t_{k+1}) - V_x(t_{k-1})}{2\Delta t}
$$

Ce résidu correspond à une version simple de la cohérence longitudinale.

---

### 8.2.2. Résidu latéral complet

Dans le repère véhicule, la relation cinématique latérale est approximativement :

$$
A_y(t) \approx \frac{dV_y}{dt}(t) + V_x(t)r(t)
$$

Le résidu est :

$$
r_{ay}(t) = A_y(t) - \left(\frac{dV_y}{dt}(t) + V_x(t)r(t)\right)
$$

En discret :

$$
r_{ay}(t_k) = A_y(t_k) - \left(\frac{V_y(t_{k+1}) - V_y(t_{k-1})}{2\Delta t} + V_x(t_k)r(t_k)\right)
$$

Ce résidu vérifie la cohérence entre accélération latérale, vitesse latérale, vitesse longitudinale et yaw rate.

---

### 8.2.3. Résidu latéral simplifié

Si $V_y$ est indisponible ou trop bruité :

$$
r_{ay,simple}(t) = A_y(t) - V_x(t)r(t)
$$

Cette approximation est surtout valable si :

$$
\frac{dV_y}{dt}(t) \approx 0
$$

Elle est utile pour les virages quasi stationnaires, mais ne doit pas être interprétée comme une vérité générale.

---

### 8.2.4. Résidus IMU / signaux véhicule

Si les accélérations IMU body sont disponibles :

$$
r_{imu,x}(t) = a_x^b(t) - A_x(t)
$$

$$
r_{imu,y}(t) = a_y^b(t) - A_y(t)
$$

$$
r_{imu,z}(t) = a_z^b(t) - A_z(t)
$$

Ces résidus sont utiles pour détecter :

- un offset IMU ;
- un changement de repère ;
- une erreur de signe ;
- un délai temporel entre sources.

Ils doivent être interprétés avec prudence si les deux familles de signaux ne sont pas exprimées dans le même repère.

---

## 8.3. Résidus GPS / trajectoire intégrée

Le GPS apporte une référence externe. Il permet de comparer une trajectoire mesurée dans le monde avec une trajectoire reconstruite par intégration des signaux véhicule.

### 8.3.1. Projection locale GPS

À partir de la latitude et longitude, on construit une position locale :

$$
p_{gps}(t) =
\begin{bmatrix}
x_{gps}(t) \\
y_{gps}(t)
\end{bmatrix}
$$

Cette position est obtenue par projection locale, par exemple dans un repère ENU : East-North-Up.

---

### 8.3.2. Trajectoire intégrée depuis les signaux véhicule

Si un angle de cap $\psi(t)$ est disponible ou reconstruit par intégration du yaw rate :

$$
\dot{\psi}(t) = r(t)
$$

alors :

$$
\psi_{int}(t_k) = \psi_{int}(t_0) + \sum_{i=1}^{k} r(t_i)\Delta t
$$

La trajectoire intégrée est :

$$
\dot{x}_{int}(t) = V_x(t)\cos(\psi_{int}(t)) - V_y(t)\sin(\psi_{int}(t))
$$

$$
\dot{y}_{int}(t) = V_x(t)\sin(\psi_{int}(t)) + V_y(t)\cos(\psi_{int}(t))
$$

En discret :

$$
x_{int}(t_k) = x_{int}(t_0) + \sum_{i=1}^{k}\left[V_x(t_i)\cos(\psi_{int}(t_i)) - V_y(t_i)\sin(\psi_{int}(t_i))\right]\Delta t
$$

$$
y_{int}(t_k) = y_{int}(t_0) + \sum_{i=1}^{k}\left[V_x(t_i)\sin(\psi_{int}(t_i)) + V_y(t_i)\cos(\psi_{int}(t_i))\right]\Delta t
$$

---

### 8.3.3. Résidu position GPS / intégration

On définit :

$$
p_{int}(t) =
\begin{bmatrix}
x_{int}(t) \\
y_{int}(t)
\end{bmatrix}
$$

Le résidu vectoriel est :

$$
r_{gps,pos}(t) = p_{gps}(t) - p_{int}(t)
$$

L'erreur scalaire associée est :

$$
e_{gps,pos}(t) = \left\|p_{gps}(t) - p_{int}(t)\right\|_2
$$

Sur une fenêtre :

$$
\mathrm{RMSE}_{gps,pos,w}
=
\sqrt{
\frac{1}{N_w}
\sum_{k \in w}
\left\|p_{gps}(t_k) - p_{int}(t_k)\right\|_2^2
}
$$

Ce résidu est central pour détecter une incohérence entre vitesse, yaw rate, GPS et éventuellement vitesse latérale.

---

### 8.3.4. Résidu vitesse GPS / vitesse véhicule

La vitesse GPS peut être reconstruite par dérivation de la position :

$$
V_{gps}(t) = \left\|\frac{dp_{gps}}{dt}(t)\right\|_2
$$

Le résidu vitesse GPS est :

$$
r_{gps,speed}(t) = V_{gps}(t) - V(t)
$$

On peut aussi comparer à la norme des vitesses body :

$$
V_{body}(t) = \sqrt{V_x(t)^2 + V_y(t)^2}
$$

$$
r_{gps,body\_speed}(t) = V_{gps}(t) - V_{body}(t)
$$

---

### 8.3.5. Résidu cap GPS / yaw rate

Si un cap GPS $\psi_{gps}(t)$ est disponible via `gps.track` :

$$
r_{gps,yaw}(t) = \frac{d\psi_{gps}}{dt}(t) - r(t)
$$

Ce résidu doit être calculé seulement si :

$$
V(t) > V_{min,gps\_heading}
$$

par exemple :

$$
V_{min,gps\_heading} = \frac{5}{3.6}\ \mathrm{m.s^{-1}}
$$

car le cap GPS est instable à très basse vitesse.

---

## 8.4. Résidus roues / roulement

Les résidus roues vérifient la cohérence entre vitesses de roue, vitesse véhicule et paramètres de roue.

### 8.4.1. Résidu vitesse roue moyenne

$$
r_{wheel}(t) = V_x(t) - R\bar{\omega}(t)
$$

Un résidu relatif est :

$$
r_{wheel,rel}(t) = \frac{V_x(t) - R\bar{\omega}(t)}{\max(|V_x(t)|, \epsilon)}
$$

Ce résidu peut signaler :

- une erreur de rayon roue ;
- une erreur d'unité ;
- un mauvais signe de rotation ;
- du glissement ;
- un blocage roue.

---

### 8.4.2. Résidus roue par essieu et côté

Différence avant gauche / avant droite :

$$
r_{wheel,front\_diff}(t) = \omega_{FL}(t) - \omega_{FR}(t)
$$

Différence arrière gauche / arrière droite :

$$
r_{wheel,rear\_diff}(t) = \omega_{RL}(t) - \omega_{RR}(t)
$$

Différence côté gauche avant / arrière :

$$
r_{wheel,left\_diff}(t) = \omega_{FL}(t) - \omega_{RL}(t)
$$

Différence côté droit avant / arrière :

$$
r_{wheel,right\_diff}(t) = \omega_{FR}(t) - \omega_{RR}(t)
$$

Ces résidus sont utiles pour détecter des incohérences de capteur roue, mais ils ne doivent pas être interprétés comme nuls en virage ou en glissement.

---

## 8.5. Résidus force / dynamique globale

Les résidus de force vérifient la cohérence entre efforts roue et accélérations véhicule. Ils nécessitent la masse $m$, les conventions de signe et les repères des efforts.

### 8.5.1. Résidu force longitudinale

$$
r_{Fx}(t) = F_x^{\Sigma}(t) - m A_x(t)
$$

Une version enrichie peut retirer les efforts aérodynamiques, de roulement et de pente :

$$
r_{Fx,extended}(t)
= F_x^{\Sigma}(t) - mA_x(t) - F_{drag}(t) - F_{roll}(t) - F_{slope}(t)
$$

La version enrichie nécessite des modèles supplémentaires.

---

### 8.5.2. Résidu force latérale

$$
r_{Fy}(t) = F_y^{\Sigma}(t) - m A_y(t)
$$

Ce résidu vérifie la cohérence entre efforts latéraux et accélération latérale.

Il dépend fortement :

- du repère des efforts roue ;
- des conventions de signe ;
- de la projection gravitaire ;
- du roulis ;
- des filtres et délais capteurs.

---

### 8.5.3. Résidu force verticale

$$
r_{Fz}(t) = F_z^{\Sigma}(t) - mg
$$

Sur une fenêtre :

$$
\overline{r}_{Fz,w} = \frac{1}{N_w}\sum_{k \in w} r_{Fz}(t_k)
$$

$$
\mathrm{RMS}_{r_{Fz},w} = \sqrt{\frac{1}{N_w}\sum_{k \in w} r_{Fz}(t_k)^2}
$$

Ce résidu sert surtout à vérifier l'ordre de grandeur des charges verticales.

---

## 8.6. Résidus de calibration / convention

Ces résidus ne mesurent pas directement la dynamique. Ils servent à détecter des problèmes de signe, unité, repère ou délai.

### 8.6.1. Résidu de signe latéral

On peut comparer le signe de l'accélération latérale, du yaw rate et de l'angle de direction.

Exemple d'indicateur :

$$
C_{ay,r}(w) = \mathrm{corr}\left(A_y(t_k), r(t_k)\right)_{k \in w}
$$

$$
C_{\delta,r}(w) = \mathrm{corr}\left(\bar{\delta}(t_k), r(t_k)\right)_{k \in w}
$$

Une corrélation systématiquement opposée à l'attendu peut indiquer un problème de signe.

---

### 8.6.2. Résidu de délai temporel

Pour deux signaux supposés liés $x(t)$ et $y(t)$, on peut estimer un retard par corrélation croisée :

$$
\tau^* = \arg\max_{\tau \in [-\tau_{max}, \tau_{max}]} \mathrm{corr}\left(x(t), y(t+\tau)\right)
$$

Exemples :

$$
x(t) = \frac{dV_x}{dt}(t), \quad y(t) = A_x(t)
$$

$$
x(t) = V_x(t)r(t), \quad y(t) = A_y(t)
$$

Un retard important peut signaler un décalage temporel entre bus, GPS, IMU ou capteurs roue.

---

## 8.7. Scores par famille de résidus

Chaque famille de résidus reçoit un score séparé.

Pour un résidu $r_j$ :

$$
S_j(w) = \exp\left(-\frac{\mathrm{RMS}_{r_j,w}}{\tau_j}\right)
$$

avec $\tau_j$ un seuil caractéristique du résidu.

Score cinématique :

$$
S_{kin}(w) = \frac{\sum_{j \in \mathcal{R}_{kin,w}} \alpha_j S_j(w)}{\sum_{j \in \mathcal{R}_{kin,w}} \alpha_j}
$$

Score accélération :

$$
S_{acc}(w) = \frac{\sum_{j \in \mathcal{R}_{acc,w}} \alpha_j S_j(w)}{\sum_{j \in \mathcal{R}_{acc,w}} \alpha_j}
$$

Score GPS :

$$
S_{gps}(w) = \frac{\sum_{j \in \mathcal{R}_{gps,w}} \alpha_j S_j(w)}{\sum_{j \in \mathcal{R}_{gps,w}} \alpha_j}
$$

Score roues :

$$
S_{wheel}(w) = \frac{\sum_{j \in \mathcal{R}_{wheel,w}} \alpha_j S_j(w)}{\sum_{j \in \mathcal{R}_{wheel,w}} \alpha_j}
$$

Score forces :

$$
S_{force}(w) = \frac{\sum_{j \in \mathcal{R}_{force,w}} \alpha_j S_j(w)}{\sum_{j \in \mathcal{R}_{force,w}} \alpha_j}
$$

Score calibration :

$$
S_{calib}(w) = \frac{\sum_{j \in \mathcal{R}_{calib,w}} \alpha_j S_j(w)}{\sum_{j \in \mathcal{R}_{calib,w}} \alpha_j}
$$

Score physique global :

$$
S_{phys}(w)
=
\lambda_{kin}S_{kin}(w)
+\lambda_{acc}S_{acc}(w)
+\lambda_{gps}S_{gps}(w)
+\lambda_{wheel}S_{wheel}(w)
+\lambda_{force}S_{force}(w)
+\lambda_{calib}S_{calib}(w)
$$

avec :

$$
\lambda_{kin}+\lambda_{acc}+\lambda_{gps}+\lambda_{wheel}+\lambda_{force}+\lambda_{calib}=1
$$

---

## 8.8. Segmentation / fenêtrage et conservation temporelle

La segmentation / fenêtrage consiste à découper chaque acquisition en unités temporelles locales afin de qualifier les données à une échelle pertinente.

L'objectif n'est pas seulement de décider si un fichier complet est exploitable, mais d'identifier quelles portions temporelles du fichier sont propres, cohérentes physiquement, informatives et comparables à d'autres portions.

On distingue deux niveaux :

```text
window  = fenêtre temporelle régulière de durée fixe
segment = regroupement de fenêtres voisines partageant une même structure de manœuvre
```

### 8.8.1. Fenêtrage régulier

À partir de la base temporelle commune :

$$
\mathcal{T} = \{t_0, t_1, \dots, t_{N-1}\}
$$

on définit des fenêtres temporelles :

$$
w_i = [t_i, t_i + T_w]
$$

avec :

$$
T_w = \text{durée de fenêtre}
$$

et un pas de glissement :

$$
T_s = \text{stride}
$$

Exemple recommandé :

```text
window_length_sec = 10
window_stride_sec = 5
```

À une fréquence de 100 Hz, une fenêtre de 10 secondes contient :

$$
N_w = 1000
$$

échantillons.

### 8.8.2. Conservation du timestamp date et heure

Le pipeline ne doit pas seulement conserver un temps relatif en secondes. Il doit aussi conserver la date et l'heure associées aux données, lorsque l'information existe dans le fichier source.

On distingue :

$$
t_{rel}(k) = k\Delta t
$$

qui sert aux calculs numériques après resampling, et :

$$
t_{abs}(k)
$$

qui sert à replacer les signaux dans le temps réel de l'essai.

La base temporelle recommandée est :

```json
{
  "timebase": {
    "time_s": [],
    "timestamp_raw": [],
    "timestamp_datetime": [],
    "timestamp_date": [],
    "timestamp_time": [],
    "timestamp_day": [],
    "timestamp_hour": [],
    "timestamp_iso": [],
    "timezone": null,
    "source_time_channel": null
  }
}
```

Chaque fenêtre doit conserver :

```text
window_start_sec
window_end_sec
window_start_timestamp
window_end_timestamp
window_center_timestamp
window_start_date
window_center_date
window_start_time
window_center_time
window_start_hour
window_center_hour
window_day_index
time_source
```

Cette information est indispensable pour analyser l'évolution de la moyenne des résidus, du bruit, des spikes et des scores au cours du temps, par exemple par jour, par heure, par bin de vitesse ou par famille de manœuvre.

### 8.8.3. Agrégations temporelles par jour, heure et bins

Après calcul des métriques par fenêtre, on peut produire une table agrégée :

```text
time_bin_quality_summary.csv
```

Colonnes recommandées :

```text
aggregation_level
aggregation_date
aggregation_hour
speed_bin
lat_acc_bin
long_acc_bin
steer_bin
maneuver_family
trajectory_shape_label
similarity_group_id
window_count

r_ax_rms_mean
r_ax_rms_std
r_ay_rms_mean
r_ay_rms_std
r_gps_pos_rmse_mean
r_gps_pos_rmse_std
r_wheel_rms_mean
r_wheel_rms_std

signal_noise_mean
spike_count_sum
physical_consistency_score_mean
global_quality_score_mean
```

Exemple de regroupement utile :

```text
group by window_center_date, speed_bin, maneuver_family, trajectory_shape_label
compute mean(r_ax_rms), std(r_ax_rms), mean(r_gps_pos_rmse), std(signal_noise)
```

Cela permet de répondre à des questions comme :

```text
Est-ce que le résidu d'accélération augmente au fil de la journée ?
Est-ce que le bruit IMU est plus fort sur certains jours ?
Est-ce que les lignes droites GPS à 60-80 km/h sont stables dans le temps ?
Est-ce qu'un groupe de trajectoires devient progressivement moins cohérent ?
```

### 8.8.4. Segmentation par manœuvre

Après fenêtrage régulier, chaque fenêtre reçoit une famille de manœuvre :

```text
stopped
straight
lateral
longitudinal
combined
unknown
```

Cette famille est déterminée à partir de grandeurs locales comme :

$$
\overline{V}_{x,w}, \quad A_{x,RMS,w}, \quad A_{y,RMS,w}, \quad r_{RMS,w}, \quad \delta_{RMS,w}
$$

Une fenêtre rectiligne peut par exemple être définie par :

$$
\overline{V}_{x,w} > V_{min}
$$

$$
A_{y,RMS,w} < a_{y,straight}
$$

$$
r_{RMS,w} < r_{straight}
$$

$$
\delta_{RMS,w} < \delta_{straight}
$$

Si le GPS est disponible, on peut ajouter un critère géométrique :

$$
\kappa_{gps,RMS,w} < \kappa_{straight}
$$

ou une erreur faible d'ajustement à une droite locale.

### 8.8.5. Fusion en segments homogènes

Des fenêtres voisines peuvent être fusionnées si elles possèdent les mêmes labels principaux :

```text
maneuver_family
speed_bin
direction
gps_geometry
```

On obtient alors un segment homogène :

```text
segment_id
segment_start_sec
segment_end_sec
segment_start_timestamp
segment_end_timestamp
segment_family
```

---

## 9. Structuration globale des trajectoires similaires

Cette étape sert à regrouper des fenêtres comparables physiquement.

L'unité d'analyse est :

$$
\text{fichier} \times \text{fenêtre}
$$

Chaque fenêtre reçoit des labels globaux.

---

### 9.1. Vitesse moyenne et speed bin

La vitesse moyenne sur la fenêtre est :

$$
\overline{V}_{x,w} = \frac{1}{N_w}\sum_{k \in w} V_x(t_k)
$$

En $\mathrm{km.h^{-1}}$ :

$$
\overline{V}_{x,w}^{kmh} = 3.6\overline{V}_{x,w}
$$

Définition des bins :

```text
speed_bin:
  0-10 km/h
  10-20 km/h
  20-30 km/h
  30-40 km/h
  40-50 km/h
  50-60 km/h
  60-70 km/h
  70-80 km/h
  80-90 km/h
  90-100 km/h
```

Formellement :

$$
\mathrm{speed\_bin}(w) =
\begin{cases}
0\_20, & 0 \leq \overline{V}_{x,w}^{kmh} < 20 \\
20\_40, & 20 \leq \overline{V}_{x,w}^{kmh} < 40 \\
40\_60, & 40 \leq \overline{V}_{x,w}^{kmh} < 60 \\
60\_80, & 60 \leq \overline{V}_{x,w}^{kmh} < 80 \\
80\_100, & 80 \leq \overline{V}_{x,w}^{kmh} < 100 \\
100\_120, & 100 \leq \overline{V}_{x,w}^{kmh} < 120 \\
out\_of\_range, & \text{sinon}
\end{cases}
$$

---

### 9.2. Accélération latérale et lat_acc bin

On définit :

$$
A_{y,RMS,w} = \sqrt{\frac{1}{N_w}\sum_{k \in w} A_y(t_k)^2}
$$

Puis :

$$
\mathrm{lat\_acc\_bin}(w) =
\begin{cases}
faible, & A_{y,RMS,w} < 1 \\
moyen, & 1 \leq A_{y,RMS,w} < 3 \\
fort, & 3 \leq A_{y,RMS,w} < 6 \\
tres\_fort, & A_{y,RMS,w} \geq 6
\end{cases}
$$

---

### 9.3. Accélération longitudinale et long_acc bin

$$
A_{x,RMS,w} = \sqrt{\frac{1}{N_w}\sum_{k \in w} A_x(t_k)^2}
$$

$$
\mathrm{long\_acc\_bin}(w) =
\begin{cases}
faible, & A_{x,RMS,w} < 0.5 \\
moyen, & 0.5 \leq A_{x,RMS,w} < 2 \\
fort, & A_{x,RMS,w} \geq 2
\end{cases}
$$

Les seuils sont indicatifs et doivent être calibrés.

---

### 9.4. Steer bin

À partir d'un angle de direction moyen $\bar{\delta}$ :

$$
\delta_{RMS,w} = \sqrt{\frac{1}{N_w}\sum_{k \in w} \bar{\delta}(t_k)^2}
$$

$$
\mathrm{steer\_bin}(w) =
\begin{cases}
faible, & \delta_{RMS,w} < \delta_1 \\
moyen, & \delta_1 \leq \delta_{RMS,w} < \delta_2 \\
fort, & \delta_{RMS,w} \geq \delta_2
\end{cases}
$$

Les seuils $\delta_1$ et $\delta_2$ dépendent de l'unité réelle du canal de direction.

### 9.4.b. Canaux `WheelSteer` et `Camber` S1/S2

Certains fichiers contiennent deux familles de canaux liées à la géométrie roue :

```text
Camber_S1 (_)
WheelSteer_S1 (_)
Camber_S2 (_)
WheelSteer_S2 (_)
```

Après mapping canonique, on définit :

$$
\gamma_{S1}(t) = \texttt{wheel.s1.camber}(t)
$$

$$
\delta_{S1}(t) = \texttt{wheel.s1.steer}(t)
$$

$$
\gamma_{S2}(t) = \texttt{wheel.s2.camber}(t)
$$

$$
\delta_{S2}(t) = \texttt{wheel.s2.steer}(t)
$$

La différence entre `WheelSteer_S1` et `WheelSteer_S2` ne doit pas être confondue avec une erreur de mesure tant que la signification physique de `S1` et `S2` n'est pas validée.

Deux interprétations sont possibles :

```text
Cas A — S1/S2 sont deux mesures redondantes du même angle roue.
Cas B — S1/S2 désignent deux roues, deux côtés ou deux essieux différents.
```

Dans le cas A, on peut définir des résidus de cohérence :

$$
r_{\delta,S1S2}(t) = \delta_{S1}(t) - \delta_{S2}(t)
$$

$$
r_{\gamma,S1S2}(t) = \gamma_{S1}(t) - \gamma_{S2}(t)
$$

Sur une fenêtre $w$, on calcule :

$$
\mathrm{RMS}_{\delta,S1S2,w}
=
\sqrt{
\frac{1}{N_w}
\sum_{k \in w}
r_{\delta,S1S2}(t_k)^2
}
$$

$$
\mathrm{RMS}_{\gamma,S1S2,w}
=
\sqrt{
\frac{1}{N_w}
\sum_{k \in w}
r_{\gamma,S1S2}(t_k)^2
}
$$

On calcule aussi les corrélations :

$$
C_{\delta,S1S2}(w)
=
\mathrm{corr}
\left(
\delta_{S1}(t_k),
\delta_{S2}(t_k)
\right)_{k \in w}
$$

$$
C_{\gamma,S1S2}(w)
=
\mathrm{corr}
\left(
\gamma_{S1}(t_k),
\gamma_{S2}(t_k)
\right)_{k \in w}
$$

Le pipeline doit produire un statut d'interprétation :

```text
wheel_geometry_interpretation:
  redundant_sensors
  left_right_or_axle_difference
  unknown
```

Tant que l'interprétation est `unknown`, les canaux `WheelSteer_S1`, `WheelSteer_S2`, `Camber_S1` et `Camber_S2` doivent être conservés séparément.

Pour construire le `steer_bin`, on ne doit pas utiliser directement un canal brut. On définit d'abord :

$$
\bar{\delta}(t) = \texttt{wheel.steer.consolidated}(t)
$$

Règle recommandée :

```text
if S1/S2 are redundant and coherent:
    wheel.steer.consolidated = 0.5 * (wheel.s1.steer + wheel.s2.steer)
elif S1 is the trusted source:
    wheel.steer.consolidated = wheel.s1.steer
elif S2 is the trusted source:
    wheel.steer.consolidated = wheel.s2.steer
else:
    wheel.steer.consolidated = not_computable_unknown_geometry
```

Le camber ne sert pas directement au `steer_bin`, mais il peut servir à qualifier la géométrie roue, le roulis, les efforts latéraux et l'exploitabilité pour l'estimation de paramètres pneu.

---

### 9.5. Direction de manœuvre

On peut utiliser le signe moyen du yaw rate :

$$
\bar{r}_w = \frac{1}{N_w}\sum_{k \in w} r(t_k)
$$

$$
\mathrm{direction}(w) =
\begin{cases}
left, & \bar{r}_w > r_{min} \\
right, & \bar{r}_w < -r_{min} \\
mixed, & \text{si changement de signe significatif} \\
straight, & |\bar{r}_w| \leq r_{min}
\end{cases}
$$

Le mapping `left/right` dépend de la convention de signe.

---

### 9.6. Famille de manœuvre

On définit :

$$
r_{RMS,w} = \sqrt{\frac{1}{N_w}\sum_{k \in w} r(t_k)^2}
$$

La famille de manœuvre est :

$$
\mathrm{maneuver\_family}(w) =
\begin{cases}
stopped, & \overline{V}_{x,w}^{kmh} < 1 \\
straight, & \overline{V}_{x,w}^{kmh} \geq 5,\ A_{y,RMS,w}<a_y^0,\ r_{RMS,w}<r^0,\ \delta_{RMS,w}<\delta^0 \\
lateral, & A_{y,RMS,w}\geq a_y^1,\ r_{RMS,w}\geq r^1,\ A_{x,RMS,w}<a_x^1 \\
longitudinal, & A_{x,RMS,w}\geq a_x^1,\ A_{y,RMS,w}<a_y^1 \\
combined, & A_{x,RMS,w}\geq a_x^1,\ A_{y,RMS,w}\geq a_y^1 \\
unknown, & \text{sinon}
\end{cases}
$$

---

### 9.7. Similarity group ID

Un identifiant de groupe comparable est construit par concaténation de labels :

$$
\mathrm{similarity\_group\_id}(w)
= \mathrm{family}(w)
\oplus \mathrm{speed\_bin}(w)
\oplus \mathrm{lat\_acc\_bin}(w)
\oplus \mathrm{steer\_bin}(w)
\oplus \mathrm{direction}(w)
$$

Exemple :

```text
lateral__v_60_80__ay_moyen__steer_moyen__dir_left
```

Les comparaisons entre fenêtres doivent être réalisées prioritairement à l'intérieur d'un même groupe.

---

## 10. Excitation et informativité pour identification

Une fenêtre propre n'est pas nécessairement informative. Pour l'identification, il faut aussi mesurer l'excitation.

### 10.1. Excitation latérale

$$
E_{lat}(w) = \alpha_1\delta_{RMS,w} + \alpha_2 r_{RMS,w} + \alpha_3 A_{y,RMS,w}
$$

$$
S_{exc,lat}(w) = \min\left(1, \frac{E_{lat}(w)}{E_{lat}^{ref}}\right)
$$

---

### 10.2. Excitation longitudinale

$$
E_{long}(w) = \beta_1 A_{x,RMS,w} + \beta_2 \mathrm{std}(V_x)_w
$$

$$
S_{exc,long}(w) = \min\left(1, \frac{E_{long}(w)}{E_{long}^{ref}}\right)
$$


---

## 11. Exploitabilité par tâche finale

### 11.1. Identification latérale

Critères typiques :

$$
\overline{V}_{x,w}^{kmh} \geq V_{min,lat}
$$

$$
S_{exc,lat}(w) \geq \tau_{exc,lat}
$$

$$
\mathrm{RMS}_{r_{ay},w} \leq \tau_{r,ay}
$$

$$
A_{x,RMS,w} \leq A_{x,max,lat}
$$

Alors :

$$
\mathrm{usable\_for\_lateral\_identification}(w) = 1
$$

---

### 11.2. Identification longitudinale

Critères typiques :

$$
S_{exc,long}(w) \geq \tau_{exc,long}
$$

$$
\mathrm{RMS}_{r_{ax},w} \leq \tau_{r,ax}
$$

$$
A_{y,RMS,w} \leq A_{y,max,long}
$$

Alors :

$$
\mathrm{usable\_for\_longitudinal\_identification}(w) = 1
$$

---

### 11.3. Estimation de paramètres pneu

Une fenêtre est exploitable pour des paramètres pneu si :

$$
\overline{V}_{x,w}^{kmh} \geq V_{min,tire}
$$

$$
F_z^{\Sigma}(t) \text{ est cohérent}
$$

$$
F_x, F_y, F_z \text{ sont disponibles}
$$

$$
S_{wheel}(w) \geq \tau_{wheel,tire}
$$

$$
S_{force}(w) \geq \tau_{force,tire}
$$

---

### 11.4. Calcul d'indicateurs

Une fenêtre est exploitable pour indicateurs si :

$$
\mathrm{channels\_required\_for\_indicator} \subseteq \mathrm{available\_canonical\_channels}
$$

$$
S_{signal}(w) \geq \tau_{indicator}
$$

et :

$$
\mathrm{maneuver\_family}(w) \neq unknown
$$

---

## 12. Scores globaux

### 12.1. Score signal

$$
S_{signal}(w) = \frac{1}{|\mathcal{C}_w|}\sum_{c \in \mathcal{C}_w} S_c(w)
$$

avec $S_c(w)$ le score de qualité univariée du canal $c$.

---

### 12.2. Score physique

$$
S_{phys}(w)
=
\lambda_{kin}S_{kin}(w)
+\lambda_{acc}S_{acc}(w)
+\lambda_{gps}S_{gps}(w)
+\lambda_{wheel}S_{wheel}(w)
+\lambda_{force}S_{force}(w)
+\lambda_{calib}S_{calib}(w)
$$

---

### 12.3. Score global

$$
S_{global}(w) = \lambda_1 S_{signal}(w) + \lambda_2 S_{phys}(w) + \lambda_3 S_{exc}(w)
$$

avec :

$$
\lambda_1 + \lambda_2 + \lambda_3 = 1
$$

Selon la tâche, $S_{exc}$ peut être $S_{exc,lat}$, $S_{exc,long}$ ou une combinaison.

---

## 13. Sorties recommandées

### 13.1. JSON enrichi par acquisition

Structure recommandée :

```json
{
  "file": "...",
  "filepath": "...",
  "date": "...",
  "target_hz": 100.0,
  "timebase": {
    "time_s": [],
    "timestamp_raw": [],
    "timestamp_datetime": [],
    "timestamp_date": [],
    "timestamp_time": [],
    "timestamp_day": [],
    "timestamp_hour": [],
    "timestamp_iso": [],
    "timezone": null,
    "source_time_channel": null
  },
  "channels": {
    "vehicle.vx": {
      "source_name": "VelX (km/h)",
      "raw_unit": "km/h",
      "unit": "m/s",
      "frame": "vehicle_body",
      "values": []
    }
  },
  "quality": {
    "file_quality": {},
    "channel_quality": {},
    "residual_quality": {
      "kinematic": {},
      "acceleration": {},
      "gps": {},
      "wheel": {},
      "force": {},
      "calibration": {}
    }
  },
  "windows": []
}
```

---

### 13.2. Table globale de fenêtres

Un fichier recommandé :

```text
window_quality_index.csv
```

Une ligne correspond à une fenêtre.

Colonnes minimales :

```text
file
file_id
acquisition_date
acquisition_start_datetime
acquisition_start_time
window_id
window_start_sec
window_end_sec
window_start_timestamp
window_end_timestamp
window_center_timestamp
window_start_date
window_center_date
window_start_time
window_center_time
window_start_hour
window_center_hour
window_day_index
time_source

mean_vx
rms_ax
rms_ay
rms_yaw_rate
rms_steer
wheel_s1_camber_rms
wheel_s2_camber_rms
wheel_s1_steer_rms
wheel_s2_steer_rms
wheel_steer_consolidated_rms

speed_bin
lat_acc_bin
long_acc_bin
steer_bin
maneuver_direction
maneuver_family
similarity_group_id
trajectory_shape_label
trajectory_curvature_rms
trajectory_straightness_score

r_dist_rms
r_yaw_rms
r_kappa_rms
r_ax_rms
r_ay_rms
r_ay_simple_rms
r_gps_pos_rmse
r_gps_speed_rms
r_gps_yaw_rms
r_wheel_rms
r_wheel_rel_rms
wheel_s1_s2_camber_mean_diff
wheel_s1_s2_camber_rms_diff
wheel_s1_s2_camber_corr
wheel_s1_s2_steer_mean_diff
wheel_s1_s2_steer_rms_diff
wheel_s1_s2_steer_max_diff
wheel_s1_s2_steer_corr
wheel_s1_s2_steer_delay
wheel_geometry_interpretation
wheel_geometry_consistency
r_Fx_rms
r_Fy_rms
r_Fz_rms

signal_quality_score
kinematic_score
acceleration_score
gps_score
wheel_score
force_score
calibration_score
physical_consistency_score
lateral_excitation_score
longitudinal_excitation_score
global_quality_score
r_ax_drift_slope
r_ay_drift_slope
r_gps_pos_drift_slope
r_wheel_drift_slope
visualization_status

usable_for_lateral_identification
usable_for_longitudinal_identification
usable_for_tire_parameter_estimation
usable_for_indicator_computation
```

---

### 13.3. Sorties de visualisation et contrôle visuel

Le pipeline doit produire des visualisations destinées à vérifier rapidement que les signaux, les résidus, les indicateurs et les labels de trajectoire sont cohérents.

L'objectif n'est pas de remplacer les indicateurs numériques, mais de rendre leur évolution inspectable. À ce stade, le pipeline ne doit pas produire de score d'anomalie ni de flag automatique d'anomalie. Il calcule des indicateurs, conserve leur contexte temporel et laisse l'utilisateur filtrer, comparer et visualiser les situations douteuses.


Principe important : les sorties de visualisation ne doivent pas contenir de logique de décision du type `is_outlier=true`, `is_anomaly=true` ou `anomaly_score`. Les seules informations produites sont des métriques, des résidus, des statistiques de bruit, des labels de contexte et des timestamps. Les éventuelles zones à inspecter sont obtenues par filtrage interactif dans l'application.

#### 13.3.1. Visualisations par acquisition

Pour chaque acquisition, produire au minimum :

```text
plots/{file_id}/signals_overview.html
plots/{file_id}/residuals_overview.html
plots/{file_id}/gps_trajectory.html
plots/{file_id}/indicators_timeline.html
```

La figure `signals_overview` doit contenir les principaux signaux temporels :

```text
vehicle.vx
vehicle.ax
vehicle.ay
vehicle.yaw_rate
wheel.steer.consolidated
wheel.s1.steer
wheel.s2.steer
wheel.s1.camber
wheel.s2.camber
```

La figure `residuals_overview` doit contenir les familles de résidus principales :

```text
r_ax
r_ay
r_ay_simple
r_gps_pos
r_gps_speed
r_wheel
r_delta_s1s2
r_gamma_s1s2
```

La figure `indicators_timeline` doit afficher les indicateurs principaux sur l'axe temporel absolu, sans transformer automatiquement les valeurs élevées en indicateurs.

#### 13.3.2. Visualisations par fenêtre

Pour chaque fenêtre sélectionnée par l'utilisateur, ou repérée par filtrage sur indicateurs, produire une vue locale centrée sur la fenêtre :

```text
plots/{file_id}/windows/{window_id}_local_signals.html
plots/{file_id}/windows/{window_id}_local_residuals.html
plots/{file_id}/windows/{window_id}_gps_context.html
```

Chaque visualisation locale doit afficher :

```text
window_id
window_start_sec
window_end_sec
window_start_timestamp
window_end_timestamp
window_center_date
window_center_time
selected_indicator_names
channels_displayed
quality_status
```

#### 13.3.3. Visualisations globales par groupe, date, heure et bins

Pour chaque `similarity_group_id`, produire des visualisations agrégées :

```text
plots/groups/{similarity_group_id}/residual_distribution.html
plots/groups/{similarity_group_id}/residual_drift_over_time.html
plots/groups/{similarity_group_id}/trajectory_overlay.html
plots/groups/{similarity_group_id}/quality_summary.html
```

Ces figures doivent pouvoir être filtrées ou agrégées par :

```text
window_center_date
window_center_hour
speed_bin
lat_acc_bin
long_acc_bin
steer_bin
maneuver_family
trajectory_shape_label
similarity_group_id
```

Exemples de courbes à produire :

```text
mean(r_ax_rms) par jour pour chaque speed_bin
std(r_ax_rms) par jour pour chaque trajectory_shape_label
mean(r_gps_pos_rmse) par heure pour les trajectoires straight_gps
physical_consistency_score moyen par jour et par famille de manœuvre
std(vehicle.ay) moyen par heure pour chaque speed_bin
mean(r_ax_rms) par heure pour les trajectoires GPS rectilignes
```

#### 13.3.4. Filtrage par trajectoires GPS rectilignes

Une classe de visualisation importante concerne les trajectoires GPS rectilignes.

À partir de la position GPS locale :

$$
p_{gps}(t) = [x_{gps}(t), y_{gps}(t)]^\top
$$

On peut estimer une courbure géométrique locale :

$$
\kappa_{gps}(t)
=
\frac{\dot{x}_{gps}(t)\ddot{y}_{gps}(t) - \dot{y}_{gps}(t)\ddot{x}_{gps}(t)}{\left(\dot{x}_{gps}(t)^2 + \dot{y}_{gps}(t)^2\right)^{3/2}}
$$

Une fenêtre peut être labellisée rectiligne si :

$$
\kappa_{gps,RMS,w} < \kappa_{straight}
$$

et si la vitesse moyenne est suffisante :

$$
\overline{V}_{x,w} > V_{min,straight}
$$

On définit alors :

```text
trajectory_shape_label = straight_gps
```

Sur ces fenêtres, on peut suivre la dérive des résidus au cours du temps absolu, par exemple :

```text
trajectory_shape_label == straight_gps
speed_bin == v_40_60
steer_bin == faible
```

Puis tracer :

```text
r_ax_rms
r_ay_simple_rms
r_gps_pos_rmse
r_wheel_rms
wheel_s1_s2_steer_rms_diff
```

en fonction de :

```text
window_center_timestamp
window_center_date
window_center_hour
```

Cela permet de détecter une dérive d'accéléromètre, une dérive GPS, une désynchronisation progressive ou une variation de calibration roue.

#### 13.3.5. Manifest de visualisation

Chaque figure générée doit être référencée dans un manifest machine-readable :

```text
visualization_manifest.json
```

Structure recommandée :

```json
{
  "figures": [
    {
      "figure_id": "straight_gps_r_ax_drift",
      "file": "plots/diagnostics/straight_gps_r_ax_drift.html",
      "figure_type": "residual_drift_over_time",
      "x_axis": "window_center_timestamp",
      "y_axis": "r_ax_rms",
      "filters": {
        "trajectory_shape_label": "straight_gps",
        "speed_bin": "v_40_60",
        "steer_bin": "faible"
      },
      "source_table": "window_quality_index.csv",
      "windows": []
    }
  ]
}
```

Règle importante :

> Aucun indicateur ne doit être interprété comme valeur atypique automatique à ce stade. Il doit être possible de retrouver une visualisation locale permettant de comprendre pourquoi une fenêtre présente une valeur élevée, instable ou atypique.


---

## 14. Résumé du pipeline cible

```text
1. Sélection des canaux
   -> définir les canaux nécessaires à l'analyse

2. Contrôle de propreté minimale
   -> ouverture, présence, temps, durée, valeurs finies

3. Standardisation canonique
   -> source_name, canonical_name, unité SI, repère, convention

4. Qualité univariée locale
   -> NaN, bruit, spikes, zones de zéro, saturation

5. Résidus cinématiques
   -> distance/vitesse, yaw/angle, courbure

6. Résidus d'accélération
   -> ax - dVx/dt, ay - dVy/dt - Vx*r, IMU vs véhicule

7. Résidus GPS
   -> trajectoire GPS vs trajectoire intégrée, vitesse GPS, cap GPS

8. Résidus roues
   -> vitesse roue moyenne, différences roue gauche/droite/avant/arrière

9. Résidus forces
   -> Fx - mAx, Fy - mAy, Fz - mg

10. Résidus de calibration
   -> signe, repère, unité, délai temporel

11. Segmentation / fenêtrage
   -> fenêtres régulières, segments homogènes, timestamp date/heure

12. Structuration globale
   -> speed_bin, lat_acc_bin, long_acc_bin, steer_bin, direction, famille de manœuvre

13. Similarité trajectoire
   -> similarity_group_id

14. Visualisation et traçabilité temporelle
   -> figures de signaux, résidus, indicateurs et dérives par jour/heure/bin

15. Exploitabilité tâche
   -> identification latérale, identification longitudinale, pneus, indicateurs
```

La logique finale est :

> Un fichier est exploitable s'il est techniquement lisible.  
> Une fenêtre est propre si ses signaux sont localement fiables.  
> Une fenêtre est physiquement crédible si ses familles de résidus sont raisonnables.  
> Une fenêtre est comparable si elle appartient à un groupe de trajectoires similaires.  
> Une fenêtre est traçable si elle conserve son timestamp date/heure et ses figures de diagnostic.  
> Une fenêtre est utile si elle excite suffisamment le système pour la tâche visée.

---

## 15. Points à valider expérimentalement

Les éléments suivants doivent être calibrés sur données réelles :

1. seuils de bruit par canal ;
2. seuils de spike par canal ;
3. seuils des bins de direction ;
4. conventions de signe des efforts roue ;
5. convention left/right du yaw rate ;
6. unité réelle des canaux angulaires à unité `_`, notamment `Camber_S1/S2` et `WheelSteer_S1/S2` ;
7. valeur du rayon roue effectif $R$ ;
8. masse véhicule $m$ ;
9. pertinence de $r_{ay}$ versus $r_{ay,simple}$ ;
10. seuils $\tau_j$ des scores de résidus ;
11. seuils d'excitation pour chaque tâche d'identification ;
12. qualité du GPS à basse vitesse ;
13. délai temporel éventuel entre GPS, IMU, bus véhicule et capteurs roue.

---

## 16. Priorité d'implémentation

Priorité recommandée :

```text
P0 — Exploitabilité fichier
P1 — Mapping canonique + conversion unités SI
P2 — Qualité univariée locale : NaN, finite_ratio, bruit, spikes, Vx proche zéro
P3 — Résidus d'accélération : r_ax, r_ay_simple, r_ay
P4 — Résidus cinématiques simples : r_dist, r_yaw si angle disponible
P5 — Résidus GPS : trajectoire intégrée vs GPS, vitesse GPS, cap GPS
P6 — Résidus roues : r_wheel, wheel_diff
P7 — Labels globaux : speed_bin, lat_acc_bin, steer_bin, maneuver_family
P8 — Similarity group ID
P9 — Conservation timestamp absolu date/heure + colonnes temporelles par fenêtre
P10 — Visualisations signaux, résidus, GPS, indicateurs et dérives temporelles
P11 — Agrégations par jour, heure, bins et groupe de trajectoires
P12 — Résidus forces : r_Fx, r_Fy, r_Fz
P13 — Scores d'excitation pour identification
P14 — Rapport automatique par fichier et par groupe de trajectoires similaires
```

---

## 17. Structure de tests `pytest` pour l'implémentation

L'implémentation du pipeline doit être accompagnée d'une suite de tests `pytest`. L'objectif est d'assurer que les sorties numériques, les timestamps, les formats de fichiers et les agrégations restent stables lorsque le code évolue.

La structure recommandée est :

```text
tests/
├── conftest.py
├── fixtures/
│   ├── synthetic_straight_run.json
│   ├── synthetic_lateral_run.json
│   ├── synthetic_missing_channels.json
│   └── expected_window_quality_index.csv
├── test_mapping.py
├── test_timebase.py
├── test_resampling.py
├── test_windowing.py
├── test_residuals.py
├── test_wheel_geometry.py
├── test_gps_geometry.py
├── test_aggregations.py
├── test_output_schema.py
└── test_api_contract.py
```

### 17.1. Tests de mapping canonique

Ces tests vérifient que les noms Dewesoft bruts sont correctement convertis vers les noms canoniques.

Cas à tester :

```text
VelX (km/h)              -> vehicle.vx
VelY (km/h)              -> vehicle.vy
VehYaw_W_Actl (rad/s)    -> vehicle.yaw_rate
Camber_S1 (_)            -> wheel.s1.camber
WheelSteer_S1 (_)        -> wheel.s1.steer
Camber_S2 (_)            -> wheel.s2.camber
WheelSteer_S2 (_)        -> wheel.s2.steer
```

Les tests doivent vérifier :

```text
nom canonique
unité interne
facteur de conversion
statut si unité inconnue
présence du source_name brut
```

### 17.2. Tests de timestamp et base temporelle

Ces tests sont critiques, car les analyses de dérive dépendent du timestamp absolu.

À vérifier :

```text
time_s commence à 0
Delta t est constant après resampling
window_start_timestamp = acquisition_start_timestamp + window_start_sec
window_center_timestamp = acquisition_start_timestamp + window_center_sec
window_date est cohérent avec window_center_timestamp
window_hour est cohérent avec window_center_timestamp
le fuseau horaire est conservé
```

Exemple de test attendu :

```python
from datetime import datetime, timedelta


def test_window_center_timestamp():
    acquisition_start = datetime.fromisoformat("2026-06-14T09:31:12.430+02:00")
    window_center_sec = 15.0
    expected = acquisition_start + timedelta(seconds=window_center_sec)
    assert expected.isoformat() == "2026-06-14T09:31:27.430000+02:00"
```

### 17.3. Tests de fenêtrage

Les tests de fenêtrage doivent vérifier que le nombre de fenêtres, les bornes temporelles et les recouvrements sont corrects.

Pour une acquisition de durée $T$ avec :

```text
window_sec = 10
window_stride_sec = 5
```

on vérifie :

```text
window_0 : 0 -> 10 s
window_1 : 5 -> 15 s
window_2 : 10 -> 20 s
```

Les tests doivent aussi couvrir :

```text
fichier trop court
fenêtre incomplète en fin de fichier
NaN dans une fenêtre
fenêtre avec vitesse quasi nulle
```

### 17.4. Tests de résidus

Chaque résidu doit avoir au moins un test sur données synthétiques simples.

Exemples :

```text
si Ax = dVx/dt, alors r_ax_rms ≈ 0
si Ay = Vx * yaw_rate et Vy absent, alors r_ay_simple_rms ≈ 0
si gps.position correspond à l'intégration de Vx et yaw_rate, alors r_gps_pos_rmse ≈ 0
si Vx = R * omega_mean, alors r_wheel_rms ≈ 0
```

Ces tests doivent utiliser des tolérances explicites :

```python
import numpy as np


def test_r_ax_zero_on_consistent_synthetic_signal():
    assert np.isclose(r_ax_rms, 0.0, atol=1e-8)
```

### 17.5. Tests de géométrie roue S1/S2

Les canaux `WheelSteer` et `Camber` doivent être testés séparément.

Cas minimaux :

```text
S1 = S2                  -> rms_diff ≈ 0, corr ≈ 1
S1 = -S2                 -> corr ≈ -1
S1 = S2 + offset         -> mean_diff ≈ offset
S1 absent, S2 présent    -> consolidated = S2 avec statut single_source
S1 et S2 absents         -> consolidated not_computable_missing_channel
```

Ces tests ne doivent pas conclure à une anomalie ni produire de flag automatique. Ils vérifient seulement que les indicateurs de cohérence sont correctement calculés.

### 17.6. Tests de géométrie GPS

Les tests GPS doivent couvrir :

```text
trajectoire rectiligne synthétique
trajectoire circulaire synthétique
trajectoire avec GPS absent
trajectoire avec GPS bruité
```

Pour une trajectoire rectiligne, on attend :

```text
trajectory_shape_label = straight ou gps_geometry = straight
trajectory_curvature_rms faible
trajectory_straightness_score élevé
```

Pour une trajectoire circulaire, on attend une courbure non nulle et stable.

### 17.7. Tests d'agrégation temporelle

Les agrégations par date, heure et bins doivent être testées avec une petite table de fenêtres connue.

À vérifier :

```text
groupby date
 groupby hour
 groupby speed_bin
 groupby maneuver_family
mean/std/rms calculés correctement
nombre de fenêtres correct
pas de mélange entre deux jours différents
```

Exemple :

```python
def test_daily_aggregation_keeps_days_separate(window_df):
    out = aggregate_by_time_and_bins(window_df, level="day")
    assert set(out["aggregation_date"]) == {"2026-06-14", "2026-06-15"}
```

### 17.8. Tests de schéma de sortie

Les fichiers produits doivent être validés contre un contrat minimal.

À tester :

```text
dataset_index.json contient schema_version, files, created_at
chaque acquisition JSON contient timebase, channels, features
window_quality_index contient les colonnes obligatoires
indicator_time_summary contient les colonnes d'agrégation
trajectory_segments.geojson est un FeatureCollection valide
visualization_manifest.json référence uniquement des sources existantes
```

Les tests doivent échouer si une colonne critique disparaît, notamment :

```text
window_center_timestamp
window_center_date
window_center_hour
speed_bin
maneuver_family
similarity_group_id
r_ax_rms
r_gps_pos_rmse
physical_consistency_score
```

### 17.9. Tests de contrat API pour l'application de visualisation

Si l'application FastAPI est adaptée au nouveau format, les endpoints doivent être testés avec `TestClient`.

Endpoints minimaux à tester :

```text
GET /api/files
GET /api/file/{json_name}/summary
GET /api/file/{json_name}/channels
GET /api/file/{json_name}/series
GET /api/windows
GET /api/indicators/timeseries
GET /api/trajectories/segments
GET /api/visualization/manifest
```

Exemple :

```python
from fastapi.testclient import TestClient


def test_api_windows_returns_items(client: TestClient):
    response = client.get("/api/windows?speed_bin=60_80&gps_geometry=straight")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "filters" in payload
```

### 17.10. Tests de non-régression

Une petite acquisition synthétique de référence doit être conservée dans `tests/fixtures/` avec les sorties attendues.

À chaque modification du pipeline, on vérifie que :

```text
les mêmes fenêtres sont produites
les timestamps restent identiques
les résidus restent dans la tolérance
les bins restent identiques
les fichiers de sortie restent compatibles avec l'application
```

Ces tests permettent d'éviter qu'un changement de code modifie silencieusement les indicateurs ou casse les visualisations.