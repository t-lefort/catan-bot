# AGENTS.md

Ce document fournit des consignes pratiques pour les agents (Codex, Claude Code, Copilot, etc.) qui modifient ce dépôt. Son périmètre couvre l’intégralité du répertoire.

## Objectif
- Accélérer la contribution en donnant des règles claires et homogènes.
- Éviter les régressions (tests, typage, style) et les refactorings inutiles.
- Respecter les décisions d’architecture et les invariants de performance.

## Politique d’exécution (agents)
- Claude Code: se conformer à `CLAUDE.md` (ne pas exécuter de commandes Python; demander à l’utilisateur de les lancer et d’en rapporter les résultats).
- Autres agents: suivez la politique de votre harness. Par défaut, utilisez les cibles `make` prévues et évitez les actions destructrices non demandées.

## Prérequis & installation
- Python: 3.10+
- Environnement virtuel recommandé: `python3 -m venv venv && source venv/bin/activate`
- Dépendances: `pip install -r requirements.txt`

## Commandes utiles (Makefile)
- `make install`: installe les dépendances
- `make test`: lance les tests (`pytest -v`)
- `make lint`: `mypy src/` + `ruff check src/ tests/`
- `make format`: `black src/ tests/` + `ruff check --fix`
- `make gui`: lance la GUI (`python -m src.gui.game_window`)
- `make simulate`: simulations rapides (`python -m src.simulate`)
- `make train`: script d’entraînement RL (`python -m src.rl.train`)

## Structure du projet (résumé)
- `src/core/`: moteur de jeu (critique performance)
  - `board.py`: plateau hexagonal (IDs déterministes pour nodes/edges)
  - `constants.py`: constantes + enums
  - `player.py`: état joueur (ressources en `numpy`)
  - `game_state.py`: état complet, immuable, règles
  - `actions.py`: types d’actions (dataclasses)
- `src/rl/`: environnement Gymnasium + entraînement
- `src/gui/`: interface Pygame simple
- `tests/`: suite de tests (pytest)
- `pyproject.toml`: black/ruff/mypy (voir Conventions)

## Conventions de code
- Style
  - Black: largeur de ligne 100 (`pyproject.toml`)
  - Ruff: règles `E,F,I,N,W,B,SIM`; corrigez les avertissements
  - Imports triés par Ruff
- Typage
  - Mypy cible Python 3.10, `disallow_untyped_defs = true`
  - Ajoutez des annotations complètes pour toute nouvelle fonction
- Architecture
  - `GameState` immuable: toute action retourne une COPIE modifiée
  - Pas d’état global caché; pas d’effets de bord non maîtrisés
  - `Board`: utilise des IDs entiers DÉTERMINISTES pour nodes/edges (stables entre runs)
  - Pré-calculs/Index: privilégier des index (ex: `nodes_to_edges`, `tiles_by_number`) pour les hot paths
- Performance
  - Optimiser après profiling; éviter les boucles coûteuses dans `get_valid_actions()` et la distribution de ressources
  - Utiliser `numpy`/structures adaptées; Numba si nécessaire pour hot paths

## Tests & validation
- Avant toute finalisation:
  - `make format`
  - `make lint`
  - `make test`
- Tests ciblés possibles: `pytest tests/test_*.py -k <motif>`
- Couverture: `pytest --cov=src --cov-report=term`

## Règles de contribution (agents)
- Changements ciblés et minimaux: ne pas renommer largement ni déplacer sans nécessité.
- Préserver les interfaces publiques (types d’actions, signatures des méthodes clés).
- Respecter l’immutabilité de `GameState` et l’API de `Board`/`PlayerState`.
- Documenter brièvement les zones complexes (calculs de routes, encodage d’actions).
- N’ajoutez pas d’entêtes de licence; gardez le style existant.

## Pièges et divergences connues
- Évolution du plateau: la base actuelle de `board.py` implémente un système d’IDs (tiles/nodes/edges) et un `Tile` moderne; certains tests historiques (ex: `tests/test_board.py`) référencent des types anciens (`HexCoord`, `VertexCoord`, `EdgeCoord`, `Hex`).
  - Si vous touchez à `board.py` ou aux tests, évitez les refactorings massifs. Deux chemins possibles selon la tâche:
    1) Ajouter des wrappers de compatibilité légers exposant les anciens noms vers les nouvelles structures; ou
    2) Mettre à jour les tests pour utiliser les API actuelles, de façon incrémentale.
- `Board.create_standard_board`: ports/eau encore simplifiés (TODO). Tenez compte des TODOs avant d’introduire des régressions.
- `GameState.get_valid_actions`: critique performance; ne pas alourdir sans indexation adaptée.
- `RL env` (`src/rl/environment.py`): encodage/décodage d’actions encore à faire; ne mélangez pas la logique cœur avec du code d’expérience RL.

## Ajouts typiques et emplacements
- Nouvelles règles: `src/core/game_state.py` (génération d’actions, application d’actions, production, voleur, échanges, bonus).
- Géométrie/plateau: `src/core/board.py` (IDs déterministes, maps d’adjacence, ports/eau).
- Agents/entraînement: `src/rl/` (gardez l’API `CatanEnv` claire et stable).
- GUI: `src/gui/game_window.py` (ne mélangez pas UI et règles).

## Checklist avant handoff/PR
- Code formaté (Black) et linté (Ruff/Mypy) sans erreurs.
- Tests pertinents verts localement (`make test`).
- Pas de réécriture inutile ni de régression perf évidente.
- TODOs touchés documentés et alignés avec l’architecture.

## Références
- `README.md`, `QUICKSTART.md`, `ARCHITECTURE.md` pour la vision et les flux principaux.
- `CLAUDE.md` pour la politique d’exécution spécifique à Claude Code.
- `TEST_COVERAGE_REPORT.md` pour l’étendue attendue des tests (attention aux décalages historiques mentionnés ci‑dessus).

