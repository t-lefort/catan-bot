# Schémas de données — CatanBot 1v1

## Objectifs
- Offrir des structures stables et sérialisables (JSON / MsgPack / NumPy) pour l'état du jeu, les actions et les observations RL.
- Garantir une correspondance 1:1 entre identifiants logiques (tuiles, sommets, arêtes, joueurs) et leur représentation interne.
- Permettre la reprise d'une partie, la comparaison moteur↔simulation et l'entraînement RL à grande échelle.

## Principes généraux
- **Format canonique**: JSON (UTF-8) pour la persistance lisible, MsgPack/NPZ optionnels pour le RL (vectorisation).
- **Versionnement**: chaque snapshot inclut `schema_version` (semver). Incrément mineur pour ajout de champs, majeur pour rupture.
- **IDs stables**: entiers non négatifs, jamais réaffectés. Les entités supprimées restent référencées par leur ID historique dans les logs.
- **Ordre**: toutes les listes sont ordonnées de manière déterministe (tri par ID croissant) pour éviter les diffs inutiles.
- **RNG**: chaque snapshot transporte `rng_state` (pickle `random.Random` ou tuple NumPy) pour assurer la reproductibilité.

## Identifiants

| Entité          | Type        | Domaine                                   | Notes |
|-----------------|-------------|-------------------------------------------|-------|
| `PlayerId`      | `uint8`     | `[0, 1]` (1v1)                            | Index fixe (0 = premier joueur). |
| `TileId`        | `uint8`     | `[0, 18]`                                 | 19 tuiles; mapping axial fixé ci-dessous. |
| `VertexId`      | `uint8`     | `[0, 53]`                                 | 54 sommets; ordre déterminé par (tile, local_vertex). |
| `EdgeId`        | `uint8`     | `[0, 71]`                                 | 72 arêtes; ordre déterminé par (tile, local_edge). |
| `PortId`        | `uint8`     | `[0, 8]`                                  | 9 ports. |
| `ActionId`      | `uint32`    | Monotone croissant                        | Identifiant unique d'action dans un match. |
| `GameId`        | `uuid4`     | RFC 4122                                  | Identifie une partie, utile pour logging. |

### Mapping axial (TileId)

Nous utilisons des coordonnées cube `(x, y, z)` avec contrainte `x + y + z = 0`. L'origine (TileId 0) est centrée sur le désert. Les TileId croissent en spiral (rayons 0 → 2) dans l'ordre horaire en partant du nord-est.

| TileId | Cube `(x,y,z)` | Ressource (setup standard) |
|--------|----------------|----------------------------|
| 0      | (0, 0, 0)      | DESERT (voleur initial)    |
| 1      | (1, -1, 0)     | ORE                        |
| 2      | (1, 0, -1)     | GRAIN                      |
| 3      | (0, 1, -1)     | WOOL                       |
| 4      | (-1, 1, 0)     | BRICK                      |
| 5      | (-1, 0, 1)     | LUMBER                     |
| 6      | (0, -1, 1)     | GRAIN                      |
| 7      | (2, -1, -1)    | LUMBER                     |
| 8      | (2, 0, -2)     | BRICK                      |
| 9      | (1, 1, -2)     | WOOL                       |
| 10     | (0, 2, -2)     | ORE                        |
| 11     | (-1, 2, -1)    | GRAIN                      |
| 12     | (-2, 2, 0)     | LUMBER                     |
| 13     | (-2, 1, 1)     | BRICK                      |
| 14     | (-2, 0, 2)     | WOOL                       |
| 15     | (-1, -1, 2)    | LUMBER                     |
| 16     | (0, -2, 2)     | GRAIN                      |
| 17     | (1, -2, 1)     | WOOL                       |
| 18     | (2, -2, 0)     | ORE                        |

*Remarque*: la distribution des ressources est celle du setup de référence (peut être randomisée via `rng_state`). Les numéros de dés (`pip_number`) sont stockés dans `BoardLayout`.

### VertexId et EdgeId
- Les sommets sont identifiés par des coordonnées cube triples `(x, y, z, direction)` dérivées du centre de tuile et d'une orientation. Un pré-calcul unique liste tous les sommets possibles, les trie lexicographiquement et assigne `VertexId` de 0 à 53.  
  (Implémentation prévue dans `ENG-001`: génération + cache `vertex_coordinate -> vertex_id`).
- Les arêtes sont identifiées par la paire ordonnée de sommets `(vertex_a, vertex_b)` avec `vertex_a < vertex_b`. Le même pré-calcul génère la table `edge_coordinate -> edge_id` (0 à 71).
- `PortId` référence une arête (`edge_id`) ainsi que le type (`["ANY", "BRICK", "LUMBER", "WOOL", "GRAIN", "ORE"]`).

