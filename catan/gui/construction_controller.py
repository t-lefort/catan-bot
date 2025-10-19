"""Contrôleur pour la construction et les achats GUI (GUI-006).

Ce module gère l'interaction utilisateur pour:
- Construire routes, colonies, villes
- Acheter des cartes de développement
- Afficher les coûts et valider les ressources en temps réel
- Fournir les positions légales pour la construction

Conforme aux specs docs/gui-h2h.md section "Actions principales".
"""

from __future__ import annotations

from typing import Dict, Optional, Set

import pygame

from catan.app.game_service import GameService
from catan.engine.state import GameState
from catan.engine.actions import (
    Action,
    PlaceRoad,
    PlaceSettlement,
    BuildCity,
    BuyDevelopment,
)
from catan.engine.rules import COSTS


class ConstructionController:
    """Contrôleur pour la construction et les achats GUI.

    Gère l'interaction utilisateur pour construire et acheter,
    avec validation des ressources et affichage des positions légales.
    """

    def __init__(self, game_service: GameService, screen: pygame.Surface) -> None:
        """Initialize construction controller.

        Args:
            game_service: Service de jeu orchestrant l'état
            screen: Surface pygame pour l'affichage
        """
        self.game_service = game_service
        self.screen = screen
        self.state: GameState = game_service.state

        # Cache for legal actions to avoid recomputation
        self._legal_actions_cache: Optional[list[Action]] = None

    def refresh_state(self) -> None:
        """Refresh internal state from game service.

        Doit être appelé après chaque action pour synchroniser l'état.
        """
        self.state = self.game_service.state
        self._legal_actions_cache = None

    def _get_legal_actions(self) -> list[Action]:
        """Get legal actions with caching."""
        if self._legal_actions_cache is None:
            self._legal_actions_cache = self.state.legal_actions()
        return self._legal_actions_cache

    # === Resource checks ===

    def can_afford_road(self) -> bool:
        """Check if current player can afford a road.

        Returns:
            True if player has enough resources for a road
        """
        player = self.state.players[self.state.current_player_id]
        road_cost = COSTS["road"]

        for resource, amount in road_cost.items():
            if player.resources.get(resource, 0) < amount:
                return False

        return True

    def can_afford_settlement(self) -> bool:
        """Check if current player can afford a settlement.

        Returns:
            True if player has enough resources for a settlement
        """
        player = self.state.players[self.state.current_player_id]
        settlement_cost = COSTS["settlement"]

        for resource, amount in settlement_cost.items():
            if player.resources.get(resource, 0) < amount:
                return False

        return True

    def can_afford_city(self) -> bool:
        """Check if current player can afford a city.

        Returns:
            True if player has enough resources for a city
        """
        player = self.state.players[self.state.current_player_id]
        city_cost = COSTS["city"]

        for resource, amount in city_cost.items():
            if player.resources.get(resource, 0) < amount:
                return False

        return True

    def can_afford_development(self) -> bool:
        """Check if current player can afford a development card.

        Returns:
            True if player has enough resources for a development card
        """
        player = self.state.players[self.state.current_player_id]
        dev_cost = COSTS["development"]

        for resource, amount in dev_cost.items():
            if player.resources.get(resource, 0) < amount:
                return False

        return True

    # === Legal positions ===

    def get_legal_road_positions(self) -> Set[int]:
        """Get set of edge IDs where roads can be built.

        Returns:
            Set of legal edge IDs for road placement
        """
        legal_actions = self._get_legal_actions()
        return {
            action.edge_id
            for action in legal_actions
            if isinstance(action, PlaceRoad) and not action.free
        }

    def get_legal_settlement_positions(self) -> Set[int]:
        """Get set of vertex IDs where settlements can be built.

        Returns:
            Set of legal vertex IDs for settlement placement
        """
        legal_actions = self._get_legal_actions()
        return {
            action.vertex_id
            for action in legal_actions
            if isinstance(action, PlaceSettlement) and not action.free
        }

    def get_legal_city_positions(self) -> Set[int]:
        """Get set of vertex IDs where cities can be built.

        Returns:
            Set of legal vertex IDs for city upgrades
        """
        legal_actions = self._get_legal_actions()
        return {
            action.vertex_id
            for action in legal_actions
            if isinstance(action, BuildCity)
        }

    # === Construction actions ===

    def handle_build_road(self, edge_id: int) -> bool:
        """Handle road building action.

        Args:
            edge_id: Edge where road should be built

        Returns:
            True if road was built successfully, False otherwise
        """
        # Create action
        action = PlaceRoad(edge_id=edge_id, free=False)

        # Check if action is legal
        legal_actions = self._get_legal_actions()
        if action not in legal_actions:
            return False

        # Dispatch action
        self.game_service.dispatch(action)
        self.refresh_state()

        return True

    def handle_build_settlement(self, vertex_id: int) -> bool:
        """Handle settlement building action.

        Args:
            vertex_id: Vertex where settlement should be built

        Returns:
            True if settlement was built successfully, False otherwise
        """
        # Create action
        action = PlaceSettlement(vertex_id=vertex_id, free=False)

        # Check if action is legal
        legal_actions = self._get_legal_actions()
        if action not in legal_actions:
            return False

        # Dispatch action
        self.game_service.dispatch(action)
        self.refresh_state()

        return True

    def handle_build_city(self, vertex_id: int) -> bool:
        """Handle city building action (upgrade settlement to city).

        Args:
            vertex_id: Vertex where city should be built

        Returns:
            True if city was built successfully, False otherwise
        """
        # Create action
        action = BuildCity(vertex_id=vertex_id)

        # Check if action is legal
        legal_actions = self._get_legal_actions()
        if action not in legal_actions:
            return False

        # Dispatch action
        self.game_service.dispatch(action)
        self.refresh_state()

        return True

    def handle_buy_development(self) -> bool:
        """Handle development card purchase.

        Returns:
            True if card was purchased successfully, False otherwise
        """
        # Create action
        action = BuyDevelopment()

        # Check if action is legal
        legal_actions = self._get_legal_actions()
        if action not in legal_actions:
            return False

        # Dispatch action
        self.game_service.dispatch(action)
        self.refresh_state()

        return True

    # === Cost information ===

    def get_costs(self) -> Dict[str, Dict[str, int]]:
        """Get construction and purchase costs.

        Returns:
            Dictionary mapping construction type to resource costs
        """
        return {
            "road": dict(COSTS["road"]),
            "settlement": dict(COSTS["settlement"]),
            "city": dict(COSTS["city"]),
            "development": dict(COSTS["development"]),
        }


__all__ = ["ConstructionController"]
