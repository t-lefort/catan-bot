"""Tests unitaires pour le contrôleur de construction GUI (GUI-006).

Ces tests couvrent:
- Construction de routes, colonies, villes
- Achat de cartes de développement
- Validation des coûts en temps réel
- Affichage des positions légales pour construction
"""

import pytest
import pygame

from catan.app.game_service import GameService
from catan.gui.construction_controller import ConstructionController
from catan.engine.state import GameState, Player, SetupPhase, TurnSubPhase, DEV_CARD_TYPES
from catan.engine.board import Board
from catan.engine.actions import PlaceSettlement, PlaceRoad, BuildCity, BuyDevelopment


@pytest.fixture
def pygame_init():
    """Initialize pygame for tests."""
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    yield screen
    pygame.quit()


@pytest.fixture
def game_in_play(pygame_init):
    """Create a game state in PLAY phase with resources for testing."""
    state = GameState.new_1v1_game(seed=42)

    # Complete the setup phase properly using legal actions
    legal = state.legal_actions()
    # Place first settlement for player 0
    settlement_actions = [a for a in legal if isinstance(a, PlaceSettlement)]
    state = state.apply_action(settlement_actions[0])

    # Place first road for player 0
    legal = state.legal_actions()
    road_actions = [a for a in legal if isinstance(a, PlaceRoad)]
    state = state.apply_action(road_actions[0])

    # Place first settlement for player 1
    legal = state.legal_actions()
    settlement_actions = [a for a in legal if isinstance(a, PlaceSettlement)]
    state = state.apply_action(settlement_actions[0])

    # Place first road for player 1
    legal = state.legal_actions()
    road_actions = [a for a in legal if isinstance(a, PlaceRoad)]
    state = state.apply_action(road_actions[0])

    # Place second settlement for player 1 (reverse order in round 2)
    legal = state.legal_actions()
    settlement_actions = [a for a in legal if isinstance(a, PlaceSettlement)]
    state = state.apply_action(settlement_actions[0])

    # Place second road for player 1
    legal = state.legal_actions()
    road_actions = [a for a in legal if isinstance(a, PlaceRoad)]
    state = state.apply_action(road_actions[0])

    # Place second settlement for player 0
    legal = state.legal_actions()
    settlement_actions = [a for a in legal if isinstance(a, PlaceSettlement)]
    state = state.apply_action(settlement_actions[0])

    # Place second road for player 0
    legal = state.legal_actions()
    road_actions = [a for a in legal if isinstance(a, PlaceRoad)]
    state = state.apply_action(road_actions[0])

    # Now should be in PLAY phase
    assert state.phase == SetupPhase.PLAY

    # Roll dice to start the game
    from catan.engine.actions import RollDice
    state = state.apply_action(RollDice())

    # Give players plenty of resources for testing (after rolling dice)
    state.players[0].resources = {
        "BRICK": 10,
        "LUMBER": 10,
        "WOOL": 10,
        "GRAIN": 10,
        "ORE": 10,
    }
    state.players[1].resources = {
        "BRICK": 10,
        "LUMBER": 10,
        "WOOL": 10,
        "GRAIN": 10,
        "ORE": 10,
    }

    service = GameService()
    service._state = state

    controller = ConstructionController(service, pygame_init)

    return controller, service, state


def test_can_afford_checks_resources(game_in_play):
    """Test that can_afford correctly checks player resources."""
    controller, service, state = game_in_play

    # Player has 5 of each resource
    assert controller.can_afford_road()
    assert controller.can_afford_settlement()
    assert controller.can_afford_city()
    assert controller.can_afford_development()

    # Remove resources
    state.players[0].resources = {"BRICK": 0, "LUMBER": 0, "WOOL": 0, "GRAIN": 0, "ORE": 0}
    controller.refresh_state()

    assert not controller.can_afford_road()
    assert not controller.can_afford_settlement()
    assert not controller.can_afford_city()
    assert not controller.can_afford_development()


def test_can_afford_road_exact_resources(game_in_play):
    """Test can_afford_road with exact resources."""
    controller, service, state = game_in_play

    # Exactly enough for a road (BRICK:1, LUMBER:1)
    state.players[0].resources = {"BRICK": 1, "LUMBER": 1, "WOOL": 0, "GRAIN": 0, "ORE": 0}
    controller.refresh_state()

    assert controller.can_afford_road()
    assert not controller.can_afford_settlement()


def test_can_afford_settlement_exact_resources(game_in_play):
    """Test can_afford_settlement with exact resources."""
    controller, service, state = game_in_play

    # Exactly enough for settlement (BRICK:1, LUMBER:1, WOOL:1, GRAIN:1)
    state.players[0].resources = {"BRICK": 1, "LUMBER": 1, "WOOL": 1, "GRAIN": 1, "ORE": 0}
    controller.refresh_state()

    assert controller.can_afford_road()  # Has BRICK:1 + LUMBER:1
    assert controller.can_afford_settlement()
    assert not controller.can_afford_city()


