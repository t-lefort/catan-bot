# Architecture — CatanBot 1v1

## Vue d'ensemble
- Objectif: séparer clairement le moteur de jeu (règles 1v1), la simulation headless massivement parallélisable, la GUI H2H et la pile RL.
- Principes: moteur pur Python sans dépendance UI, données sérialisables, RNG seedable, évènements observables, dépendances unidirectionnelles (GUI/RL → services → engine).
- Licence: réimplémentation inspirée de catanatron (cf. `docs/catanatron-study.md`), aucun code GPL réutilisé.

```
           +-------------------+     +------------------+
           |   catan.gui.h2h   |     |   catan.rl.*     |
           +----------+--------+     +---------+--------+
                      |                        |
                      v                        v
               +-------------+       +------------------+
               | catan.app.* |<----->| catan.sim.runner |
               +------+------+       +------------------+
                      |
                      v
            +-----------------------+
            |    catan.engine.*     |
            +----------+------------+
                       |
                       v
            +-----------------------+
            |  catan.shared.utils   |
            +-----------------------+
```

## Modules et responsabilités

### catan.engine
- `board`: topologie hexagonale (19 tuiles, 54 sommets, 72 arêtes), ports, coordonnées cube.
- `state`: état complet immuable (ou semi-immuable) décrivant joueurs, banque, défausse, decks dev, position du voleur, logs d'évènements.
- `actions`: types d'actions (enum + payload dataclasses) et validateurs.
- `rules`: constantes (coûts, VP, seuils) et logique de vérification.
- `reducers`: fonctions pures transformant l'état selon une action légale (TDD visé).
- `serialize`: encodage/decodage compact (structures JSON-friendly + buffers numpy optionnels).
- `rng`: générateur seedable (wrapping `random.Random`/`numpy Generator`).
- `metrics`: calcul des titres (longest road, largest army) et VP.

### catan.app (services de jeu)
- `GameService`: oriente le déroulement d'une partie (setup serpent, tours, fin de partie).
- `EventBus`: notifie GUI, simulation et observateurs RL.
- `CommandBus` / `ActionQueue`: pipeline pour les actions utilisateur/bot, gère validations.
- `Persistence`: snapshots (sauvegarde/reprise) via sérialisation engine.
- `ScenarioLoader`: charge des scénarios pré-scriptés (tests, replays).

### catan.sim
- `runner`: boucle headless orchestrant des matchs (self-play ou vs policy).
- `policies`: interface `AgentPolicy` minimale (expose `select_action(state)`).
- `schedulers`: planification des seeds, nombre de parties, collecte de métriques.
- `rollout_buffer`: stockage des trajectoires (pour RL, benchmarks).
- `instrumentation`: hooks perf (jeux/s, latence par action).

### catan.gui
- `h2h`: interface 1v1, connectée via `GameService`.
- `widgets`: représentation plateau, mains, ports; écoute les évènements de l'EventBus.
- `controllers`: mappe les interactions utilisateur -> actions engine.
- `replay`: visualisation d'une partie enregistrée.

### catan.rl
- `env`: enveloppe Gym-like (ou PettingZoo) autour de `GameService`.
- `algorithms`: implémentations RL (PPO initialement, plug-in pour d'autres).
- `training`: orchestration entrainement (scheduler, checkpoints, evaluation loop).
- `features`: extraction d'observations (tensorisation state).
- `evaluation`: match vs heuristiques, logging TensorBoard/live dashboard.

### catan.shared
- `utils`: helpers communs (chrono, seed, random).
- `config`: configuration hiérarchique (YAML/pyproject) pour aligner engine/sim/RL.
- `logging`: configuration structurée (JSON logs, instrumentation).
- `types`: alias dataclasses/TypedDict utilisés cross layers.

## Flux principaux

1. **Setup** (DOC-005 ↔ ENG-002)  
   `GameService` crée un `State` initial via `Board.standard()`, orchestre le placement serpent en validant chaque action via `engine.actions`.

2. **Tour de jeu**  
   - `GameService` déclenche `RollDice`, `engine.reducers` distribue les ressources (tenue par `state`).
   - Actions validées par `engine.actions.validate`.
   - `EventBus` publie `TurnStarted`, `ActionApplied`, `TurnEnded` pour GUI/sim/RL.

3. **Simulation headless**  
   - `catan.sim.runner` instancie des `AgentPolicy` (bots heuristiques ou RL) et consomme l'API `GameService`.
   - Les trajectoires sont sérialisées via `engine.serialize` pour stockage/analyse.

4. **Entraînement RL**  
   - `catan.rl.env` enveloppe `GameService` pour produire observations/récompenses.
   - `training` orchestre N simulations en parallèle (multiprocessing ou asyncio), stockées dans `rollout_buffer`, puis passées aux `algorithms`.
   - `evaluation` relance des matchs vs baseline et renvoie des métriques (winrate, VP moyens).

5. **GUI H2H**  
   - La GUI écoute `EventBus` pour rafraîchir l'état local, et publie des commandes utilisateur vers `ActionQueue`.
   - Support du replay: lecture d'un log d'actions via `engine.serialize` -> refeed `GameService`.

## Points d'extension

- `AgentPolicy` (simulation/RL): interface stable pour brancher des bots (heuristiques, RL, humains via CLI).
- `EventBus` observateurs: possibilité d'ajouter des trackers (statistiques, analytics, streaming) sans modifier le moteur.
- `ScenarioLoader`: injection de scénarios/datasets externes (benchmarks, puzzles).
- `Serializer`: plug pour différents formats (JSON, msgpack, numpy) selon besoins RL/perf.
- `GUI Theme/Renderer`: interchangeabilité (Qt, web, textual) tant que l'on parle au même `GameService`.
- `Metrics` hooks: instrumentation custom (longest-road recalcul, fairness checks).

## Contraintes techniques

- **Déterminisme**: toute fonction dans `engine` doit être pure/déterministe (seed transmise explicitement).
- **Thread safety**: `GameService` encapsule mutations; `State` est cloné pour lecture côté observateurs.
- **Performances**: `engine` évite dépendances lourdes (pas de NetworkX). `sim.runner` supporte multiprocessing et vectorisation plus tard.
- **Tests-first**: chaque module inclut ses tests contractuels (`tests/eng/...`, `tests/sim/...`). Objectif >70 % couverture sur `engine`.
- **Doc vivante**: `docs/schemas.md` (DOC-006) décrit les formats utilisés par `serialize`; ce fichier doit rester synchronisé.

## Interfaces externes

- **Cross-validation catanatron**: script optionnel (`tools/crosscheck.py`) comparant nos résultats à ceux de `external/catanatron` si présent.
- **Persistence**: sauvegarde d'états vers disque (JSON/npz) pour reprendre une partie/simulation.
- **Monitoring**: export métriques vers Prometheus/TensorBoard, configurable via `catan.shared.config`.

## Roadmap documentation ↔ plan

- DOC-005 (ce fichier) aligne ENG/SIM/GUI/RL sur une architecture en couches.
- DOC-006 décrira les structures `StateSnapshot`, `ActionRecord`, `ObservationTensor`.
- ENG-001..011 implémenteront les modules `engine.*` selon ce découpage.
- SIM-001..004 s'appuieront sur `catan.sim` tel que décrit.
- GUI-001..004 cibleront `catan.gui.h2h` adossé à `GameService`.
- RL-001..004 suivront la séparation `env`/`algorithms`/`training`.

