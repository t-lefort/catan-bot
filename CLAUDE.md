# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CatanBot is a superhuman Catan (Settlers of Catan) AI using reinforcement learning. The goal is to create a bot capable of beating top human players in both 1v1 (15 points) and 4-player (10 points) modes, with potential integration with Colonist.IO for competitive play.

### Key Design Goals

1. **Performance**: Game engine optimized for running thousands of simulations quickly
2. **Correctness**: Complete and accurate implementation of all Catan rules
3. **Modularity**: Clear separation between game engine, RL training, and GUI
4. **Testability**: Simple GUI to verify rule implementation and play against the bot

## Project Structure

```
src/
├── core/           # Game engine (optimized for speed)
│   ├── board.py        # Hexagonal board representation (cubic coordinates)
│   ├── constants.py    # Game constants, resources, terrain types
│   ├── player.py       # Player state (resources, buildings, dev cards)
│   ├── game_state.py   # Complete game state (immutable, hashable)
│   └── actions.py      # All possible actions (type-safe)
├── rl/             # Reinforcement learning infrastructure
│   ├── environment.py  # Gymnasium-compatible environment
│   └── train.py        # Training script
├── gui/            # Simple Pygame GUI for testing
│   └── game_window.py  # Main game window
└── integration/    # Future: Colonist.IO integration
```

## Core Architecture

### Board Representation

The board uses **cubic coordinates** for hexagons (q, r, s where q+r+s=0):
- `HexCoord`: Hexagon position
- `VertexCoord`: Intersection of 3 hexagons (building placement)
- `EdgeCoord`: Edge between 2 hexagons (road placement)

This system provides O(1) neighbor lookups and efficient geometric calculations.

### Game State Design

`GameState` is designed to be:
- **Immutable**: Each action creates a new state (important for MCTS/AlphaZero)
- **Hashable**: Can be used as dict keys for caching/transposition tables
- **Fast to copy**: Uses copy-on-write for large structures
- **Complete**: Contains all information needed to continue the game

### Action System

Actions are type-safe dataclasses (see `actions.py`):
- Each action type is a distinct class
- Actions can be encoded/decoded to integers for neural networks
- Action masking is used to filter invalid actions efficiently

### Player State

`PlayerState` uses NumPy arrays for resources (indexed by `ResourceType`) for fast vectorized operations during simulations.

## Development Commands

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Type checking
mypy src/

# Code formatting
black src/ tests/
ruff check src/ tests/
```

### Running the Project

```bash
# Launch GUI to play against bot
python -m src.gui.game_window

# Run fast simulations (benchmark)
python -m src.simulate

# Train the RL model
python -m src.rl.train
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_board.py

# Run with coverage
pytest --cov=src tests/
```

## Implementation Status

### Currently Implemented (Scaffolding)
- Board geometry and coordinate systems
- Basic data structures (GameState, PlayerState, Board)
- Action type definitions
- Gymnasium environment wrapper
- Simple Pygame GUI framework
- Project structure and configuration

### TODO (Critical for MVP)
1. **Complete game rules engine**:
   - Resource production on dice rolls
   - Building placement validation (distance rule, connectivity)
   - Trading (bank, ports, players)
   - Development cards (knight, road building, year of plenty, monopoly)
   - Robber mechanics
   - Longest road and largest army calculation
   - Victory condition checking

2. **Standard board generation**:
   - Create the 19-hex standard Catan board
   - Shuffle terrain types and numbers
   - Place ports correctly

3. **Action encoding/decoding**:
   - Convert actions to/from integers for neural networks
   - Efficient action space representation

4. **RL training pipeline**:
   - Choose algorithm (PPO, DQN, or AlphaZero)
   - Implement reward shaping
   - Self-play infrastructure
   - Checkpoint management

5. **GUI improvements**:
   - Interactive building placement
   - Display valid moves
   - Better visualization

## Key Technical Decisions

### Why Python?
Despite performance concerns, Python offers:
- Rich RL ecosystem (PyTorch, Stable-Baselines3)
- Fast prototyping
- NumPy for performance-critical code
- Numba JIT compilation for hot paths if needed

### Why Cubic Coordinates?
Cubic coordinates (q, r, s) for hexagons provide:
- Simple neighbor calculations (6 unit vectors)
- Efficient distance metrics
- Natural vertex/edge representation
- No complex offset coordinate conversions

### Why Immutable GameState?
Immutability is essential for:
- MCTS/AlphaZero tree search (share states safely)
- Parallel simulations
- Debugging (state history)
- Avoiding subtle bugs from mutation

### Performance Optimization Strategy
1. **First**: Implement correctly with readable code
2. **Then**: Profile to find bottlenecks
3. **Finally**: Optimize hot paths (Numba, Cython, or C++ bindings)

Target: 1000+ games/second on a single CPU core

## Future Enhancements

- **Colonist.IO Integration**: Selenium/Playwright for web automation
- **Multi-agent training**: Self-play with diverse strategies
- **Advanced RL algorithms**: AlphaZero, MuZero
- **Distributed training**: Ray or similar framework
- **Rule variants**: Cities & Knights, Seafarers expansions
- **Analysis tools**: Strategy visualization, game replay

## Common Patterns

### Adding a New Action Type

1. Define the action class in `actions.py`
2. Add validation in `GameState.can_perform_action()`
3. Implement effect in `GameState.apply_action()`
4. Add to action encoding/decoding
5. Write tests

### Optimizing Performance

1. Profile with `cProfile` or `py-spy`
2. Use NumPy for array operations
3. Consider Numba `@jit` for hot loops
4. Cache expensive calculations (e.g., longest road)
5. Use `__slots__` for memory-intensive classes

### Testing Game Rules

Use the GUI to verify rules:
```bash
python -m src.gui.game_window
```

Play through scenarios to ensure correct behavior.
