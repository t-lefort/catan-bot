"""Script pour lancer des simulations rapides.

Utilisé pour tester la performance et valider les règles.
"""

import time
from typing import List
import numpy as np

from .core.game_state import GameState
from .core.board import Board


def run_simulation(num_games: int = 1000, verbose: bool = False) -> None:
    """Lance plusieurs parties pour mesurer la performance."""

    print(f"Lancement de {num_games} simulations...")

    start_time = time.time()
    winners: List[int] = []

    for i in range(num_games):
        # Créer une nouvelle partie
        board = Board.create_standard_board(shuffle=True)
        game_state = GameState(
            board=board,
            num_players=4,
            victory_points_to_win=10,
        )

        # TODO: Jouer la partie avec des actions aléatoires ou un bot simple

        if verbose and i % 100 == 0:
            print(f"  Partie {i}/{num_games}")

    elapsed_time = time.time() - start_time
    games_per_second = num_games / elapsed_time

    print(f"\nRésultats:")
    print(f"  Temps total: {elapsed_time:.2f}s")
    print(f"  Parties par seconde: {games_per_second:.2f}")
    print(f"  Temps moyen par partie: {elapsed_time/num_games*1000:.2f}ms")


if __name__ == "__main__":
    run_simulation(num_games=100, verbose=True)