## Structures sérialisées

### StateSnapshot

```json
{
  "schema_version": "0.1.0",
  "game_id": "7e3a2c2c-9a1f-4c4a-8d8a-1ef6adf1b4c3",
  "variant": {"vp_to_win": 15, "discard_threshold": 9},
  "rng_state": {"type": "py_random", "state": [3, [2147483648, ...], 0]},
  "turn": {
    "number": 12,
    "phase": "ACTION",
    "current_player": 1,
    "dice": {"last_roll": [3, 4], "robber_triggered": false}
  },
  "board": {
    "tiles": [
      {"tile_id": 0, "resource": "DESERT", "pip_number": null, "has_robber": true},
      {"tile_id": 1, "resource": "ORE", "pip_number": 5, "has_robber": false}
      ...
    ],
    "ports": [
      {"port_id": 0, "edge_id": 5, "type": "ANY"},
      {"port_id": 1, "edge_id": 12, "type": "BRICK"}
    ]
  },
  "players": [
    {
      "player_id": 0,
      "name": "Blue",
      "victory_points": 7,
      "hidden_victory_points": 1,
      "resources": {"BRICK": 1, "LUMBER": 0, "WOOL": 2, "GRAIN": 3, "ORE": 0},
      "dev_cards": {
        "KNIGHT": 1,
        "ROAD_BUILDING": 0,
        "YEAR_OF_PLENTY": 0,
        "MONOPOLY": 0,
        "VICTORY_POINT": 0
      },
      "new_dev_cards": {
        "KNIGHT": 0,
        "ROAD_BUILDING": 0,
        "YEAR_OF_PLENTY": 0,
        "MONOPOLY": 0,
        "VICTORY_POINT": 0
      },
      "settlements": [12, 23],
      "cities": [45],
      "roads": [5, 18, 19],
      "longest_road_len": 3,
      "largest_army_size": 1,
      "played_dev_cards": {
        "KNIGHT": 1,
        "ROAD_BUILDING": 0,
        "YEAR_OF_PLENTY": 0,
        "MONOPOLY": 0
      }
    },
    {
      "player_id": 1,
      "name": "Orange",
      "victory_points": 6,
      "hidden_victory_points": 2,
      "resources": {"BRICK": 0, "LUMBER": 2, "WOOL": 0, "GRAIN": 1, "ORE": 2},
      "dev_cards": {
        "KNIGHT": 0,
        "ROAD_BUILDING": 1,
        "YEAR_OF_PLENTY": 0,
        "MONOPOLY": 0,
        "VICTORY_POINT": 0
      },
      "new_dev_cards": {
        "KNIGHT": 0,
        "ROAD_BUILDING": 0,
        "YEAR_OF_PLENTY": 0,
        "MONOPOLY": 0,
        "VICTORY_POINT": 1
      },
      "settlements": [34, 41],
      "cities": [],
      "roads": [9, 10],
      "longest_road_len": 2,
      "largest_army_size": 0,
      "played_dev_cards": {
        "KNIGHT": 0,
        "ROAD_BUILDING": 0,
        "YEAR_OF_PLENTY": 0,
        "MONOPOLY": 0
      }
    }
  ],
  "bank": {
    "resources": {"BRICK": 18, "LUMBER": 16, "WOOL": 17, "GRAIN": 15, "ORE": 18},
    "dev_deck": ["KNIGHT", "VICTORY_POINT", "ROAD_BUILDING", ...]
  },
  "discard_pile": {"dev_cards": []},
  "log": [
    {"action_id": 23, "type": "BUILD_ROAD", "player_id": 0, "payload": {"edge_id": 19}}
  ]
}
```

### ActionRecord

```json
{
  "schema_version": "0.1.0",
  "game_id": "7e3a2c2c-9a1f-4c4a-8d8a-1ef6adf1b4c3",
  "action_id": 27,
  "turn_number": 12,
  "player_id": 1,
  "type": "BUILD_SETTLEMENT",
  "payload": {
    "vertex_id": 34,
    "pay_with": {"BRICK": 1, "LUMBER": 1, "WOOL": 1, "GRAIN": 1},
    "free": false
  },
  "result": {
    "state_hash": "sha256:e8d5...",
    "events": ["VICTORY_POINTS_UPDATED", "SETTLEMENT_PLACED"]
  },
  "timestamp_utc": "2025-10-17T20:41:00Z"
}
```

