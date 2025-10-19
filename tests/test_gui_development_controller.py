"""Tests unitaires pour DevelopmentController (GUI-007).

Ces tests valident:
- La séparation des cartes jouables et fraîchement achetées
- L'exécution des cartes Chevalier et Progrès via le contrôleur GUI
- La cohérence des cibles légales exposées à l'UI
"""

from __future__ import annotations

import os
from typing import Dict

import pygame
import pytest

from catan.app.game_service import GameService
from catan.engine.actions import PlayProgress
from catan.engine.state import (
    GameState,
    RESOURCE_TYPES,
    SetupPhase,
    TurnSubPhase,
)


def _empty_resources() -> Dict[str, int]:
    """Retourne un inventaire vide pour chaque ressource."""

    return {resource: 0 for resource in RESOURCE_TYPES}


def _fresh_play_state() -> GameState:
    """Construit un état prêt pour les tests GUI en phase PLAY."""

    state = GameState.new_1v1_game()
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 1
    state.current_player_id = 0
    state.dice_rolled_this_turn = True

    for player in state.players:
        player.resources = _empty_resources()
        player.roads = []
        player.settlements = []
        player.cities = []
        player.victory_points = 0
        player.hidden_victory_points = 0
        for card in player.dev_cards.keys():
            player.dev_cards[card] = 0
        for card in player.new_dev_cards.keys():
            player.new_dev_cards[card] = 0
        for card in player.played_dev_cards.keys():
            player.played_dev_cards[card] = 0

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


class TestDevelopmentController:
    """Tests du contrôleur de cartes de développement."""

    def test_card_counts_separate_new_and_playable(self, pygame_screen):
        """Les cartes jouables ne doivent pas inclure les cartes fraîchement achetées."""

        from catan.gui.development_controller import DevelopmentController

        state = _fresh_play_state()
        player = state.players[0]
        player.dev_cards["KNIGHT"] = 1
        player.new_dev_cards["YEAR_OF_PLENTY"] = 1

        service = _service_with_state(state)
        controller = DevelopmentController(service, pygame_screen)

        playable = controller.get_playable_cards()
        assert playable.get("KNIGHT") == 1
        assert "YEAR_OF_PLENTY" not in playable

        new_cards = controller.get_new_cards()
        assert new_cards.get("YEAR_OF_PLENTY") == 1

    def test_handle_play_knight_triggers_robber_phase(self, pygame_screen):
        """Jouer un chevalier doit déclencher la phase de déplacement du voleur."""

        from catan.gui.development_controller import DevelopmentController

        state = _fresh_play_state()
        player = state.players[0]
        player.dev_cards["KNIGHT"] = 1

        service = _service_with_state(state)
        controller = DevelopmentController(service, pygame_screen)

        assert controller.handle_play_knight()

        updated_state = service.state
        updated_player = updated_state.players[0]

        assert updated_state.turn_subphase == TurnSubPhase.ROBBER_MOVE
        assert updated_state.current_player_id == 0
        assert updated_player.dev_cards["KNIGHT"] == 0
        assert updated_player.played_dev_cards["KNIGHT"] == 1

    def test_handle_play_knight_rejects_new_card(self, pygame_screen):
        """Un chevalier fraîchement acheté ne doit pas être jouable par le contrôleur."""

        from catan.gui.development_controller import DevelopmentController

        state = _fresh_play_state()
        player = state.players[0]
        player.new_dev_cards["KNIGHT"] = 1

        service = _service_with_state(state)
        controller = DevelopmentController(service, pygame_screen)

        assert not controller.handle_play_knight()
        assert service.state.turn_subphase == TurnSubPhase.MAIN
        assert service.state.players[0].new_dev_cards["KNIGHT"] == 1

    def test_get_legal_road_building_targets_matches_state(self, pygame_screen):
        """Les cibles routes gratuites doivent correspondre aux actions légales du moteur."""

        from catan.gui.development_controller import DevelopmentController

        state = _fresh_play_state()
        player = state.players[0]
        opponent = state.players[1]

        player.dev_cards["ROAD_BUILDING"] = 1
        player.settlements = [10]
        player.roads = [8]
        opponent.settlements = [30]
        opponent.roads = [35]

        service = _service_with_state(state)
        controller = DevelopmentController(service, pygame_screen)

        legal_from_state = sorted(
            tuple(action.edges or [])
            for action in state.legal_actions()
            if isinstance(action, PlayProgress) and action.card == "ROAD_BUILDING"
        )
        assert legal_from_state, "Le moteur doit annoncer au moins une combinaison de routes"

        targets = controller.get_legal_road_building_targets()
        assert sorted(tuple(target) for target in targets) == legal_from_state

    def test_handle_play_road_building_places_roads(self, pygame_screen):
        """Le contrôleur doit jouer Road Building et poser deux routes."""

        from catan.gui.development_controller import DevelopmentController

        state = _fresh_play_state()
        player = state.players[0]
        opponent = state.players[1]

        player.dev_cards["ROAD_BUILDING"] = 1
        player.settlements = [10]
        player.roads = [8]
        opponent.settlements = [30]
        opponent.roads = [35]

        service = _service_with_state(state)
        controller = DevelopmentController(service, pygame_screen)

        targets = controller.get_legal_road_building_targets()
        assert targets

        chosen = list(targets[0])
        assert controller.handle_play_road_building(chosen)

        updated_player = service.state.players[0]
        for edge_id in chosen:
            assert edge_id in updated_player.roads
        assert updated_player.dev_cards["ROAD_BUILDING"] == 0

    def test_handle_play_year_of_plenty_grants_resources(self, pygame_screen):
        """Year of Plenty doit ajouter les ressources choisies et retirer la carte."""

        from catan.gui.development_controller import DevelopmentController

        state = _fresh_play_state()
        player = state.players[0]
        player.dev_cards["YEAR_OF_PLENTY"] = 1

        service = _service_with_state(state)
        controller = DevelopmentController(service, pygame_screen)

        options = controller.get_legal_year_of_plenty_options()
        assert options

        choice = options[0]
        assert controller.handle_play_year_of_plenty(choice)

        updated_state = service.state
        updated_player = updated_state.players[0]
        for resource, amount in choice.items():
            assert updated_player.resources[resource] == amount
        assert updated_player.dev_cards["YEAR_OF_PLENTY"] == 0

    def test_handle_play_monopoly_collects_resources(self, pygame_screen):
        """Monopoly doit collecter toutes les ressources ciblées chez l'adversaire."""

        from catan.gui.development_controller import DevelopmentController

        state = _fresh_play_state()
        player = state.players[0]
        opponent = state.players[1]

        player.dev_cards["MONOPOLY"] = 1
        opponent.resources["BRICK"] = 2
        opponent.resources["ORE"] = 1

        service = _service_with_state(state)
        controller = DevelopmentController(service, pygame_screen)

        legal_resources = controller.get_legal_monopoly_resources()
        assert set(legal_resources) == set(RESOURCE_TYPES)

        assert controller.handle_play_monopoly("BRICK")

        updated_player = service.state.players[0]
        updated_opponent = service.state.players[1]
        assert updated_player.resources["BRICK"] == 2
        assert updated_opponent.resources["BRICK"] == 0
        assert updated_player.dev_cards["MONOPOLY"] == 0
