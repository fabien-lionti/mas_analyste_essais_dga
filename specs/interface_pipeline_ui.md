# Spécification — Interface Pipeline configurable

## Objectif

L'interface web doit permettre de piloter le cycle complet du pipeline sans
passer par le terminal :

```text
choisir les donnees DXD
-> configurer les chemins, le resampling et les canaux
-> scanner / convertir les DXD
-> extraire les features
-> mettre a jour SQLite
-> annoter
-> entrainer les modeles conserves
-> explorer les resultats
```

Le terminal reste utile pour le developpement et le debug, mais ne doit pas etre
necessaire pour une utilisation normale de l'outil.

## Principe structurant : acquisition et mapping de canaux

Le pipeline ne doit pas partir directement d'une liste de canaux codee en dur.
Il doit d'abord gerer une notion d'`acquisition`.

Une acquisition represente un ensemble de fichiers `.dxd` appartenant au meme
contexte d'essai ou au meme dossier source. L'utilisateur doit pouvoir :

1. choisir ou changer le dossier d'acquisition DXD ;
2. demander au backend d'ouvrir un ou plusieurs `.dxd` ;
3. recuperer la liste des canaux reellement disponibles dans ces fichiers ;
4. choisir les canaux utiles ;
5. leur associer un nom canonique utilise par le reste de l'application ;
6. sauvegarder ce mapping de facon permanente.

Le mapping sauvegarde devient ensuite la source de verite pour le resampling,
l'extraction de features, l'annotation, l'entrainement et l'exploration.

## Navigation

Ajouter un onglet principal `Pipeline` dans la navigation existante :

```text
Explorer | Validite | Drift / Coherence | Annotateur | Pipeline
```

L'onglet `Pipeline` doit etre une console operationnelle, pas une page de
documentation.

## Structure UI

### 1. Bandeau d'etat

Un bandeau en haut de la page resume l'etat courant :

```text
Etat pipeline : pret / en cours / erreur / termine
Dernier run : date, duree, etape
Base SQLite : prete / absente / erreur
DXD : nombre de fichiers detectes
JSON resamples : nombre de fichiers disponibles
```

Actions rapides :

- `Previsualiser`
- `Relancer tout`
- `Arreter`
- `Ouvrir logs`

### 2. Configuration

Un panneau de configuration regroupe les parametres persistants.

#### Donnees

- dossier des fichiers `.dxd` bruts ;
- acquisition active ;
- creation / selection / suppression d'une acquisition ;
- dossier de sortie des JSON resamples ;
- chemin de la base SQLite ;
- dossier des annotations ;
- dossier des runs de modeles.

#### Resampling

- frequence cible, par defaut `20 Hz` ;
- limite optionnelle du nombre de fichiers pour les essais rapides ;
- politique en cas de canal manquant ;
- strategie d'alignement / interpolation si elle est configurable.

#### Canaux

- bouton `Lire les canaux disponibles` depuis les fichiers `.dxd` ;
- liste des canaux bruts detectes ;
- selection des canaux a conserver ;
- proposition automatique d'un nom canonique ;
- edition manuelle du nom canonique ;
- type de canal : `requis`, `optionnel`, `ignore` ;
- unite detectee si disponible ;
- unite cible si une conversion est appliquee ;
- statut de presence par fichier ou par echantillon ;
- sauvegarde permanente du mapping.

Exemple de table UI :

```text
Canal brut DXD                         Nom canonique      Type       Unite   Statut
AI Front Wheel Speed Left              wheel_speed_fl     requis     rad/s   present
Vehicle Speed                          vehicle.vx         requis     m/s     present
Steering Angle Sensor 1                steer_s1           requis     deg     present
Steering Angle Sensor 2                steer_s2           optionnel  deg     absent sur 3 fichiers
```

Le nom canonique doit etre propose automatiquement lorsque le canal brut est
reconnu, mais l'utilisateur doit pouvoir le modifier. Une fois sauvegarde, le
choix doit rester stable pour l'acquisition.

#### Modeles

- activation de l'entrainement CNN ;
- activation de l'entrainement drift / coherence ;
- parametres courts : `epochs`, `window_sec`, `stride_sec`, `batch_size`.

La configuration doit etre sauvegardee explicitement via un bouton
`Enregistrer configuration`.

### 3. Etapes du pipeline

La zone centrale presente un workflow lineaire :

