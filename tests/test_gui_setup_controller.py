"""Tests pour le contrôleur de setup GUI (GUI-003).

Ce module teste l'interaction utilisateur durant la phase de placement initial.
Conforme aux specs docs/gui-h2h.md section "1. Phase de placement serpent".

Tests headless (pas de fenêtre pygame réelle).
"""

import pytest
import pygame
from typing import List

from catan.engine.board import Board
from catan.engine.state import GameState, SetupPhase
from catan.engine.actions import PlaceSettlement, PlaceRoad, Action
from catan.app.game_service import GameService
from catan.gui.setup_controller import SetupController


@pytest.fixture
def headless_pygame():
    """Initialize pygame in headless mode."""
    import os
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def game_service():
    """Create a fresh game service for setup testing."""
    service = GameService()
    service.start_new_game(player_names=["Bleu", "Orange"], seed=42)
    return service


@pytest.fixture
def mock_screen(headless_pygame):
    """Create a dummy pygame surface."""
    return pygame.display.set_mode((800, 600))


class TestSetupControllerInit:
    """Test initialization of setup controller."""

    def test_controller_initializes_with_service(self, game_service, mock_screen):
        """Controller should initialize with game service and screen."""
        controller = SetupController(game_service, mock_screen)
        assert controller.game_service == game_service
        assert controller.screen == mock_screen
        assert controller.state is not None

    def test_controller_identifies_setup_phase(self, game_service, mock_screen):
        """Controller should recognize when game is in setup phase."""
        controller = SetupController(game_service, mock_screen)
        assert controller.state.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2)


class TestLegalPositionHighlighting:
    """Test highlighting of legal positions during setup."""

    def test_legal_settlements_highlighted_at_start(self, game_service, mock_screen):
        """All vertices should be highlighted as legal for first placement."""
        controller = SetupController(game_service, mock_screen)
        legal_vertices = controller.get_legal_settlement_vertices()

        # First placement: many vertices should be legal
        assert len(legal_vertices) > 0
        # Should be consistent with engine's legal_actions
        legal_actions = controller.state.legal_actions()
        settlement_actions = [a for a in legal_actions if isinstance(a, PlaceSettlement)]
        assert len(settlement_actions) == len(legal_vertices)

    def test_legal_roads_highlighted_after_settlement(self, game_service, mock_screen):
        """After placing settlement, only adjacent edges should be highlighted."""
        controller = SetupController(game_service, mock_screen)

        # Place a settlement
        legal_actions = controller.state.legal_actions()
        settlement_action = next(a for a in legal_actions if isinstance(a, PlaceSettlement))
        game_service.dispatch(settlement_action)

        # Update controller state
        controller.refresh_state()

        # Now we should be waiting for a road
        legal_edges = controller.get_legal_road_edges()
        assert len(legal_edges) > 0

        # Verify these match engine's legal actions
        legal_actions = controller.state.legal_actions()
        road_actions = [a for a in legal_actions if isinstance(a, PlaceRoad)]
        assert len(road_actions) == len(legal_edges)


class TestUserInteraction:
    """Test user click handling during setup."""

    def test_click_on_legal_vertex_places_settlement(self, game_service, mock_screen):
        """Clicking on a legal vertex should place a settlement."""
        controller = SetupController(game_service, mock_screen)

        # Get a legal settlement position
        legal_actions = controller.state.legal_actions()
        settlement_action = next(a for a in legal_actions if isinstance(a, PlaceSettlement))
        vertex_id = settlement_action.vertex_id

        # Simulate click on that vertex
        result = controller.handle_vertex_click(vertex_id)

        # Should return True indicating action was taken
        assert result is True

        # State should have updated
        controller.refresh_state()
        # Now expecting road placement
        legal_actions = controller.state.legal_actions()
        assert all(isinstance(a, PlaceRoad) for a in legal_actions)

    def test_click_on_illegal_vertex_ignored(self, game_service, mock_screen):
        """Clicking on an illegal vertex should be ignored."""
        controller = SetupController(game_service, mock_screen)

        # Get all legal vertices
        legal_actions = controller.state.legal_actions()
        legal_vertices = {a.vertex_id for a in legal_actions if isinstance(a, PlaceSettlement)}

        # Find an illegal vertex (one that's too close to a legal one)
        # For now, just use vertex 999 which doesn't exist
        result = controller.handle_vertex_click(999)

        # Should return False or None indicating no action
        assert result is False or result is None

    def test_click_on_legal_edge_places_road(self, game_service, mock_screen):
        """Clicking on a legal edge should place a road."""
        controller = SetupController(game_service, mock_screen)

        # First place a settlement
        legal_actions = controller.state.legal_actions()
        settlement_action = next(a for a in legal_actions if isinstance(a, PlaceSettlement))
        game_service.dispatch(settlement_action)
        controller.refresh_state()

        # Now click on a legal edge
        legal_actions = controller.state.legal_actions()
        road_action = next(a for a in legal_actions if isinstance(a, PlaceRoad))
        edge_id = road_action.edge_id

        result = controller.handle_edge_click(edge_id)
        assert result is True


