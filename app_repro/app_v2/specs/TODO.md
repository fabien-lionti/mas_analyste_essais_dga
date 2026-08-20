# TODO - Modele capteurs

## Objectif

Ajouter plus tard une couche metier "capteurs" au-dessus des canaux DXD.

L'objectif n'est pas seulement d'associer un nom de capteur a un canal, mais de
distinguer :

- le capteur comme objet transverse reutilisable entre plusieurs campagnes ;
- l'utilisation de ce capteur dans une campagne donnee ;
- le mapping entre cette utilisation et les canaux DXD de la campagne.

## Principe metier

Un capteur et ses proprietes existent independamment d'une campagne d'essais.

En revanche, pour une campagne donnee :

- le capteur peut etre monte a une position particuliere sur le vehicule ;
- son montage peut changer ;
- les canaux DXD associes peuvent changer ;
- certains canaux peuvent rester sans capteur associe.

## Modele relationnel propose

### `sensors`

Catalogue transverse des capteurs connus.

Champs pressentis :

- `sensor_id`
- `name`
- `sensor_type`
- `manufacturer`
- `model`
- `serial_number`
- `description`
- `metadata_json`
- `created_at`
- `updated_at`

### `analysis_sensors`

Capteurs utilises dans une campagne.

Champs pressentis :

- `analysis_sensor_id`
- `analysis_id`
- `sensor_id`
- `vehicle_position`
- `mounting_description`
- `metadata_json`
- `created_at`
- `updated_at`

### `analysis_sensor_channels`

Association entre un capteur utilise dans une campagne et les canaux DXD de
cette campagne.

Champs pressentis :

- `analysis_sensor_channel_id`
- `analysis_sensor_id`
- `analysis_id`
- `canonical_channel_name`
- `dxd_channel_name`
- `unit`
- `metadata_json`
- `created_at`

## Relations

```text
sensors
  1 -> n analysis_sensors

analyses
  1 -> n analysis_sensors

analysis_sensors
  1 -> n analysis_sensor_channels

analysis_sensor_channels
  n -> canaux DXD disponibles dans channel_inventory / channel_presence
```

## Integration UI future

### Catalogue capteurs

Ajouter une vue ou un sous-onglet permettant de :

- lister les capteurs connus ;
- ajouter un capteur ;
- modifier ses proprietes ;
- supprimer un capteur si non utilise ;
- consulter les campagnes ou il est utilise.

### Workflow `Creer une campagne`

Dans le workflow de creation de campagne, apres `Canaux DXD`, prevoir une etape
`Capteurs` permettant de :

- choisir les capteurs utilises dans la campagne ;
- definir leur position sur le vehicule ;
- associer les canaux DXD selectionnes aux capteurs ;
- laisser certains canaux sans capteur si necessaire.

## Exemple

```text
Capteur catalogue:
  IMU Xsens MTi-300

Campagne A:
  IMU Xsens MTi-300
    position vehicule: centre
    canaux DXD:
      - vehicle.ax
      - vehicle.ay
      - vehicle.az

Campagne B:
  IMU Xsens MTi-300
    position vehicule: arriere
    canaux DXD:
      - imu_rear.ax
      - imu_rear.ay
      - imu_rear.az
```

## Points a clarifier avant implementation

- La position vehicule doit-elle etre libre ou issue d'une liste controlee ?
- Un meme capteur physique peut-il etre utilise plusieurs fois dans une meme
  campagne ?
- Faut-il gerer les numeros de serie des capteurs ou seulement les types/modeles ?
- Faut-il distinguer capteur physique, type de capteur et voie de mesure ?
- L'association capteur/canal doit-elle etre obligatoire pour les canaux
  selectionnes ?