```text
1. Scanner DXD
   Entree : dossier DXD
   Sortie : channel_presence.csv + JSON resamples

2. Extraire features
   Entree : JSON resamples
   Sortie : index et agregats de features

3. Mettre a jour SQLite
   Entree : CSV/JSON generes
   Sortie : pipeline.sqlite

4. Entrainer CNN
   Entree : annotations
   Sortie : modele segment_cnn

5. Entrainer drift / coherence
   Entree : JSON resamples
   Sortie : run dynamic_channel_coherence_*
```

Chaque etape affiche :

- statut : `a lancer`, `en cours`, `termine`, `erreur` ;
- derniere duree ;
- date du dernier succes ;
- chemin des sorties ;
- bouton `Lancer` ;
- bouton `Details`.

Une action `Relancer tout` execute les etapes dans l'ordre, en s'arretant au
premier echec.

### 4. Logs et details

Un panneau lateral ou inferieur affiche :

- logs du job courant ;
- progression ;
- commande effective construite par le backend ;
- fichiers generes ;
- erreur courte et erreur complete.

Prevoir des onglets internes :

```text
Logs | Resume | Artefacts
```

## Responsive

Sur desktop, la page peut utiliser trois colonnes :

```text
Configuration | Etapes du pipeline | Logs
```

Sur mobile ou petit ecran, utiliser des onglets internes :

```text
Config | Etapes | Logs
```

## Configuration persistante

Ajouter un fichier de configuration persistant :

```text
config/pipeline.json
```

Exemple :

```json
{
  "raw_dxd_dir": "data",
  "resampled_json_dir": "selected_dxd_json_resampled",
  "sqlite_path": "pipeline.sqlite",
  "annotations_dir": "manual_segment_annotations",
  "sample_hz": 20.0,
  "max_files": null,
  "channels": {
    "required": [
      "vehicle.vx",
      "vehicle.vy",
      "vehicle.ax",
      "vehicle.ay",
      "vehicle.yaw_rate",
      "steer_s1",
      "steer_s2"
    ],
    "optional": []
  },
  "models": {
    "segment_cnn": {
      "enabled": true,
      "epochs": 40,
      "window_sec": 4.0,
      "stride_sec": 1.0,
      "batch_size": 32
    },
    "drift_coherence": {
      "enabled": true,
      "history_sec": 4.0,
      "horizon_sec": 1.0,
      "stride_sec": 0.5
    }
  }
}
```

Les chemins relatifs sont resolus depuis la racine du projet.

## Structure de donnees acquisition

Ajouter un fichier persistant par acquisition, par exemple :

```text
config/acquisitions.json
```

Structure proposee :

```json
{
  "active_acquisition_id": "essais_avril_2025",
  "acquisitions": [
    {
      "id": "essais_avril_2025",
      "label": "Essais avril 2025",
      "raw_dxd_dir": "data",
      "resampled_json_dir": "selected_dxd_json_resampled",
      "sqlite_path": "pipeline.sqlite",
      "created_at": "2026-07-20T00:00:00Z",
      "updated_at": "2026-07-20T00:00:00Z",
      "last_channel_scan": {
        "status": "ok",
        "sampled_files": 10,
        "total_files": 248,
        "channels_detected": 126,
        "missing_required_channels": []
      },
      "channel_mapping": [
        {
          "raw_name": "Vehicle Speed",
          "canonical_name": "vehicle.vx",
          "role": "required",
          "source_unit": "km/h",
          "target_unit": "m/s",
          "conversion": "kmh_to_mps",
          "enabled": true
        },
        {
          "raw_name": "Steering Angle Sensor 1",
          "canonical_name": "steer_s1",
          "role": "required",
          "source_unit": "deg",
          "target_unit": "deg",
          "conversion": null,
          "enabled": true
        }
      ]
    }
  ]
}
```

Cette structure doit permettre de changer d'acquisition sans perdre les choix de
canaux deja faits sur les autres acquisitions.

## Scan des canaux DXD

Avant tout resampling, l'utilisateur doit pouvoir lancer une etape de scan :

```text
1. choisir acquisition / dossier DXD ;
2. ouvrir un echantillon ou tous les fichiers `.dxd` ;
3. extraire la liste des canaux disponibles ;
4. agreger les presences par canal ;
5. proposer un mapping par defaut ;
6. laisser l'utilisateur valider ou corriger ;
7. sauvegarder le mapping.
```

Le scan doit produire une structure exploitable par l'UI :

