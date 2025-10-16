# Démarrage Rapide

Guide pour commencer à développer sur CatanBot.

## Installation

```bash
# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

## Premiers Tests

### 1. Vérifier que l'installation fonctionne

```bash
# Lancer les tests
pytest

# Si les tests passent, tout est correctement installé
```

### 2. Lancer la GUI

```bash
# Démarrer l'interface graphique
python -m src.gui.game_window

# Appuyez sur 'N' pour une nouvelle partie
# ESC pour quitter
```

### 3. Tester les simulations

```bash
# Lancer quelques parties rapides
python -m src.simulate
```

## Prochaines Étapes

### Phase 1: Compléter le Moteur de Jeu

Les fichiers suivants ont besoin d'implémentation:

1. **[board.py](src/core/board.py)** - `create_standard_board()`
   - Générer le plateau standard avec 19 hexagones
   - Distribution correcte des terrains et numéros
   - Placement des ports

2. **[game_state.py](src/core/game_state.py)** - Logique des règles
   - `get_valid_actions()`: Liste toutes les actions possibles
   - `apply_action()`: Applique une action et retourne le nouvel état
   - Distribution des ressources lors d'un jet de dés
   - Gestion du voleur (robber)
   - Calcul de la plus longue route
   - Calcul de la plus grande armée

3. **[actions.py](src/core/actions.py)** - Encodage/décodage
   - Convertir Action → int pour les réseaux de neurones
   - Convertir int → Action pour l'exécution

### Phase 2: Entraînement RL

Une fois le moteur de jeu complet:

1. **Choisir un algorithme**:
   - PPO (simple, stable)
   - DQN (classique)
   - AlphaZero (le plus puissant mais complexe)

2. **Implémenter dans [train.py](src/rl/train.py)**:
   - Boucle d'entraînement
   - Self-play
   - Sauvegarde de checkpoints
   - Logging (TensorBoard/W&B)

3. **Reward shaping** (optionnel):
   - Récompense pour victoire: +1
   - Pénalité pour défaite: -1
   - Bonus pour constructions: +0.1 par colonie, +0.2 par ville
   - Bonus pour ressources: +0.01 par ressource

### Phase 3: Optimisation et Tests

1. **Profiling**:
   ```bash
   python -m cProfile -o profile.stats -m src.simulate
   python -m pstats profile.stats
   ```

2. **Optimisation**:
   - Identifier les fonctions lentes
   - Utiliser NumPy pour les opérations vectorielles
   - Ajouter `@numba.jit` sur les hot paths
   - Considérer Cython pour le code critique

3. **Benchmarks**:
   - Objectif: 1000+ parties/seconde
   - Mesurer régulièrement avec `src.simulate`

### Phase 4: Interface Colonist.IO (Avancé)

Pour jouer sur Colonist.IO:

1. Analyser l'interface web (DevTools)
2. Automatiser avec Selenium/Playwright
3. Parser l'état du jeu depuis le DOM
4. Traduire en GameState
5. Exécuter les actions du bot
6. Gérer les timing et latences

## Architecture Décisionnelle

### Pour un Bot Simple (Baseline)

Créer d'abord un bot basé sur des heuristiques:

```python
# src/rl/baseline_agent.py
class HeuristicAgent:
    def choose_action(self, game_state):
        # 1. Toujours construire si possible
        # 2. Préférer les colonies sur les meilleurs spots
        # 3. Commercer intelligemment
        # 4. Placer le voleur sur le joueur en tête
        pass
```

Cela permet de:
- Tester le moteur de jeu
- Avoir un adversaire pour l'entraînement
- Établir une baseline de performance

### Pour l'Entraînement RL

**Recommandé pour commencer: PPO**

```python
from stable_baselines3 import PPO

model = PPO(
    "MultiInputPolicy",
    env,
    verbose=1,
    tensorboard_log="./logs/"
)

model.learn(total_timesteps=1_000_000)
```

**Pour niveau expert: AlphaZero**

Plus complexe mais potentiellement plus fort:
- MCTS pour l'exploration
- Réseau de neurones pour l'évaluation
- Self-play pour l'entraînement

## Conseils de Développement

1. **Commencer petit**: Implémentez d'abord une version simplifiée (plateau fixe, pas de cartes dev)

2. **Tester constamment**: Utilisez la GUI pour vérifier chaque règle implémentée

3. **Commits fréquents**: Chaque règle implémentée = 1 commit

4. **Documentation**: Commentez les parties complexes (calcul longest road, etc.)

5. **Tests unitaires**: Testez chaque règle individuellement

## Ressources

- [Règles officielles Catan](https://www.catan.com/understand-catan/game-rules)
- [Gymnasium docs](https://gymnasium.farama.org/)
- [PyTorch RL tutorial](https://pytorch.org/tutorials/intermediate/reinforcement_q_learning.html)
- [AlphaZero paper](https://arxiv.org/abs/1712.01815)

## Questions Fréquentes

**Q: Par où commencer?**
A: Implémentez `Board.create_standard_board()` puis testez avec la GUI.

**Q: Comment débugger le moteur de jeu?**
A: Utilisez la GUI et jouez manuellement pour vérifier les règles.

**Q: Quel algorithme RL choisir?**
A: PPO pour commencer, AlphaZero pour le niveau expert.

**Q: Comment accélérer les simulations?**
A: Profile → Optimize hot paths → Numba → Cython si nécessaire.

**Q: Combien de temps pour l'entraînement?**
A: Plusieurs heures à plusieurs jours selon l'algorithme et le hardware.
