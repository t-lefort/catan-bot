"""État du jeu et logique de transition (ENG-002+).

Ce module définit l'état immuable d'une partie et les transitions d'état.
Conforme aux schémas (docs/schemas.md) et specs (docs/specs.md).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, List


@dataclass
class Player:
    """Représentation d'un joueur."""

    player_id: int
    name: str
    resources: Dict[str, int] = field(
        default_factory=lambda: {
            "BRICK": 0,
            "LUMBER": 0,
            "WOOL": 0,
            "GRAIN": 0,
            "ORE": 0,
        }
    )
    settlements: List[int] = field(default_factory=list)  # vertex_ids
    cities: List[int] = field(default_factory=list)  # vertex_ids
    roads: List[int] = field(default_factory=list)  # edge_ids
    dev_cards: Dict[str, int] = field(
        default_factory=lambda: {"KNIGHT": 0, "PROGRESS": 0, "VP": 0}
    )
    victory_points: int = 0


class SetupPhase(Enum):
    """Phases de setup."""

    SETUP_ROUND_1 = "SETUP_ROUND_1"
    SETUP_ROUND_2 = "SETUP_ROUND_2"
    PLAY = "PLAY"


@dataclass
class GameState:
    """État immuable du jeu.

    Toutes les modifications doivent retourner un nouvel état.
    """

    board: "Board"  # type: ignore
    players: List[Player]
    phase: SetupPhase
    current_player_id: int
    turn_number: int = 0
    # Compteurs de placements pendant setup
    _setup_settlements_placed: int = 0
    _setup_roads_placed: int = 0
    _waiting_for_road: bool = False  # True si colonie placée, en attente de route

    @classmethod
    def new_1v1_game(cls, player_names: List[str] | None = None) -> "GameState":
        """Crée un nouveau jeu 1v1 avec plateau standard.

        Args:
            player_names: Noms des joueurs (par défaut ["Player 0", "Player 1"])

        Returns:
            État initial en phase SETUP_ROUND_1
        """
        from catan.engine.board import Board

        if player_names is None:
            player_names = ["Player 0", "Player 1"]

        board = Board.standard()
        players = [
            Player(player_id=i, name=name) for i, name in enumerate(player_names)
        ]

        return cls(
            board=board,
            players=players,
            phase=SetupPhase.SETUP_ROUND_1,
            current_player_id=0,
            turn_number=0,
        )

    def is_action_legal(self, action: "Action") -> bool:  # type: ignore
        """Vérifie si une action est légale dans l'état actuel.

        Args:
            action: Action à vérifier

        Returns:
            True si l'action est légale
        """
        from catan.engine.actions import PlaceRoad, PlaceSettlement

        # Pendant setup, les règles sont spécifiques
        if self.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2):
            if isinstance(action, PlaceSettlement):
                # Vérifier que le sommet est libre
                vertex_id = action.vertex_id
                if vertex_id not in self.board.vertices:
                    return False
                # Vérifier qu'aucun joueur n'a déjà construit ici
                for player in self.players:
                    if vertex_id in player.settlements or vertex_id in player.cities:
                        return False
                # Pendant setup, on attend une colonie seulement si pas en attente de route
                return not self._waiting_for_road

            elif isinstance(action, PlaceRoad):
                # Doit être en attente de route après placement de colonie
                if not self._waiting_for_road:
                    return False
                # Vérifier que l'arête est libre
                edge_id = action.edge_id
                if edge_id not in self.board.edges:
                    return False
                for player in self.players:
                    if edge_id in player.roads:
                        return False
                # Vérifier que l'arête est adjacente à la dernière colonie placée
                current_player = self.players[self.current_player_id]
                if not current_player.settlements:
                    return False
                last_settlement = current_player.settlements[-1]
                edge = self.board.edges[edge_id]
                return last_settlement in edge.vertices

        # TODO: règles pour phase PLAY
        return False

    def apply_action(self, action: "Action") -> "GameState":  # type: ignore
        """Applique une action et retourne le nouvel état.

        Args:
            action: Action à appliquer

        Returns:
            Nouvel état après application de l'action

        Raises:
            ValueError: Si l'action n'est pas légale
        """
        from catan.engine.actions import PlaceRoad, PlaceSettlement

        if not self.is_action_legal(action):
            raise ValueError(f"Action illégale: {action}")

        # Copier les joueurs pour modification immuable
        new_players = [copy.deepcopy(p) for p in self.players]
        current_player = new_players[self.current_player_id]

        new_state_fields = {
            "board": self.board,
            "players": new_players,
            "phase": self.phase,
            "current_player_id": self.current_player_id,
            "turn_number": self.turn_number,
            "_setup_settlements_placed": self._setup_settlements_placed,
            "_setup_roads_placed": self._setup_roads_placed,
            "_waiting_for_road": self._waiting_for_road,
        }

        if isinstance(action, PlaceSettlement):
            # Placer la colonie
            current_player.settlements.append(action.vertex_id)
            current_player.victory_points += 1
            new_state_fields["_setup_settlements_placed"] = self._setup_settlements_placed + 1
            new_state_fields["_waiting_for_road"] = True

        elif isinstance(action, PlaceRoad):
            # Placer la route
            current_player.roads.append(action.edge_id)
            new_state_fields["_setup_roads_placed"] = self._setup_roads_placed + 1
            new_state_fields["_waiting_for_road"] = False

            # Distribution de ressources UNIQUEMENT après le 2e placement (SETUP_ROUND_2)
            if self.phase == SetupPhase.SETUP_ROUND_2:
                # Récupérer la dernière colonie placée
                last_settlement = current_player.settlements[-1]
                vertex = self.board.vertices[last_settlement]
                # Distribuer une ressource de chaque tuile adjacente (sauf désert)
                for tile_id in vertex.adjacent_tiles:
                    tile = self.board.tiles[tile_id]
                    if tile.resource != "DESERT":
                        current_player.resources[tile.resource] += 1

            # Avancer le jeu après placement de la route
            new_state_fields.update(self._advance_setup_turn())

        return GameState(**new_state_fields)

    def _advance_setup_turn(self) -> dict:
        """Calcule le prochain état après un placement complet (colonie + route).

        Returns:
            Dictionnaire avec les champs à mettre à jour
        """
        updates = {}

        # Compter les placements complets (1 colonie + 1 route = 1 placement)
        total_placements = self._setup_roads_placed + 1  # +1 car on vient de placer

        if self.phase == SetupPhase.SETUP_ROUND_1:
            # Round 1: ordre normal (0, 1)
            if total_placements < 2:
                # Passer au joueur suivant
                updates["current_player_id"] = (self.current_player_id + 1) % 2
            else:
                # Passer au round 2, ordre inverse (commence par joueur 1)
                updates["phase"] = SetupPhase.SETUP_ROUND_2
                updates["current_player_id"] = 1

        elif self.phase == SetupPhase.SETUP_ROUND_2:
            # Round 2: ordre inverse (1, 0)
            if total_placements < 4:
                # Passer au joueur précédent (ordre inverse)
                updates["current_player_id"] = 1 if self.current_player_id == 1 else 0
            else:
                # Setup terminé, passer en phase PLAY
                updates["phase"] = SetupPhase.PLAY
                updates["current_player_id"] = 0  # Le premier joueur commence
                updates["turn_number"] = 1

        return updates


__all__ = [
    "GameState",
    "Player",
    "SetupPhase",
]