class TestSetupProgression:
    """Test progression through setup phases."""

    def test_setup_round_1_to_round_2_transition(self, game_service, mock_screen):
        """After both players place in round 1, should transition to round 2."""
        controller = SetupController(game_service, mock_screen)

        assert controller.state.phase == SetupPhase.SETUP_ROUND_1

        # Player 0 places settlement + road
        for _ in range(2):
            legal = controller.state.legal_actions()
            game_service.dispatch(legal[0])
            controller.refresh_state()

        # Player 1 places settlement + road
        for _ in range(2):
            legal = controller.state.legal_actions()
            game_service.dispatch(legal[0])
            controller.refresh_state()

        # Should now be in SETUP_ROUND_2
        assert controller.state.phase == SetupPhase.SETUP_ROUND_2

    def test_setup_round_2_has_reversed_order(self, game_service, mock_screen):
        """Round 2 should start with player 1 (reversed)."""
        controller = SetupController(game_service, mock_screen)

        # Complete round 1
        for _ in range(4):  # 2 actions per player, 2 players
            legal = controller.state.legal_actions()
            game_service.dispatch(legal[0])
            controller.refresh_state()

        # Now in round 2, should be player 1's turn
        assert controller.state.current_player_id == 1

    def test_complete_setup_transitions_to_play(self, game_service, mock_screen):
        """After all placements, should transition to PLAY phase."""
        controller = SetupController(game_service, mock_screen)

        # Complete all 8 placements (2 settlements + 2 roads per player)
        for _ in range(8):
            legal = controller.state.legal_actions()
            if legal:
                game_service.dispatch(legal[0])
                controller.refresh_state()

        # Should no longer be in setup
        assert controller.state.phase not in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2)


class TestInstructions:
    """Test that controller provides correct instructions to players."""

    def test_instructions_show_current_player(self, game_service, mock_screen):
        """Instructions should indicate which player's turn it is."""
        controller = SetupController(game_service, mock_screen)
        instructions = controller.get_instructions()

        # Should mention the current player
        current_player = controller.state.players[controller.state.current_player_id]
        assert current_player.name in instructions

    def test_instructions_indicate_settlement_or_road(self, game_service, mock_screen):
        """Instructions should tell player whether to place settlement or road."""
        controller = SetupController(game_service, mock_screen)

        # Initially should ask for settlement
        instructions = controller.get_instructions()
        assert "colonie" in instructions.lower() or "settlement" in instructions.lower()

        # After placing settlement
        legal = controller.state.legal_actions()
        settlement = next(a for a in legal if isinstance(a, PlaceSettlement))
        game_service.dispatch(settlement)
        controller.refresh_state()

        # Should now ask for road
        instructions = controller.get_instructions()
        assert "route" in instructions.lower() or "road" in instructions.lower()

    def test_instructions_indicate_round_number(self, game_service, mock_screen):
        """Instructions should indicate whether it's round 1 or 2."""
        controller = SetupController(game_service, mock_screen)

        instructions = controller.get_instructions()
        # Should mention round or first/second placement
        assert "1" in instructions or "premier" in instructions.lower() or "first" in instructions.lower()
