"""Module RL pour CatanBot.

Ce module contient les composants nécessaires pour l'entraînement par
Reinforcement Learning (apprentissage par renforcement) :

- features.py : Encodage des observations du jeu en tenseurs pour les réseaux de neurones
- policies.py : Agents baselines (aléatoire, heuristique) pour l'évaluation et la simulation

L'encodage utilise une **perspective ego-centrée** : toutes les informations sont
encodées relativement au joueur actuel, ce qui accélère l'apprentissage en rendant
la tâche de l'agent symétrique (il n'a pas besoin d'apprendre séparément comment
jouer en tant que joueur 0 et joueur 1).

Exemple :
    >>> from catan.engine.state import GameState
    >>> from catan.rl.features import build_observation
    >>>
    >>> state = GameState.new_1v1_game(seed=42)
    >>> obs = build_observation(state)
    >>> # obs.hands[0] contient toujours les ressources du joueur actuel
    >>> # obs.hands[1] contient toujours les ressources de l'adversaire
"""

from .features import ObservationTensor, build_observation
from .policies import AgentPolicy, HeuristicPolicy, RandomLegalPolicy

__all__ = [
    "AgentPolicy",
    "HeuristicPolicy",
    "RandomLegalPolicy",
    "ObservationTensor",
    "build_observation",
]