```json
{
  "acquisition_id": "essais_avril_2025",
  "files": [
    {
      "file": "angle_braquage_2025_04_14_0001.dxd",
      "can_open": true,
      "channel_count": 126
    }
  ],
  "channels": [
    {
      "raw_name": "Vehicle Speed",
      "suggested_canonical_name": "vehicle.vx",
      "unit": "km/h",
      "present_files": 248,
      "missing_files": 0
    }
  ]
}
```

Le scan ne modifie pas les donnees resamplees. Il ne fait que lire les DXD et
preparer le choix utilisateur.

## Mode acquisition live

L'interface doit pouvoir surveiller une acquisition pendant des essais en cours.
Lorsque de nouveaux fichiers `.dxd` sont ajoutes dans le dossier de
l'acquisition active, le systeme doit pouvoir les detecter et mettre a jour les
artefacts de maniere incrementale.

### Objectif

Le mode live doit permettre :

```text
nouveau .dxd detecte
-> attendre que le fichier soit stable
-> ouvrir le fichier
-> verifier les canaux selon le mapping sauvegarde
-> resampler uniquement ce nouveau fichier
-> mettre a jour les index / SQLite
-> rafraichir l'UI
```

Le traitement live ne doit pas relancer tout le pipeline si seuls quelques
fichiers ont ete ajoutes.

### Configuration UI

Ajouter une section `Surveillance live` dans l'onglet `Pipeline` :

- interrupteur `Surveiller le dossier DXD` ;
- intervalle de detection, par exemple `5 s`, `10 s`, `30 s` ;
- delai de stabilisation fichier, par exemple `30 s` sans changement de taille ;
- option `Traiter automatiquement les nouveaux fichiers` ;
- option `Mettre a jour SQLite automatiquement` ;
- option `Notifier uniquement, sans lancer le traitement` ;
- dernier fichier detecte ;
- file d'attente des fichiers a traiter ;
- erreurs recentes.

### Detection des fichiers

Un fichier `.dxd` est considere nouveau s'il :

- est present dans le dossier DXD de l'acquisition active ;
- n'est pas encore reference dans l'index de l'acquisition ;
- n'a pas encore de JSON resample associe ;
- n'est pas deja en cours de traitement.

Un fichier est considere stable si :

- sa taille ne change plus pendant le delai de stabilisation ;
- sa date de modification ne change plus pendant le delai de stabilisation ;
- il peut etre ouvert par le lecteur DXD sans erreur bloquante.

### Traitement incremental

Pour chaque nouveau fichier stable :

1. lire les metadonnees du `.dxd` ;
2. verifier la presence des canaux requis du mapping ;
3. produire le JSON resample uniquement pour ce fichier ;
4. extraire les features uniquement pour ce fichier ;
5. mettre a jour les tables SQLite concernees ;
6. mettre a jour le catalogue de fichiers ;
7. signaler le resultat dans l'UI.

Le traitement doit etre idempotent : si le meme fichier est redetecte, le
backend doit savoir s'il est deja traite ou si une regeneration est necessaire.

### Etats possibles d'un fichier live

```text
detected
waiting_for_stability
ready
processing
processed
skipped
error
```

Chaque entree doit conserver :

- nom du fichier ;
- taille ;
- date de modification ;
- statut ;
- message d'erreur court ;
- date de detection ;
- date de traitement ;
- chemin du JSON genere ;
- statut SQLite.

### Structure persistante

Ajouter un etat live par acquisition :

```json
{
  "acquisition_id": "essais_avril_2025",
  "watch": {
    "enabled": true,
    "poll_interval_sec": 10,
    "stability_delay_sec": 30,
    "auto_process": true,
    "auto_update_sqlite": true
  },
  "files": [
    {
      "file": "nouvel_essai_0001.dxd",
      "status": "processed",
      "size_bytes": 123456789,
      "modified_at": "2026-07-20T10:15:00Z",
      "detected_at": "2026-07-20T10:15:10Z",
      "processed_at": "2026-07-20T10:16:02Z",
      "json_name": "nouvel_essai_0001.json",
      "sqlite_status": "updated",
      "error": null
    }
  ]
}
```

Cet etat peut etre stocke dans :

```text
config/acquisition_live_state.json
```

ou dans SQLite si la base devient la source de verite operationnelle.

## Backend propose

Ajouter un module :

```text
src/mas_essais/pipeline/
  __init__.py
  acquisitions.py
  config.py
  jobs.py
  watcher.py
  runners.py
```

Responsabilites :

- `acquisitions.py` : gerer les acquisitions, le scan de canaux et le mapping ;
- `config.py` : charger, valider et sauvegarder `config/pipeline.json` ;
- `jobs.py` : gerer l'etat d'un job, les logs et le verrou d'execution ;
- `watcher.py` : detecter les nouveaux DXD et gerer la file live ;
- `runners.py` : construire et lancer les scripts autorises.

