"""Contrôleur HUD pour la GUI Catane (GUI-008).

Responsabilités:
- Fournir les données synchronisées des joueurs (ressources, cartes, scores)
- Indiquer les titres Longest Road / Largest Army détenus
- Exposer les obligations de défausse pendant ROBBER_DISCARD

La logique reste headless: aucun rendu pygame, uniquement des structures de
données prêtes à consommer par la couche de présentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pygame

from catan.app.game_service import GameService
from catan.engine.state import GameState, Player, TurnSubPhase


@dataclass(frozen=True)
class PlayerPanel:
    """Données pour l'affichage HUD d'un joueur."""

    player_id: int
    name: str
    is_current_player: bool
    resources: Dict[str, int]
    dev_cards: Dict[str, int]
    new_dev_cards: Dict[str, int]
    played_knights: int
    victory_points: int
    hidden_victory_points: int
    total_victory_points: int
    has_longest_road: bool
    has_largest_army: bool
    pending_discard: Optional[int]
    hand_size: int


class HUDController:
    """Contrôleur fournissant les données du HUD GUI."""

    def __init__(self, game_service: GameService, screen: pygame.Surface) -> None:
        self.game_service = game_service
        self.screen = screen
        self.state: GameState = game_service.state

    def refresh_state(self) -> None:
        """Synchronise le contrôleur avec l'état courant du GameService."""

        self.state = self.game_service.state

    def get_player_panels(self) -> List[PlayerPanel]:
        """Retourne les panneaux HUD pour chaque joueur."""

        panels: List[PlayerPanel] = []
        for player in self.state.players:
            panels.append(self._build_panel(player))
        return panels

    def is_discard_prompt_active(self) -> bool:
        """Indique si une phase de défausse est en cours."""

        return (
            self.state.turn_subphase == TurnSubPhase.ROBBER_DISCARD
            and bool(self.state.pending_discards)
        )

    def _build_panel(self, player: Player) -> PlayerPanel:
        """Construit les données HUD pour un joueur donné."""

        player_id = player.player_id
        is_current = self.state.current_player_id == player_id

        resources = dict(player.resources)
        dev_cards = {card: count for card, count in player.dev_cards.items() if count > 0}
        new_dev_cards = {
            card: count for card, count in player.new_dev_cards.items() if count > 0
        }

        victory_points = player.victory_points
        hidden_victory_points = player.hidden_victory_points
        total_vp = victory_points + hidden_victory_points

        has_longest = self.state.longest_road_owner == player_id
        has_largest = self.state.largest_army_owner == player_id

        pending_discard: Optional[int] = None
        if self.state.turn_subphase == TurnSubPhase.ROBBER_DISCARD:
            pending_discard = self.state.pending_discards.get(player_id)

        hand_size = sum(resources.values())
        played_knights = player.played_dev_cards.get("KNIGHT", 0)

        return PlayerPanel(
            player_id=player_id,
            name=player.name,
            is_current_player=is_current,
            resources=resources,
            dev_cards=dev_cards,
            new_dev_cards=new_dev_cards,
            played_knights=played_knights,
            victory_points=victory_points,
            hidden_victory_points=hidden_victory_points,
            total_victory_points=total_vp,
            has_longest_road=has_longest,
            has_largest_army=has_largest,
            pending_discard=pending_discard,
            hand_size=hand_size,
        )


__all__ = ["HUDController", "PlayerPanel"]

