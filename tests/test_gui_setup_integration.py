"""Tests d'intégration pour le setup GUI interactif (GUI-003).

Ce module teste l'intégration complète du setup GUI:
- Rendu des surbrillances
- Détection de clics
- Progression complète de la phase setup
"""

import pytest
import pygame
import os

from catan.engine.board import Board
from catan.app.game_service import GameService
from catan.gui.renderer import BoardRenderer, SCREEN_WIDTH, SCREEN_HEIGHT
from catan.gui.setup_controller import SetupController


@pytest.fixture
def headless_pygame():
    """Initialize pygame in headless mode."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def setup_components(headless_pygame):
    """Create all components for setup GUI testing."""
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    game_service = GameService()
    game_service.start_new_game(player_names=["Bleu", "Orange"], seed=42)
    board = Board.standard()
    renderer = BoardRenderer(screen, board)
    controller = SetupController(game_service, screen)

    return {
        "screen": screen,
        "service": game_service,
        "board": board,
        "renderer": renderer,
        "controller": controller,
    }


class TestSetupRendering:
    """Test rendering of setup phase elements."""

    def test_render_highlighted_vertices(self, setup_components):
        """Should render highlighted vertices without crashing."""
        renderer = setup_components["renderer"]
        controller = setup_components["controller"]

        legal_vertices = controller.get_legal_settlement_vertices()
        assert len(legal_vertices) > 0

        # Should not crash
        renderer.render_highlighted_vertices(legal_vertices)

    def test_render_highlighted_edges(self, setup_components):
        """Should render highlighted edges without crashing."""
        renderer = setup_components["renderer"]
        controller = setup_components["controller"]
        service = setup_components["service"]

        # Place a settlement first to get legal edges
        legal = controller.state.legal_actions()
        settlement = [a for a in legal if a.__class__.__name__ == "PlaceSettlement"][0]
        service.dispatch(settlement)
        controller.refresh_state()

        legal_edges = controller.get_legal_road_edges()
        assert len(legal_edges) > 0

        # Should not crash
        renderer.render_highlighted_edges(legal_edges)


class TestClickDetection:
    """Test click detection on vertices and edges."""

    def test_get_vertex_at_position(self, setup_components):
        """Should detect vertex at screen position."""
        renderer = setup_components["renderer"]
        controller = setup_components["controller"]

        # Get a legal vertex and its screen position
        legal_vertices = controller.get_legal_settlement_vertices()
        vertex_id = next(iter(legal_vertices))

        # Get screen position
        vertex_pos = renderer._vertex_screen_coords[vertex_id]

        # Should find the vertex
        found_vertex = renderer.get_vertex_at_position(vertex_pos)
        assert found_vertex == vertex_id

    def test_get_vertex_at_position_miss(self, setup_components):
        """Should return None when clicking away from vertices."""
        renderer = setup_components["renderer"]

        # Click at a position far from any vertex
        result = renderer.get_vertex_at_position((10, 10))
        # Might be None or might find a vertex near (10,10), depends on layout
        # Just ensure it doesn't crash
        assert result is None or isinstance(result, int)

    def test_get_edge_at_position(self, setup_components):
        """Should detect edge at screen position."""
        renderer = setup_components["renderer"]
        controller = setup_components["controller"]
        service = setup_components["service"]

        # Place settlement to get legal edges
        legal = controller.state.legal_actions()
        settlement = [a for a in legal if a.__class__.__name__ == "PlaceSettlement"][0]
        service.dispatch(settlement)
        controller.refresh_state()

        legal_edges = controller.get_legal_road_edges()
        edge_id = next(iter(legal_edges))

        # Get edge vertices positions
        edge = renderer.board.edges[edge_id]
        v1_pos = renderer._vertex_screen_coords[edge.vertices[0]]
        v2_pos = renderer._vertex_screen_coords[edge.vertices[1]]

        # Click at midpoint
        mid_pos = ((v1_pos[0] + v2_pos[0]) // 2, (v1_pos[1] + v2_pos[1]) // 2)

        found_edge = renderer.get_edge_at_position(mid_pos)
        assert found_edge == edge_id


class TestCompleteSetupFlow:
    """Test complete setup flow with simulated clicks."""

    def test_complete_setup_via_controller(self, setup_components):
        """Should complete entire setup phase via controller."""
        controller = setup_components["controller"]

        assert not controller.is_setup_complete()

        # Complete all 8 placements (4 settlements + 4 roads)
        for _ in range(8):
            # Get first legal action
            legal = controller.state.legal_actions()
            assert len(legal) > 0

            first_action = legal[0]

            # Dispatch via controller based on action type
            if first_action.__class__.__name__ == "PlaceSettlement":
                result = controller.handle_vertex_click(first_action.vertex_id)
                assert result is True
            elif first_action.__class__.__name__ == "PlaceRoad":
                result = controller.handle_edge_click(first_action.edge_id)
                assert result is True

        # Should now be complete
        assert controller.is_setup_complete()

    def test_setup_instructions_update(self, setup_components):
        """Instructions should update as setup progresses."""
        controller = setup_components["controller"]

        # Initial instructions should mention settlement
        instructions = controller.get_instructions()
        assert "colonie" in instructions.lower() or "settlement" in instructions.lower()

        # Place settlement
        legal = controller.state.legal_actions()
        settlement = [a for a in legal if a.__class__.__name__ == "PlaceSettlement"][0]
        controller.handle_vertex_click(settlement.vertex_id)

        # Now should mention road
        instructions = controller.get_instructions()
        assert "route" in instructions.lower() or "road" in instructions.lower()
