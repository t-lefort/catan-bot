"""Main game state representation.

Le GameState contient l'état complet d'une partie de Catan.
Conçu pour être:
- Immutable (copie pour chaque action)
- Hashable (pour MCTS/AlphaZero)
- Sérialisable (pour sauvegarder/charger)
- Rapide à copier (copy-on-write pour les structures volumineuses)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple
from enum import IntEnum, auto
import numpy as np

from .board import Board, VertexCoord, EdgeCoord
from .player import PlayerState
from .constants import DevelopmentCardType, ResourceType


class GamePhase(IntEnum):
    """Phases du jeu."""
    SETUP = 0           # Phase d'installation (colonies + routes initiales)
    MAIN_GAME = 1       # Jeu principal
    GAME_OVER = 2       # Partie terminée


class TurnPhase(IntEnum):
    """Phases du tour."""
    ROLL_DICE = 0       # Lancer les dés
    ROBBER = 1          # Déplacer le voleur (si 7)
    DISCARD = 2         # Défausser si trop de cartes (si 7)
    MAIN = 3            # Phase principale (construire, commercer, etc.)
    END_TURN = 4        # Fin du tour


@dataclass
class GameState:
    """
    État complet du jeu.

    Contient:
    - Le plateau
    - L'état de chaque joueur
    - La phase du jeu
    - L'historique nécessaire pour les règles
    """

    # Configuration
    board: Board
    num_players: int
    victory_points_to_win: int = 10

    # État des joueurs
    players: List[PlayerState] = field(default_factory=list)
    current_player_idx: int = 0

    # Phase du jeu
    game_phase: GamePhase = GamePhase.SETUP
    turn_phase: TurnPhase = TurnPhase.ROLL_DICE

    # Cartes développement restantes
    dev_card_deck: List[DevelopmentCardType] = field(default_factory=list)

    # État du plateau
    settlements_on_board: dict[VertexCoord, int] = field(default_factory=dict)
    cities_on_board: dict[VertexCoord, int] = field(default_factory=dict)
    roads_on_board: dict[EdgeCoord, int] = field(default_factory=dict)

    # Compteurs de tours
    turn_number: int = 0

    # Dernier jet de dés
    last_dice_roll: Optional[int] = None

    # Gagnant
    winner: Optional[int] = None

    @property
    def current_player(self) -> PlayerState:
        """Retourne le joueur actuel."""
        return self.players[self.current_player_idx]

    def is_game_over(self) -> bool:
        """Vérifie si la partie est terminée."""
        return self.game_phase == GamePhase.GAME_OVER

    def check_victory(self) -> Optional[int]:
        """Vérifie si un joueur a gagné. Retourne l'ID du gagnant ou None."""
        for player in self.players:
            if player.victory_points() >= self.victory_points_to_win:
                return player.player_id
        return None

    def next_player(self) -> None:
        """Passe au joueur suivant."""
        self.current_player_idx = (self.current_player_idx + 1) % self.num_players
        self.turn_number += 1

    def can_place_settlement(self, vertex: VertexCoord, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une colonie sur un sommet.

        Règles:
        - Le sommet ne doit pas avoir de construction
        - Les sommets adjacents ne doivent pas avoir de construction (règle de distance)
        - En phase principale: doit être adjacent à une route du joueur
        """
        # Vérifier qu'il n'y a pas déjà une construction
        if vertex in self.settlements_on_board or vertex in self.cities_on_board:
            return False

        # Règle de distance: pas de construction sur les sommets adjacents
        for adj_vertex in vertex.adjacent_vertices():
            if adj_vertex in self.settlements_on_board or adj_vertex in self.cities_on_board:
                return False

        # En phase principale, doit être adjacent à une route du joueur
        if self.game_phase == GamePhase.MAIN_GAME:
            player = self.players[player_id]
            # Vérifier qu'au moins une route adjacente appartient au joueur
            adjacent_edges = [
                edge for v1 in vertex.adjacent_vertices()
                for edge in self._edges_between(vertex, v1)
            ]
            if not any(edge in player.roads for edge in adjacent_edges):
                return False

        return True

    def can_place_city(self, vertex: VertexCoord, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une ville sur un sommet.

        Règles:
        - Doit y avoir une colonie du joueur
        """
        return (
            vertex in self.settlements_on_board
            and self.settlements_on_board[vertex] == player_id
        )

    def can_place_road(self, edge: EdgeCoord, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une route sur une arête.

        Règles:
        - L'arête ne doit pas avoir de route
        - Doit être adjacent à une construction ou route du joueur
        """
        # Vérifier qu'il n'y a pas déjà une route
        if edge in self.roads_on_board:
            return False

        player = self.players[player_id]

        # Vérifier qu'une extrémité est connectée à une route ou construction du joueur
        v1, v2 = edge.vertices()

        # Vérifier les constructions du joueur
        if v1 in player.settlements or v1 in player.cities:
            return True
        if v2 in player.settlements or v2 in player.cities:
            return True

        # Vérifier les routes adjacentes
        for adj_edge in edge.adjacent_edges():
            if adj_edge in player.roads:
                return True

        return False

    def _edges_between(self, v1: VertexCoord, v2: VertexCoord) -> List[EdgeCoord]:
        """Retourne les arêtes entre deux sommets adjacents."""
        # TODO: Implémenter la conversion vertex->edge
        return []

    def get_valid_actions(self) -> List['Action']:
        """
        Retourne toutes les actions valides pour le joueur actuel.

        Cette méthode est critique pour la performance (appelée des millions de fois).
        """
        # TODO: Implémenter
        return []

    def apply_action(self, action: 'Action') -> 'GameState':
        """
        Applique une action et retourne le nouvel état.

        Retourne une copie modifiée du GameState (immutabilité).
        """
        # TODO: Implémenter
        return self

    def __repr__(self) -> str:
        return (
            f"GameState(turn={self.turn_number}, "
            f"phase={self.game_phase.name}, "
            f"current_player={self.current_player_idx}, "
            f"winner={self.winner})"
        )