def test_can_afford_city_exact_resources(game_in_play):
    """Test can_afford_city with exact resources."""
    controller, service, state = game_in_play

    # Exactly enough for city (GRAIN:2, ORE:3)
    state.players[0].resources = {"BRICK": 0, "LUMBER": 0, "WOOL": 0, "GRAIN": 2, "ORE": 3}
    controller.refresh_state()

    assert not controller.can_afford_road()
    assert not controller.can_afford_settlement()
    assert controller.can_afford_city()


def test_can_afford_development_exact_resources(game_in_play):
    """Test can_afford_development with exact resources."""
    controller, service, state = game_in_play

    # Exactly enough for development card (WOOL:1, GRAIN:1, ORE:1)
    state.players[0].resources = {"BRICK": 0, "LUMBER": 0, "WOOL": 1, "GRAIN": 1, "ORE": 1}
    controller.refresh_state()

    assert not controller.can_afford_road()
    assert not controller.can_afford_settlement()
    assert not controller.can_afford_city()
    assert controller.can_afford_development()


def test_get_legal_road_positions(game_in_play):
    """Test getting legal road positions."""
    controller, service, state = game_in_play

    legal_edges = controller.get_legal_road_positions()

    # Should return set of edge IDs
    assert isinstance(legal_edges, set)
    # Player has resources and existing roads/settlements, should have legal positions
    assert len(legal_edges) > 0


def test_get_legal_settlement_positions(game_in_play):
    """Test getting legal settlement positions."""
    controller, service, state = game_in_play

    legal_vertices = controller.get_legal_settlement_positions()

    # Should return set of vertex IDs
    assert isinstance(legal_vertices, set)
    # Settlements have distance rules, might be empty or have positions


def test_get_legal_city_positions(game_in_play):
    """Test getting legal city positions."""
    controller, service, state = game_in_play

    legal_vertices = controller.get_legal_city_positions()

    # Should return set of vertex IDs with player's settlements
    assert isinstance(legal_vertices, set)
    # Player 0 has settlements (from setup), should have some legal city positions
    player0_settlements = state.players[0].settlements
    # At least some of the settlements should be upgradeable to cities
    for settlement_id in player0_settlements:
        if settlement_id in legal_vertices:
            # Found at least one - test passes
            assert True
            return
    # If player has settlements, at least one should be upgradeable
    if len(player0_settlements) > 0:
        pytest.fail(f"Player has settlements {player0_settlements} but no legal city positions")


def test_handle_build_road_success(game_in_play):
    """Test successful road building."""
    controller, service, state = game_in_play

    # Get a legal edge
    legal_edges = controller.get_legal_road_positions()
    if not legal_edges:
        pytest.skip("No legal road positions available")

    edge_id = next(iter(legal_edges))
    initial_resources = dict(state.players[0].resources)

    # Build road
    result = controller.handle_build_road(edge_id)

    assert result is True
    # Get updated state from controller
    new_state = controller.state
    assert edge_id in new_state.players[0].roads
    # Resources should be deducted
    assert new_state.players[0].resources["BRICK"] == initial_resources["BRICK"] - 1
    assert new_state.players[0].resources["LUMBER"] == initial_resources["LUMBER"] - 1


def test_handle_build_road_invalid_position(game_in_play):
    """Test building road at invalid position."""
    controller, service, state = game_in_play

    # Try to build at edge 99 (likely invalid)
    result = controller.handle_build_road(999)

    assert result is False


def test_handle_build_settlement_success(game_in_play):
    """Test successful settlement building.

    To build a new settlement during play phase, we need to:
    1. Build roads to reach a position at distance from existing settlements
    2. Then build the settlement at the new position
    """
    controller, service, state = game_in_play

    # First, build roads to create new legal settlement positions
    roads_built = 0
    max_roads = 3  # Try building up to 3 roads to reach a new position

    for _ in range(max_roads):
        legal_edges = controller.get_legal_road_positions()
        if not legal_edges:
            break

        # Build a road
        edge_id = next(iter(legal_edges))
        controller.handle_build_road(edge_id)
        roads_built += 1

        # Check if we now have legal settlement positions
        legal_vertices = controller.get_legal_settlement_positions()
        if legal_vertices:
            break

    # Now try to build a settlement
    legal_vertices = controller.get_legal_settlement_positions()
    if not legal_vertices:
        pytest.skip(f"No legal settlement positions available after building {roads_built} roads")

    vertex_id = next(iter(legal_vertices))
    initial_resources = dict(controller.state.players[0].resources)

    # Build settlement
    result = controller.handle_build_settlement(vertex_id)

    assert result is True
    # Get updated state from controller
    new_state = controller.state
    assert vertex_id in new_state.players[0].settlements
    # Resources should be deducted
    assert new_state.players[0].resources["BRICK"] == initial_resources["BRICK"] - 1
    assert new_state.players[0].resources["LUMBER"] == initial_resources["LUMBER"] - 1
    assert new_state.players[0].resources["WOOL"] == initial_resources["WOOL"] - 1
    assert new_state.players[0].resources["GRAIN"] == initial_resources["GRAIN"] - 1


