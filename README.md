# CatanBot

Un bot Catan de niveau surhumain utilisant l'apprentissage par renforcement.

## Objectifs

- Créer un environnement de simulation rapide du jeu Catan (Colons de Catane)
- Développer un agent RL capable de battre les meilleurs joueurs humains
- Mode 1v1 (15 points) et 4 joueurs (10 points)
- Interface graphique simple pour tester et jouer contre le bot
- Potentiellement compatible avec Colonist.IO pour jouer en classé

## Architecture

### Core Game Engine (`src/core/`)
Moteur de jeu optimisé pour la vitesse, permettant des milliers de simulations rapides.

### RL Training (`src/rl/`)
Infrastructure d'apprentissage par renforcement pour entraîner le bot.

### GUI (`src/gui/`)
Interface graphique simple pour jouer contre le bot et vérifier les règles.

### Integration (`src/integration/`)
Code pour interfacer avec Colonist.IO (futur).

## Technologie

- **Python 3.10+** pour la flexibilité et l'écosystème RL
- **NumPy** pour les calculs rapides
- **PyTorch** pour l'apprentissage par renforcement
- **Pygame** pour l'interface graphique simple
- **Numba** (optionnel) pour accélérer les parties critiques

## Installation

```bash
pip install -r requirements.txt
```

## Démarrage Rapide

```bash
# Installation
pip install -r requirements.txt

# Lancer l'interface graphique
make gui
# ou: python -m src.gui.game_window

# Lancer les tests
make test

# Voir toutes les commandes
make help
```

Voir [QUICKSTART.md](QUICKSTART.md) pour un guide détaillé.

## Utilisation

```bash
# Lancer une simulation rapide
make simulate
# ou: python -m src.simulate

# Jouer contre le bot (GUI)
make gui
# ou: python -m src.gui.game_window

# Entraîner le bot
make train
# ou: python -m src.rl.train

# Lancer les tests
make test
# ou: pytest

# Formatter le code
make format
```

## État du Projet

### ✅ Implémenté (Structure de base)

- Structure du projet et configuration
- Système de coordonnées hexagonales (cubic coordinates)
- Classes de base (GameState, PlayerState, Board)
- Définitions des actions
- Wrapper Gymnasium pour l'environnement RL
- Interface Pygame basique
- Tests unitaires de base

### 🚧 En cours d'implémentation

- Génération du plateau standard (19 hexagones)
- Moteur de règles complet
- Distribution des ressources
- Validation des placements de constructions
- Commerce avec la banque et les ports
- Cartes développement
- Calcul de la plus longue route / plus grande armée

### 📋 À faire

- Encodage/décodage des actions pour les réseaux de neurones
- Choix et implémentation de l'algorithme RL (PPO/AlphaZero)
- Pipeline d'entraînement avec self-play
- Optimisation des performances (objectif: 1000+ parties/sec)
- Interface graphique interactive
- Intégration Colonist.IO

## Documentation

- [CLAUDE.md](CLAUDE.md) - Guide d'architecture et développement pour Claude Code
- [QUICKSTART.md](QUICKSTART.md) - Guide de démarrage détaillé
- [requirements.txt](requirements.txt) - Dépendances Python
