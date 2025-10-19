"""Tests unitaires pour HUDController (GUI-008).

Ces tests valident:
- La synchronisation des informations joueurs (ressources, cartes, scores)
- L'exposition des titres Longest Road / Largest Army
- La remontée des besoins de défausse pendant la phase ROBBER_DISCARD
- La mise à jour après une action de défausse via refresh_state()
"""

from __future__ import annotations

import os
from typing import Dict, List

import pygame
import pytest

from catan.app.game_service import GameService
from catan.engine.actions import DiscardResources
from catan.engine.state import (
    GameState,
    RESOURCE_TYPES,
    SetupPhase,
    TurnSubPhase,
)


def _empty_resources() -> Dict[str, int]:
    """Retourne un inventaire vide pour chaque ressource."""

    return {resource: 0 for resource in RESOURCE_TYPES}


def _play_ready_state() -> GameState:
    """Construit un état prêt pour les tests HUD (phase PLAY)."""

    state = GameState.new_1v1_game()
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 3
    state.current_player_id = 0
    state.dice_rolled_this_turn = True

    for player in state.players:
        player.resources = _empty_resources()
        player.roads = []
        player.settlements = []
        player.cities = []
        player.victory_points = 0
        player.hidden_victory_points = 0
        for card_type in player.dev_cards.keys():
            player.dev_cards[card_type] = 0
        for card_type in player.new_dev_cards.keys():
            player.new_dev_cards[card_type] = 0
        for card_type in player.played_dev_cards.keys():
            player.played_dev_cards[card_type] = 0

    return state


def _service_with_state(state: GameState) -> GameService:
    """Retourne un GameService initialisé avec l'état fourni."""

    service = GameService()
    service._state = state
    return service


@pytest.fixture
def pygame_screen():
    """Initialise pygame en mode headless et fournit une surface."""

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    yield screen
    pygame.quit()


class TestHUDController:
    """Tests pour le contrôleur HUD."""

    def test_player_panels_reflect_state(self, pygame_screen):
        """Les panneaux joueurs doivent refléter ressources, cartes et scores."""

        from catan.gui.hud_controller import HUDController

        state = _play_ready_state()
        state.current_player_id = 1

        player0 = state.players[0]
        player0.resources.update({"BRICK": 2, "ORE": 1})
        player0.dev_cards["KNIGHT"] = 1
        player0.new_dev_cards["YEAR_OF_PLENTY"] = 1
        player0.victory_points = 3
        player0.hidden_victory_points = 1

        player1 = state.players[1]
        player1.resources.update({"GRAIN": 4})
        player1.dev_cards["MONOPOLY"] = 2
        player1.played_dev_cards["KNIGHT"] = 3
        player1.victory_points = 5

        state.longest_road_owner = 0
        state.longest_road_length = 5
        state.largest_army_owner = 1
        state.largest_army_size = 3

        service = _service_with_state(state)
        controller = HUDController(service, pygame_screen)

        panels = controller.get_player_panels()
        assert len(panels) == 2

        panel0 = next(panel for panel in panels if panel.player_id == 0)
        panel1 = next(panel for panel in panels if panel.player_id == 1)

        assert panel0.resources["BRICK"] == 2
        assert panel0.dev_cards["KNIGHT"] == 1
        assert panel0.new_dev_cards["YEAR_OF_PLENTY"] == 1
        assert panel0.total_victory_points == 4
        assert panel0.has_longest_road is True
        assert panel0.has_largest_army is False
        assert panel0.is_current_player is False
        assert panel0.pending_discard is None

        assert panel1.resources["GRAIN"] == 4
        assert panel1.dev_cards["MONOPOLY"] == 2
        assert panel1.new_dev_cards == {}
        assert panel1.total_victory_points == 5
        assert panel1.has_longest_road is False
        assert panel1.has_largest_army is True
        assert panel1.is_current_player is True

    def test_discard_prompts_exposed(self, pygame_screen):
        """Pendant ROBBER_DISCARD, le HUD doit exposer les besoins de défausse."""

        from catan.gui.hud_controller import HUDController

        state = _play_ready_state()
        state.turn_subphase = TurnSubPhase.ROBBER_DISCARD
        state.current_player_id = 1
        state.pending_discards = {1: 3}
        state.pending_discard_queue = [1]

        state.players[1].resources.update({"BRICK": 2, "GRAIN": 2, "ORE": 1})

        service = _service_with_state(state)
        controller = HUDController(service, pygame_screen)

        panels = controller.get_player_panels()
        panel0 = next(panel for panel in panels if panel.player_id == 0)
        panel1 = next(panel for panel in panels if panel.player_id == 1)

        assert panel0.pending_discard is None
        assert panel1.pending_discard == 3
        assert controller.is_discard_prompt_active() is True

    def test_refresh_after_discard_updates_panels(self, pygame_screen):
        """Après défausse, le HUD doit refléter la disparition de l'obligation."""

        from catan.gui.hud_controller import HUDController

        state = _play_ready_state()
        state.turn_subphase = TurnSubPhase.ROBBER_DISCARD
        state.current_player_id = 0
        state.pending_discards = {0: 2}
        state.pending_discard_queue = [0]

        state.players[0].resources.update({"BRICK": 2, "GRAIN": 1})

        service = _service_with_state(state)
        controller = HUDController(service, pygame_screen)

        panels_before = controller.get_player_panels()
        panel_before = next(panel for panel in panels_before if panel.player_id == 0)
        assert panel_before.pending_discard == 2

        # Exécuter la défausse via GameService
        action = DiscardResources(resources={"BRICK": 1, "GRAIN": 1})
        service.dispatch(action)

        controller.refresh_state()
        panels_after = controller.get_player_panels()
        panel_after = next(panel for panel in panels_after if panel.player_id == 0)

        assert panel_after.pending_discard is None
        assert controller.is_discard_prompt_active() is False
        assert panel_after.resources["BRICK"] == 1
        assert panel_after.resources["GRAIN"] == 0

