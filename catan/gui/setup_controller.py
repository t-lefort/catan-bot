"""Contrôleur pour la phase de setup GUI (GUI-003).

Ce module gère l'interaction utilisateur durant la phase de placement initial.
Conforme aux specs docs/gui-h2h.md section "1. Phase de placement serpent".

Responsabilités:
- Identifier les positions légales (sommets/arêtes) selon l'état du jeu
- Gérer les clics utilisateur (sommets/arêtes)
- Envoyer les actions au GameService
- Fournir les instructions contextuelles pour l'UI
- Maintenir la synchronisation avec l'état du jeu
"""

from __future__ import annotations

from typing import List, Optional, Set

import pygame

from catan.app.game_service import GameService
from catan.engine.state import GameState, SetupPhase
from catan.engine.actions import Action, PlaceSettlement, PlaceRoad


class SetupController:
    """Contrôleur pour la phase de setup GUI.

    Gère l'interaction utilisateur durant les placements initiaux et
    fournit les données nécessaires pour l'affichage (positions légales,
    instructions).
    """

    def __init__(self, game_service: GameService, screen: pygame.Surface) -> None:
        """Initialize setup controller.

        Args:
            game_service: Service de jeu orchestrant l'état
            screen: Surface pygame pour l'affichage
        """
        self.game_service = game_service
        self.screen = screen
        self.state: GameState = game_service.state

        # Cache for legal actions to avoid recomputation
        self._legal_actions_cache: Optional[List[Action]] = None

    def refresh_state(self) -> None:
        """Refresh internal state from game service.

        Doit être appelé après chaque action pour synchroniser l'état.
        """
        self.state = self.game_service.state
        self._legal_actions_cache = None

    def _get_legal_actions(self) -> List[Action]:
        """Get legal actions with caching."""
        if self._legal_actions_cache is None:
            self._legal_actions_cache = self.state.legal_actions()
        return self._legal_actions_cache

    def get_legal_settlement_vertices(self) -> Set[int]:
        """Get set of vertex IDs where settlements can be placed.

        Returns:
            Set of legal vertex IDs
        """
        legal_actions = self._get_legal_actions()
        return {
            action.vertex_id
            for action in legal_actions
            if isinstance(action, PlaceSettlement)
        }

    def get_legal_road_edges(self) -> Set[int]:
        """Get set of edge IDs where roads can be placed.

        Returns:
            Set of legal edge IDs
        """
        legal_actions = self._get_legal_actions()
        return {
            action.edge_id
            for action in legal_actions
            if isinstance(action, PlaceRoad)
        }

    def handle_vertex_click(self, vertex_id: int) -> bool:
        """Handle user click on a vertex.

        Args:
            vertex_id: ID of clicked vertex

        Returns:
            True if action was taken, False otherwise
        """
        # Check if this vertex is legal for settlement placement
        legal_vertices = self.get_legal_settlement_vertices()

        if vertex_id not in legal_vertices:
            return False

        # Find the corresponding action
        legal_actions = self._get_legal_actions()
        settlement_action = next(
            (a for a in legal_actions
             if isinstance(a, PlaceSettlement) and a.vertex_id == vertex_id),
            None
        )

        if settlement_action is None:
            return False

        # Dispatch action to game service
        self.game_service.dispatch(settlement_action)

        # Refresh state
        self.refresh_state()

        return True

    def handle_edge_click(self, edge_id: int) -> bool:
        """Handle user click on an edge.

        Args:
            edge_id: ID of clicked edge

        Returns:
            True if action was taken, False otherwise
        """
        # Check if this edge is legal for road placement
        legal_edges = self.get_legal_road_edges()

        if edge_id not in legal_edges:
            return False

        # Find the corresponding action
        legal_actions = self._get_legal_actions()
        road_action = next(
            (a for a in legal_actions
             if isinstance(a, PlaceRoad) and a.edge_id == edge_id),
            None
        )

        if road_action is None:
            return False

        # Dispatch action to game service
        self.game_service.dispatch(road_action)

        # Refresh state
        self.refresh_state()

        return True

    def get_instructions(self) -> str:
        """Get contextual instructions for the current player.

        Returns:
            Instruction text to display to user
        """
        current_player = self.state.players[self.state.current_player_id]
        player_name = current_player.name

        # Determine round
        if self.state.phase == SetupPhase.SETUP_ROUND_1:
            round_text = "Premier tour de placement"
        elif self.state.phase == SetupPhase.SETUP_ROUND_2:
            round_text = "Second tour de placement"
        else:
            return "Phase de setup terminée"

        # Determine what to place
        legal_actions = self._get_legal_actions()
        if not legal_actions:
            return f"{player_name} — En attente..."

        first_action = legal_actions[0]
        if isinstance(first_action, PlaceSettlement):
            action_text = "Placez une colonie"
        elif isinstance(first_action, PlaceRoad):
            action_text = "Placez une route adjacente"
        else:
            action_text = "Action requise"

        return f"{round_text} — {player_name}: {action_text}"

    def is_setup_complete(self) -> bool:
        """Check if setup phase is complete.

        Returns:
            True if no longer in setup phase
        """
        return self.state.phase not in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2)


__all__ = ["SetupController"]
