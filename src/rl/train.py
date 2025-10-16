"""Script d'entraînement du bot par RL.

Point d'entrée pour entraîner le modèle.
"""

import torch
import numpy as np
from typing import Optional

from .environment import CatanEnv


def train(
    num_episodes: int = 10000,
    checkpoint_dir: str = "./checkpoints",
    wandb_project: Optional[str] = None,
) -> None:
    """
    Entraîne le bot avec l'apprentissage par renforcement.

    Args:
        num_episodes: Nombre d'épisodes d'entraînement
        checkpoint_dir: Répertoire pour sauvegarder les checkpoints
        wandb_project: Nom du projet W&B (None = pas de logging)
    """

    print(f"Démarrage de l'entraînement pour {num_episodes} épisodes...")

    # Créer l'environnement
    env = CatanEnv(num_players=4, victory_points=10)

    # TODO: Initialiser le modèle (PPO, DQN, AlphaZero, etc.)
    # TODO: Boucle d'entraînement
    # TODO: Logging et checkpointing

    print("Entraînement terminé!")


if __name__ == "__main__":
    train(num_episodes=1000)