## Endpoints API

```text
GET  /api/pipeline/config
PUT  /api/pipeline/config
GET  /api/pipeline/preview

GET  /api/pipeline/acquisitions
POST /api/pipeline/acquisitions
GET  /api/pipeline/acquisitions/{acquisition_id}
PUT  /api/pipeline/acquisitions/{acquisition_id}
POST /api/pipeline/acquisitions/{acquisition_id}/activate
POST /api/pipeline/acquisitions/{acquisition_id}/scan-channels
PUT  /api/pipeline/acquisitions/{acquisition_id}/channel-mapping

GET  /api/pipeline/live/status
PUT  /api/pipeline/live/config
POST /api/pipeline/live/start
POST /api/pipeline/live/stop
POST /api/pipeline/live/scan-now
POST /api/pipeline/live/process-queue

POST /api/pipeline/run/scan
POST /api/pipeline/run/features
POST /api/pipeline/run/sqlite
POST /api/pipeline/run/train-cnn
POST /api/pipeline/run/train-drift
POST /api/pipeline/run/all

GET  /api/pipeline/job
GET  /api/pipeline/log
POST /api/pipeline/job/stop
```

Les commandes ne doivent jamais etre envoyees directement par le frontend. Le
frontend choisit une action, puis le backend construit la commande a partir de
la configuration validee.

## Scripts a adapter

Les scripts doivent accepter explicitement les parametres configures :

```bash
python scripts/scan_dxd_channel_presence.py \
  --input-dir data \
  --output-dir selected_dxd_json_resampled \
  --sample-hz 20 \
  --channel-mapping config/acquisitions.json \
  --acquisition-id essais_avril_2025

python scripts/extract_features.py \
  --input-dir selected_dxd_json_resampled

python scripts/migrate_pipeline_to_sqlite.py \
  --db pipeline.sqlite

python scripts/train_segment_cnn.py \
  --window-sec 4.0 \
  --stride-sec 1.0 \
  --epochs 40

python scripts/train_drift_coherence.py \
  --input-dir selected_dxd_json_resampled \
  --output-dir dynamic_channel_coherence_app_run
```

## Garde-fous

L'interface doit etre volontairement limitee :

- un seul job actif a la fois ;
- interdiction de lancer une commande arbitraire ;
- validation des chemins avant sauvegarde ;
- impossibilite de lancer le resampling sans mapping de canaux valide ;
- avertissement si des canaux requis sont absents d'une partie des fichiers ;
- ne jamais traiter un fichier `.dxd` tant qu'il est encore en cours d'ecriture ;
- ne jamais lancer deux traitements live en parallele sur le meme fichier ;
- journaliser les fichiers ignores et les raisons ;
- confirmation avant ecrasement de sorties existantes ;
- affichage du nombre de fichiers impactes avant lancement ;
- logs persistants ;
- statut robuste en cas de crash ou d'interruption ;
- bouton `Arreter` si le processus peut etre interrompu proprement ;
- erreurs lisibles sans masquer le traceback complet disponible dans les logs.

## Critères d'acceptation

La fonctionnalite est acceptable si :

1. l'utilisateur peut configurer les chemins principaux depuis l'UI ;
2. l'utilisateur peut creer, selectionner et changer d'acquisition ;
3. l'utilisateur peut scanner un dossier DXD et obtenir la liste des canaux ;
4. l'utilisateur peut choisir les canaux et modifier leur nom canonique ;
5. le mapping de canaux reste persistant par acquisition ;
6. l'utilisateur peut configurer la frequence de resampling ;
7. l'utilisateur peut previsualiser les fichiers detectes avant execution ;
8. l'utilisateur peut activer ou desactiver la surveillance live ;
9. un nouveau `.dxd` ajoute au dossier est detecte automatiquement ;
10. un fichier detecte n'est traite qu'une fois stable ;
11. chaque etape du pipeline peut etre lancee depuis l'UI ;
12. l'UI affiche le statut et les logs du job courant ;
13. un deuxieme job ne peut pas etre lance pendant qu'un premier est actif ;
14. les scripts restent lancables depuis le terminal ;
15. les commandes executees sont construites cote backend a partir de la config ;
16. aucun chemin dangereux ou invalide n'est accepte silencieusement ;
17. apres mise a jour SQLite, les vues existantes utilisent les nouvelles donnees.
