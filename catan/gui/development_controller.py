"""Contrôleur GUI pour les cartes de développement (GUI-007).

Ce module expose les opérations nécessaires pour:
- Lister les cartes de développement jouables vs fraîchement achetées
- Déclencher les actions `PlayKnight` et `PlayProgress` (Road Building, Year of Plenty, Monopoly)
- Fournir à l'UI les combinaisons légales pertinentes (routes à placer, ressources à choisir)

Conforme aux specs docs/gui-h2h.md (sections 2, 5) et au moteur `catan.engine.state`.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import pygame

from catan.app.game_service import GameService
from catan.engine.actions import Action, PlayKnight, PlayProgress
from catan.engine.state import GameState


class DevelopmentController:
    """Contrôleur dédié aux cartes de développement."""

    def __init__(self, game_service: GameService, screen: pygame.Surface) -> None:
        """Initialise le contrôleur.

        Args:
            game_service: Service orchestrant la partie Catane
            screen: Surface pygame utilisée par la GUI (référence conservée)
        """

        self.game_service = game_service
        self.screen = screen
        self.state: GameState = game_service.state
        self._legal_actions_cache: Optional[List[Action]] = None

    # -- Synchronisation -------------------------------------------------

    def refresh_state(self) -> None:
        """Met à jour le pointeur d'état et invalide le cache des actions légales."""

        self.state = self.game_service.state
        self._legal_actions_cache = None

    def _get_legal_actions(self) -> List[Action]:
        """Retourne la liste des actions légales en cachant le résultat."""

        if self._legal_actions_cache is None:
            self._legal_actions_cache = self.state.legal_actions()
        return self._legal_actions_cache

    # -- Inventaires de cartes -------------------------------------------

    def get_playable_cards(self) -> Dict[str, int]:
        """Retourne les cartes de développement jouables (hors nouveautés)."""

        player = self.state.players[self.state.current_player_id]
        return {
            card: count
            for card, count in player.dev_cards.items()
            if count > 0
        }

    def get_new_cards(self) -> Dict[str, int]:
        """Retourne les cartes fraîchement achetées (non jouables ce tour)."""

        player = self.state.players[self.state.current_player_id]
        return {
            card: count
            for card, count in player.new_dev_cards.items()
            if count > 0
        }

    # -- Chevaliers ------------------------------------------------------

    def can_play_knight(self) -> bool:
        """Indique si l'action PlayKnight est actuellement légale."""

        return any(isinstance(action, PlayKnight) for action in self._get_legal_actions())

    def handle_play_knight(self) -> bool:
        """Déclenche la carte Chevalier si elle est légale."""

        if not self.can_play_knight():
            return False

        self.game_service.dispatch(PlayKnight())
        self.refresh_state()
        return True

    # -- Road Building ---------------------------------------------------

    def get_legal_road_building_targets(self) -> List[Tuple[int, int]]:
        """Retourne les couples d'arêtes disponibles pour Road Building."""

        targets: List[Tuple[int, int]] = []
        for action in self._get_legal_actions():
            if not isinstance(action, PlayProgress):
                continue
            if action.card != "ROAD_BUILDING":
                continue
            edges = tuple(action.edges or [])
            if len(edges) != 2:
                continue
            targets.append(edges)
        return targets

    def handle_play_road_building(self, edges: Sequence[int]) -> bool:
        """Joue Road Building en choisissant deux arêtes à placer."""

        if len(edges) != 2:
            return False

        normalized = tuple(sorted(int(edge) for edge in edges))

        for action in self._get_legal_actions():
            if not isinstance(action, PlayProgress) or action.card != "ROAD_BUILDING":
                continue
            candidate_edges = tuple(sorted((action.edges or [])))
            if candidate_edges != normalized:
                continue
            self.game_service.dispatch(action)
            self.refresh_state()
            return True

        return False

    # -- Year of Plenty --------------------------------------------------

    def get_legal_year_of_plenty_options(self) -> List[Dict[str, int]]:
        """Retourne les combinaisons de ressources disponibles pour Year of Plenty."""

        options: List[Dict[str, int]] = []
        for action in self._get_legal_actions():
            if not isinstance(action, PlayProgress) or action.card != "YEAR_OF_PLENTY":
                continue
            resources = dict(action.resources or {})
            if resources not in options:
                options.append(resources)
        return options

    def handle_play_year_of_plenty(self, resources: Dict[str, int]) -> bool:
        """Déclenche Year of Plenty avec la combinaison fournie."""

        normalized = {res: amount for res, amount in resources.items() if amount > 0}

        for action in self._get_legal_actions():
            if not isinstance(action, PlayProgress) or action.card != "YEAR_OF_PLENTY":
                continue
            candidate = dict(action.resources or {})
            if candidate != normalized:
                continue
            self.game_service.dispatch(action)
            self.refresh_state()
            return True

        return False

    # -- Monopoly --------------------------------------------------------

    def get_legal_monopoly_resources(self) -> List[str]:
        """Retourne la liste des ressources ciblables par Monopoly."""

        resources: List[str] = []
        for action in self._get_legal_actions():
            if not isinstance(action, PlayProgress) or action.card != "MONOPOLY":
                continue
            resource = action.resource or ""
            if resource and resource not in resources:
                resources.append(resource)
        return resources

    def handle_play_monopoly(self, resource: str) -> bool:
        """Déclenche Monopoly sur la ressource indiquée."""

        if not resource:
            return False

        for action in self._get_legal_actions():
            if not isinstance(action, PlayProgress) or action.card != "MONOPOLY":
                continue
            if action.resource != resource:
                continue
            self.game_service.dispatch(action)
            self.refresh_state()
            return True

        return False


__all__ = ["DevelopmentController"]
