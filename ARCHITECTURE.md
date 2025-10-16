# Architecture du Projet CatanBot

Ce document détaille l'architecture technique du projet.

## Structure des Fichiers

```
CatanBot/
├── README.md              # Aperçu du projet
├── QUICKSTART.md          # Guide de démarrage
├── CLAUDE.md              # Guide pour Claude Code
├── ARCHITECTURE.md        # Ce fichier
├── Makefile               # Commandes make
├── requirements.txt       # Dépendances Python
├── pyproject.toml         # Configuration Python
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/              # Moteur de jeu (performance critique)
│   │   ├── __init__.py
│   │   ├── constants.py   # Constantes du jeu (ressources, coûts, etc.)
│   │   ├── board.py       # Représentation du plateau hexagonal
│   │   ├── player.py      # État d'un joueur (ressources, constructions)
│   │   ├── game_state.py  # État complet du jeu (immutable)
│   │   └── actions.py     # Toutes les actions possibles
│   │
│   ├── rl/                # Infrastructure d'apprentissage
│   │   ├── __init__.py
│   │   ├── environment.py # Wrapper Gymnasium
│   │   └── train.py       # Script d'entraînement
│   │
│   ├── gui/               # Interface graphique
│   │   ├── __init__.py
│   │   └── game_window.py # Fenêtre Pygame
│   │
│   ├── integration/       # Intégration externe (futur)
│   │   └── __init__.py
│   │
│   └── simulate.py        # Script de simulation/benchmark
│
└── tests/
    ├── __init__.py
    └── test_board.py      # Tests du plateau
```

## Flux de Données

### 1. Simulation de Parties

```
┌─────────────┐
│   Board     │  Génération aléatoire du plateau
└──────┬──────┘
       │
       v
┌─────────────┐
│ GameState   │  État initial (phase setup)
└──────┬──────┘
       │
       v
   ┌───┴────┐
   │ Action │  Joueur choisit une action
   └───┬────┘
       │
       v
┌─────────────┐
│ GameState'  │  Nouvel état après action
└──────┬──────┘
       │
       └─────> Répéter jusqu'à victoire
```

### 2. Entraînement RL

```
┌──────────────┐
│  CatanEnv    │  Wrapper Gymnasium
│ (environment)│
└───────┬──────┘
        │
        ├─> observation (état du jeu encodé)
        │
        v
┌──────────────┐
│  RL Agent    │  Réseau de neurones (PPO/AlphaZero)
│  (modèle)    │
└───────┬──────┘
        │
        ├─> action (entier)
        │
        v
┌──────────────┐
│  GameState   │  Applique l'action
└───────┬──────┘
        │
        └─> reward (récompense pour l'agent)
```

### 3. GUI Interactive

```
┌──────────────┐
│  Pygame      │  Affichage graphique
│  Window      │
└───────┬──────┘
        │
        ├─> Render board, players, etc.
        │
        v
┌──────────────┐
│  User Input  │  Clic souris / clavier
└───────┬──────┘
        │
        v
┌──────────────┐
│  Action      │  Convertir input en action
└───────┬──────┘
        │
        v
┌──────────────┐
│  GameState'  │  Nouvel état
└──────────────┘
```

## Composants Clés

### 1. Board (Plateau)

**Responsabilité**: Représenter la géométrie du plateau

**Design Pattern**: Value Object (immutable)

**Coordonnées Cubiques**:
```
        q
       /
      /
     *-----> r
     \
      \
       s (= -q-r)
```

**Avantages**:
- Calculs de voisinage en O(1)
- Distance hexagonale simple: `(|q1-q2| + |r1-r2| + |s1-s2|) / 2`
- Pas de cas particuliers selon les lignes

**Classes**:
- `HexCoord`: Position d'un hexagone
- `VertexCoord`: Intersection de 3 hexagones (pour colonies/villes)
- `EdgeCoord`: Arête entre 2 hexagones (pour routes)
- `Hex`: Un hexagone avec son terrain et numéro
- `Board`: Collection d'hexagones avec index

### 2. GameState (État du Jeu)

**Responsabilité**: Représenter l'état complet du jeu

**Design Pattern**: Immutable State

**Pourquoi immutable?**
- Nécessaire pour MCTS (Monte Carlo Tree Search)
- Facilite le multi-threading
- Simplifie le debugging (historique des états)
- Évite les bugs de mutation

**Contenu**:
- Plateau (Board)
- Joueurs (PlayerState[])
- Phase du jeu (Setup / Main / Game Over)
- Deck de cartes développement
- Dernier jet de dés
- Compteur de tours

**Méthodes critiques**:
- `get_valid_actions()`: Liste des actions possibles (hot path!)
- `apply_action()`: Retourne nouvel état après action
- `check_victory()`: Vérifie condition de victoire