def test_handle_build_city_success(game_in_play):
    """Test successful city building."""
    controller, service, state = game_in_play

    # Get a legal city position (one of player 0's settlements)
    legal_vertices = controller.get_legal_city_positions()
    if not legal_vertices:
        pytest.skip("No legal city positions available")

    vertex_id = next(iter(legal_vertices))
    initial_resources = dict(state.players[0].resources)
    initial_settlements = list(state.players[0].settlements)
    initial_cities = list(state.players[0].cities)

    # Build city
    result = controller.handle_build_city(vertex_id)

    assert result is True
    # Get updated state from controller (handle_build_city calls refresh_state)
    new_state = controller.state
    # Settlement should be removed, city should be added
    assert vertex_id not in new_state.players[0].settlements
    assert vertex_id in new_state.players[0].cities
    # Resources should be deducted
    assert new_state.players[0].resources["GRAIN"] == initial_resources["GRAIN"] - 2
    assert new_state.players[0].resources["ORE"] == initial_resources["ORE"] - 3


def test_handle_build_city_no_settlement(game_in_play):
    """Test building city where no settlement exists."""
    controller, service, state = game_in_play

    # Try to build city at vertex without settlement
    result = controller.handle_build_city(50)

    assert result is False


def test_handle_buy_development_success(game_in_play):
    """Test successful development card purchase."""
    controller, service, state = game_in_play

    # Ensure there are dev cards in the deck
    if len(state.dev_deck) == 0:
        pytest.skip("Dev deck is empty")

    # Ensure player has enough resources (fixture may have rolled dice which changed resources)
    state.players[0].resources = {
        "BRICK": 10,
        "LUMBER": 10,
        "WOOL": 10,
        "GRAIN": 10,
        "ORE": 10,
    }
    controller.refresh_state()

    initial_resources = dict(state.players[0].resources)
    initial_dev_cards = sum(state.players[0].new_dev_cards.values())

    # Buy development card
    result = controller.handle_buy_development()

    assert result is True
    # Get updated state from controller
    new_state = controller.state
    # Resources should be deducted
    assert new_state.players[0].resources["WOOL"] == initial_resources["WOOL"] - 1
    assert new_state.players[0].resources["GRAIN"] == initial_resources["GRAIN"] - 1
    assert new_state.players[0].resources["ORE"] == initial_resources["ORE"] - 1
    # Should have one more dev card in new_dev_cards
    assert sum(new_state.players[0].new_dev_cards.values()) == initial_dev_cards + 1


def test_handle_buy_development_insufficient_resources(game_in_play):
    """Test buying development card without enough resources."""
    controller, service, state = game_in_play

    # Remove resources
    state.players[0].resources = {"BRICK": 0, "LUMBER": 0, "WOOL": 0, "GRAIN": 0, "ORE": 0}
    controller.refresh_state()

    result = controller.handle_buy_development()

    assert result is False


def test_get_costs_returns_correct_structure(game_in_play):
    """Test that get_costs returns expected structure."""
    controller, service, state = game_in_play

    costs = controller.get_costs()

    assert "road" in costs
    assert "settlement" in costs
    assert "city" in costs
    assert "development" in costs

    # Check structure of road cost
    assert isinstance(costs["road"], dict)
    assert "BRICK" in costs["road"]
    assert "LUMBER" in costs["road"]


def test_construction_during_wrong_phase(pygame_init):
    """Test that construction is blocked during non-PLAY phases."""
    board = Board.standard()
    players = [Player(player_id=0, name="Alice"), Player(player_id=1, name="Bob")]
    state = GameState(
        board=board,
        players=players,
        phase=SetupPhase.SETUP_ROUND_1,
        current_player_id=0,
    )

    service = GameService()
    service._state = state
    controller = ConstructionController(service, pygame_init)

    # Even with resources, construction should fail in SETUP
    state.players[0].resources = {"BRICK": 10, "LUMBER": 10, "WOOL": 10, "GRAIN": 10, "ORE": 10}

    result = controller.handle_build_road(0)
    assert result is False


def test_refresh_state_clears_cache(game_in_play):
    """Test that refresh_state clears the legal actions cache."""
    controller, service, state = game_in_play

    # Get legal positions (populates cache)
    legal_roads_1 = controller.get_legal_road_positions()

    # Modify state (remove resources)
    state.players[0].resources = {"BRICK": 0, "LUMBER": 0, "WOOL": 0, "GRAIN": 0, "ORE": 0}

    # Without refresh, cache would return old results
    # With refresh, should recompute
    controller.refresh_state()
    legal_roads_2 = controller.get_legal_road_positions()

    # Should be empty now (no resources)
    assert len(legal_roads_2) == 0
