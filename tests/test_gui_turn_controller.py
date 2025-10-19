"""Tests unitaires pour TurnController (GUI-004).

Tests couvrant:
- Lancer de dés (roll dice)
- Phase de défausse (discard when hand > 9)
- Déplacement du voleur (robber move)
- Vol de ressource (stealing)
"""

import pytest
import pygame

from catan.app.game_service import GameService
from catan.engine.state import TurnSubPhase
from catan.engine.actions import RollDice, DiscardResources, MoveRobber


class TestTurnController:
    """Tests unitaires pour TurnController."""

    @pytest.fixture
    def pygame_init(self):
        """Initialize pygame in headless mode."""
        import os
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        yield
        pygame.quit()

    @pytest.fixture
    def game_service(self) -> GameService:
        """Game service with completed setup phase."""
        service = GameService()
        service.start_new_game(player_names=["Bleu", "Orange"], seed=42)

        # Complete setup phase by placing settlements and roads
        # This will transition to PLAY phase
        from catan.engine.actions import PlaceSettlement, PlaceRoad

        # Effectuer les 4 placements complets (ordre serpent)
        # Round 1: P0 -> P1
        # Round 2: P1 -> P0
        placements = [
            10,  # P0 R1
            20,  # P1 R1
            30,  # P1 R2 (serpent)
            40,  # P0 R2
        ]

        for vertex_id in placements:
            # Place settlement
            service.dispatch(PlaceSettlement(vertex_id=vertex_id, free=True))

            # Get an adjacent edge and place road
            vertex = service.state.board.vertices[vertex_id]
            edge_id = vertex.edges[0]
            service.dispatch(PlaceRoad(edge_id=edge_id, free=True))

        # Should now be in PLAY phase
        assert service.state.phase.value == "PLAY"
        assert not service.state.dice_rolled_this_turn

        return service

    @pytest.fixture
    def screen(self, pygame_init):
        """Create a pygame screen in headless mode."""
        return pygame.display.set_mode((800, 600))

    def test_controller_initialization(self, game_service, screen):
        """Test that TurnController can be initialized."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        assert controller.game_service is game_service
        assert controller.screen is screen
        assert controller.state.phase.value == "PLAY"

    def test_can_roll_dice_at_start_of_turn(self, game_service, screen):
        """Test that dice can be rolled at start of turn."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        # Should be able to roll dice
        assert controller.can_roll_dice()
        assert not controller.state.dice_rolled_this_turn

    def test_cannot_roll_dice_after_already_rolled(self, game_service, screen):
        """Test that dice cannot be rolled twice in same turn."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        # Roll dice once
        controller.handle_roll_dice()

        # Should not be able to roll again
        assert not controller.can_roll_dice()
        assert controller.state.dice_rolled_this_turn

    def test_roll_dice_updates_state(self, game_service, screen):
        """Test that rolling dice updates game state."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        # Roll dice
        result = controller.handle_roll_dice()

        # Result should be a valid dice value
        assert result is not None
        assert 2 <= result <= 12
        assert controller.state.last_dice_roll == result
        assert controller.state.dice_rolled_this_turn

    def test_roll_seven_triggers_discard_phase(self, game_service, screen):
        """Test that rolling 7 triggers discard phase if player has >9 cards."""
        from catan.gui.turn_controller import TurnController

        # Give player 0 ten cards to trigger discard
        player = game_service.state.players[0]
        player.resources["BRICK"] = 10

        controller = TurnController(game_service, screen)

        # Force roll a 7
        result = controller.handle_roll_dice(forced_value=7)

        assert result == 7
        # Should transition to discard phase
        assert controller.state.turn_subphase == TurnSubPhase.ROBBER_DISCARD
        assert 0 in controller.state.pending_discards

    def test_get_discard_requirements(self, game_service, screen):
        """Test getting discard requirements for players."""
        from catan.gui.turn_controller import TurnController

        # Give player 0 twelve cards
        player = game_service.state.players[0]
        player.resources["BRICK"] = 5
        player.resources["LUMBER"] = 7

        controller = TurnController(game_service, screen)

        # Force roll a 7
        controller.handle_roll_dice(forced_value=7)

        # Player 0 should need to discard 6 cards (12 // 2 per game rules)
        requirements = controller.get_discard_requirements()
        assert 0 in requirements
        assert requirements[0] == 6  # 12 // 2 = 6

    def test_is_in_discard_phase(self, game_service, screen):
        """Test detection of discard phase."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        # Initially not in discard phase
        assert not controller.is_in_discard_phase()

        # Give player cards and roll 7
        player = game_service.state.players[0]
        player.resources["BRICK"] = 10

        controller.handle_roll_dice(forced_value=7)

        # Now should be in discard phase
        assert controller.is_in_discard_phase()

    def test_is_in_robber_move_phase(self, game_service, screen):
        """Test detection of robber movement phase."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        # Roll a 7 without triggering discard
        controller.handle_roll_dice(forced_value=7)

        # Should be in robber move phase (no discards needed)
        assert controller.is_in_robber_move_phase()

    def test_get_legal_robber_tiles(self, game_service, screen):
        """Test getting legal tiles for robber movement."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        # Roll a 7 to enable robber move
        controller.handle_roll_dice(forced_value=7)

        # Get legal tiles
        legal_tiles = controller.get_legal_robber_tiles()

        # Should have at least some legal tiles
        assert len(legal_tiles) > 0
        # Current robber tile should not be in legal tiles
        assert controller.state.robber_tile_id not in legal_tiles

    def test_handle_robber_move(self, game_service, screen):
        """Test handling robber movement."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        # Roll a 7 to enable robber move
        controller.handle_roll_dice(forced_value=7)

        original_robber_tile = controller.state.robber_tile_id
        legal_tiles = controller.get_legal_robber_tiles()

        # Move robber to first legal tile (convert set to list to index)
        new_tile = next(iter(legal_tiles))
        success = controller.handle_robber_move(new_tile)

        assert success
        # Robber should have moved
        assert controller.state.robber_tile_id == new_tile
        assert controller.state.robber_tile_id != original_robber_tile

    def test_get_instructions_roll_dice(self, game_service, screen):
        """Test instructions at start of turn."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)

        instructions = controller.get_instructions()

        # Should prompt to roll dice
        assert "dés" in instructions.lower() or "dice" in instructions.lower()

    def test_get_instructions_discard_phase(self, game_service, screen):
        """Test instructions during discard phase."""
        from catan.gui.turn_controller import TurnController

        # Give player cards and trigger discard
        player = game_service.state.players[0]
        player.resources["BRICK"] = 10

        controller = TurnController(game_service, screen)
        controller.handle_roll_dice(forced_value=7)

        instructions = controller.get_instructions()

        # Should mention discard
        assert "défausse" in instructions.lower() or "discard" in instructions.lower()

    def test_get_instructions_robber_move(self, game_service, screen):
        """Test instructions during robber move phase."""
        from catan.gui.turn_controller import TurnController

        controller = TurnController(game_service, screen)
        controller.handle_roll_dice(forced_value=7)

        instructions = controller.get_instructions()

        # Should mention robber
        assert "voleur" in instructions.lower() or "robber" in instructions.lower()