### 3. PlayerState (État d'un Joueur)

**Responsabilité**: État des ressources et constructions d'un joueur

**Optimisations**:
- Ressources = NumPy array (vectorisation)
- Constructions = Set (recherche O(1))
- Cache du longest road length

**Contenu**:
- ID du joueur
- Ressources (5 types)
- Cartes développement (main + jouées)
- Constructions (settlements, cities, roads)
- Chevaliers joués
- Bonus (longest road, largest army)

### 4. Actions

**Responsabilité**: Représenter toutes les actions possibles

**Design Pattern**: Type-safe Union (dataclasses)

**Types d'actions**:
1. **Phase de dés**: Roll dice
2. **Constructions**: Build settlement/city/road
3. **Commerce**: Trade with bank/port
4. **Cartes développement**: Play knight/road building/etc.
5. **Voleur**: Move robber, steal resource
6. **Défausse**: Discard resources (si dé = 7)
7. **Fin de tour**: End turn

**Encodage pour RL**:
```python
# Action -> int (pour le réseau de neurones)
action_int = encode_action(action)

# int -> Action (pour l'exécution)
action = decode_action(action_int)
```

### 5. CatanEnv (Environnement RL)

**Responsabilité**: Wrapper pour frameworks RL

**Interface Gymnasium**:
- `reset()`: Nouvelle partie
- `step(action)`: Exécute action, retourne (obs, reward, done, info)
- `render()`: Affichage (optionnel)

**Action Masking**:
```python
valid_actions_mask = env.get_valid_actions_mask()
# Masque binaire: 1 = action valide, 0 = invalide
# Permet au réseau de ne considérer que les actions légales
```

## Décisions d'Architecture

### Pourquoi Python?

**Avantages**:
- Écosystème RL mature (PyTorch, Stable-Baselines3, Gymnasium)
- Prototypage rapide
- NumPy pour performance
- Facilité de debugging

**Inconvénients**:
- Plus lent que C++/Rust
- GIL limite le multi-threading

**Mitigation**:
- NumPy pour opérations vectorielles
- Numba JIT pour hot paths
- Multiprocessing pour parallélisation
- Cython/C++ pour parties critiques si nécessaire

### Coordonnées Cubiques vs Offset

**Cubiques (choisi)**:
- Voisinage simple: 6 directions constantes
- Distance naturelle
- Pas de cas particuliers
- Mathématiques élégantes

**Offset (rejeté)**:
- Voisinage change selon la ligne (pair/impair)
- Plus difficile à debugger
- Cas particuliers nombreux

### Immutable vs Mutable GameState

**Immutable (choisi)**:
- Requis pour MCTS/AlphaZero
- Thread-safe par défaut
- Historique gratuit
- Debugging simplifié

**Mutable (rejeté)**:
- Plus rapide en mémoire
- Mais: bugs de mutation
- Mais: MCTS impossible
- Mais: parallélisation difficile

### Action Space: Discrete vs MultiDiscrete

**Discrete (choisi)**:
- Un seul entier par action
- Simple pour le réseau de neurones
- Action masking efficace

**MultiDiscrete (rejeté)**:
- Plus structuré (type, paramètres)
- Mais: plus complexe à encoder
- Mais: masking plus difficile

## Patterns de Performance

### 1. Hot Path Optimization

**Identifier les hot paths**:
```bash
python -m cProfile -o profile.stats -m src.simulate
python -m pstats profile.stats
```

**Optimiser par ordre**:
1. Algorithme (complexité)
2. Structure de données
3. Vectorisation NumPy
4. Numba JIT
5. Cython
6. C++ binding

### 2. Memory Efficiency

**GameState copy-on-write**:
- Board partagé entre états (immutable)
- PlayerState copié uniquement si modifié
- Cache invalidé intelligemment

### 3. Parallel Simulations

**Multiprocessing pool**:
```python
from multiprocessing import Pool

with Pool(processes=8) as pool:
    results = pool.map(run_game, range(1000))
```

### 4. Caching

**LRU cache pour calculs coûteux**:
```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def compute_longest_road(road_set):
    # Calcul coûteux
    pass
```

## Prochaines Étapes Architecture

### Court Terme
1. Implémenter `Board.create_standard_board()`
2. Compléter `GameState.get_valid_actions()`
3. Implémenter `GameState.apply_action()`
4. Action encoding/decoding

### Moyen Terme
1. Benchmark et profiling
2. Optimisation des hot paths
3. Self-play infrastructure
4. Checkpointing et logging

### Long Terme
1. Distributed training (Ray)
2. MCTS parallelization
3. Colonist.IO integration
4. Web API pour jouer contre le bot