`type` est une enum fermée. Proposition d'encodage:

| Action type            | Payload                                                           |
|------------------------|-------------------------------------------------------------------|
| `ROLL_DICE`            | `{"forced_value": [d1, d2]?}` (optionnel pour tests)              |
| `MOVE_ROBBER`          | `{"tile_id": int, "steal_from": PlayerId?}`                       |
| `BUILD_ROAD`           | `{"edge_id": int, "free": bool}`                                  |
| `BUILD_SETTLEMENT`     | `{"vertex_id": int, "free": bool}`                                |
| `BUILD_CITY`           | `{"vertex_id": int}`                                              |
| `BUY_DEVELOPMENT`      | `{}`                                                              |
| `PLAY_KNIGHT`          | `{"tile_id": int, "steal_from": PlayerId?}`                       |
| `PLAY_PROGRESS`        | `{"card": "ROAD_BUILDING"|"YEAR_OF_PLENTY"|"MONOPOLY", ...}`       |
| `TRADE_BANK`           | `{"give": {"resource": int}, "receive": {"resource": int}}`       |
| `TRADE_PORT`           | `{"port_id": int, "give": {...}, "receive": {...}}`               |
| `TRADE_PLAYER`         | `{"partner": PlayerId, "offer": {...}, "request": {...}}`         |
| `END_TURN`             | `{}`                                                              |
| `SETUP_PLACE_SETTLEMENT` | `{"vertex_id": int, "turn": 1|2}`                               |
| `SETUP_PLACE_ROAD`     | `{"edge_id": int, "turn": 1|2}`                                   |

Pour `PLAY_PROGRESS`, le contenu du payload dépend de la carte:
- `ROAD_BUILDING`: `{"card": "...", "edges": [edge_id1, edge_id2]}` — deux routes gratuites adjointes au réseau du joueur.
- `YEAR_OF_PLENTY`: `{"card": "...", "resources": {"WOOL": 1, "ORE": 1}}` — deux ressources prélevées sur la banque.
- `MONOPOLY`: `{"card": "...", "resource": "GRAIN"}` — collecte toutes les ressources ciblées chez l’adversaire.

Les cartes `VICTORY_POINT` n'ont pas d'action dédiée: elles sont comptabilisées automatiquement dans `hidden_victory_points` au moment de l'achat.

### ObservationTensor (RL)

- `board`: tensor `(19, 6)` : one-hot ressource + pip number normalisé.
- `roads`: tensor `(72,)` : -1 si libre, 0 joueur 0, 1 joueur 1.
- `settlements`: `(54,)` : -1 libre, 0 colonie j0, 1 colonie j1, 2 ville j0, 3 ville j1.
- `hands`: `(2, 5)` : compte de ressources / 19.
- `dev`: `(2, 5)` : comptes normalisés.
- `bank`: `(5,)` : ressources restantes / 19.
- `metadata`: `(10,)` : joueur courant, VP, longest road owner, largest army owner, total cartes, etc.
- `legal_actions_mask`: `(N_ACTIONS,)` aligné sur l'ordre `Action type` ci-dessus, booléen.

Les conversions `StateSnapshot -> ObservationTensor` et inversement doivent être exactes et documentées dans le code (`catan.rl.features`).

## Sérialisation & hashing

- `state_hash` utilise SHA-256 sur la sérialisation canonique JSON triée (`sort_keys=True`).
- Les snapshots persistés incluent `compressed`: booléen indiquant si MsgPack/NPZ a été utilisé.
- `ActionRecord.result.events` suit les constantes déclarées dans `catan.app.events`.

## Validation & tests

- Tests contrats (TEST-001+) vérifieront:
  - l'existence des structures `StateSnapshot`, `ActionRecord`.
  - la présence des IDs stables (tile/vertex/edge).
  - la cohérence `serialize(State) -> deserialize -> State`.
- Tests property-based (TEST-002) assureront:
  - qu'aucun ID n'est perdu/dupliqué lors de la sérialisation.
  - que les seeds RNG sont restaurées correctement.
- Les schémas JSON pourront être validés via `pydantic`/`jsonschema` (TODO).

## Synchronisation avec l'implémentation

- Tout changement dans les modules `catan.engine.serialize`, `catan.sim.runner`, `catan.rl.features` nécessite une mise à jour simultanée de ce document et un bump `schema_version`.
- `docs/architecture.md` décrit l'emplacement des modules; cette page en est le complément structuré.
- `external/catanatron` peut servir de référence de validation, mais sans réutilisation de ses IDs (mapping explicite requis).
