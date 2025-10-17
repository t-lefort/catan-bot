"""Tests for ENG-006 — development card purchase flow.

Specs (docs/specs.md):
- Buying a development card costs 1 wool, 1 grain, 1 ore.
- The deck is finite; purchasing when empty must be illegal.
- A freshly bought card cannot be played during the same turn.
"""

from __future__ import annotations

from typing import Dict, List

import pytest

from catan.engine.actions import BuyDevelopment, PlayKnight, PlayProgress
from catan.engine.rules import COSTS
from catan.engine.state import GameState, SetupPhase, TurnSubPhase


def _empty_resources() -> Dict[str, int]:
    return {"BRICK": 0, "LUMBER": 0, "WOOL": 0, "GRAIN": 0, "ORE": 0}


def play_state_with_deck(deck: List[str]) -> GameState:
    """Return a post-setup state with a deterministic development deck."""

    state = GameState.new_1v1_game(dev_deck=list(deck))
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

        if hasattr(player, "dev_cards"):
            for key in player.dev_cards.keys():
                player.dev_cards[key] = 0
        if hasattr(player, "new_dev_cards"):
            for key in player.new_dev_cards.keys():
                player.new_dev_cards[key] = 0
        if hasattr(player, "played_dev_cards"):
            for key in player.played_dev_cards.keys():
                player.played_dev_cards[key] = 0
        if hasattr(player, "hidden_victory_points"):
            player.hidden_victory_points = 0

    return state


def mature_card_state(card_type: str) -> GameState:
    """State ready to play a specific development card."""

    state = play_state_with_deck([])
    player = state.players[0]
    player.dev_cards[card_type] = 1
    player.new_dev_cards[card_type] = 0
    state.dice_rolled_this_turn = True
    return state


def test_buy_development_card_draws_from_deck_and_tracks_new_card():
    """Buying a development card consumes resources and marks the card as new."""

    state = play_state_with_deck(["KNIGHT", "VICTORY_POINT"])
    player = state.players[0]
    player.resources.update({"WOOL": 1, "GRAIN": 1, "ORE": 1})

    action = BuyDevelopment()
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert len(new_state.dev_deck) == 1
    assert new_state.dev_deck[0] == "VICTORY_POINT"
    assert new_player.resources["WOOL"] == 0
    assert new_player.resources["GRAIN"] == 0
    assert new_player.resources["ORE"] == 0

    assert new_player.new_dev_cards["KNIGHT"] == 1
    assert new_player.dev_cards["KNIGHT"] == 0


def test_buy_development_requires_resources():
    """The player must afford the development card cost."""

    state = play_state_with_deck(["KNIGHT"])
    action = BuyDevelopment()

    assert not state.is_action_legal(action)

    player = state.players[0]
    player.resources.update({"WOOL": 1, "GRAIN": 1, "ORE": 1})

    assert state.is_action_legal(action)


def test_buy_development_illegal_when_deck_empty():
    """Buying from an empty deck is not allowed."""

    state = play_state_with_deck([])
    player = state.players[0]
    player.resources.update({"WOOL": 1, "GRAIN": 1, "ORE": 1})

    action = BuyDevelopment()
    assert not state.is_action_legal(action)


def test_cannot_play_card_same_turn_it_was_bought():
    """A newly bought card cannot be played until a later turn."""

    state = play_state_with_deck(["KNIGHT"])
    player = state.players[0]
    player.resources.update(COSTS["development"])

    state_after_purchase = state.apply_action(BuyDevelopment())
    assert not state_after_purchase.is_action_legal(PlayKnight())


def test_play_knight_sets_robber_phase_and_consumes_card():
    """Playing a knight triggers the robber move phase and consumes the card."""

    state = mature_card_state("KNIGHT")
    action = PlayKnight()
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert new_player.dev_cards["KNIGHT"] == 0
    assert new_player.played_dev_cards["KNIGHT"] == 1
    assert new_state.turn_subphase == TurnSubPhase.ROBBER_MOVE
    assert new_state.robber_roller_id == 0
    assert new_state.current_player_id == 0


def test_play_road_building_places_two_free_roads():
    """Road Building should place two free roads connected to the network."""

    state = mature_card_state("ROAD_BUILDING")
    player = state.players[0]
    opponent = state.players[1]

    # Minimal board context
    player.settlements = [10]
    player.roads = [8]
    opponent.settlements = [30]
    opponent.roads = [35]

    action = PlayProgress(card="ROAD_BUILDING", edges=[15, 16])
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert 15 in new_player.roads
    assert 16 in new_player.roads
    assert new_player.dev_cards["ROAD_BUILDING"] == 0


def test_play_year_of_plenty_grants_resources_from_bank():
    """Year of Plenty grants resources and removes them from the bank."""

    state = mature_card_state("YEAR_OF_PLENTY")
    bank_before = dict(state.bank_resources)

    action = PlayProgress(
        card="YEAR_OF_PLENTY", resources={"WOOL": 1, "ORE": 1}
    )
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert new_player.resources["WOOL"] == 1
    assert new_player.resources["ORE"] == 1
    assert new_state.bank_resources["WOOL"] == bank_before["WOOL"] - 1
    assert new_state.bank_resources["ORE"] == bank_before["ORE"] - 1
    assert new_player.dev_cards["YEAR_OF_PLENTY"] == 0


def test_play_monopoly_collects_resources_from_opponent():
    """Monopoly collects all declared resources from opponents."""

    state = mature_card_state("MONOPOLY")
    player = state.players[0]
    opponent = state.players[1]
    opponent.resources["BRICK"] = 2
    opponent.resources["ORE"] = 1

    action = PlayProgress(card="MONOPOLY", resource="BRICK")
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]
    new_opponent = new_state.players[1]

    assert new_player.resources["BRICK"] == 2
    assert new_opponent.resources["BRICK"] == 0
    assert new_player.dev_cards["MONOPOLY"] == 0


def test_victory_point_card_counts_hidden_points_on_purchase():
    """Victory point cards add hidden points immediately on purchase."""

    state = play_state_with_deck(["VICTORY_POINT"])
    player = state.players[0]
    player.resources.update(COSTS["development"])

    new_state = state.apply_action(BuyDevelopment())
    new_player = new_state.players[0]

    assert new_player.hidden_victory_points == 1
    assert new_player.victory_points == 0
    assert new_player.dev_cards["VICTORY_POINT"] == 0
    assert new_player.new_dev_cards["VICTORY_POINT"] == 1
