"""Tests for ENG-007 — bank/port trades.

Specs (docs/specs.md):
- Bank trade rate: 4:1 without port access.
- Generic port (ANY) allows 3:1 for any resource.
- Specific port allows 2:1 for its resource type only.
"""

from __future__ import annotations

from typing import Dict

from catan.engine.actions import TradeBank
from catan.engine.state import GameState, SetupPhase, TurnSubPhase


def _zero_resources() -> Dict[str, int]:
    return {"BRICK": 0, "LUMBER": 0, "WOOL": 0, "GRAIN": 0, "ORE": 0}


def fresh_play_state() -> GameState:
    """Return a PLAY-phase state prepared for trading."""

    state = GameState.new_1v1_game()
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 1
    state.current_player_id = 0
    state.dice_rolled_this_turn = True

    for player in state.players:
        player.resources = _zero_resources()
        player.settlements = []
        player.cities = []
        player.roads = []

    return state


def test_trade_bank_four_to_one_without_port():
    """Trading 4 identical resources for 1 other is allowed without port access."""

    state = fresh_play_state()
    player = state.players[0]
    player.resources["BRICK"] = 4

    action = TradeBank(give={"BRICK": 4}, receive={"WOOL": 1})
    assert state.is_action_legal(action)

    bank_before = dict(state.bank_resources)
    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert new_player.resources["BRICK"] == 0
    assert new_player.resources["WOOL"] == 1
    assert new_state.bank_resources["BRICK"] == bank_before["BRICK"] + 4
    assert new_state.bank_resources["WOOL"] == bank_before["WOOL"] - 1


def test_trade_bank_three_to_one_requires_generic_port():
    """3:1 trades require ownership of a generic (ANY) port."""

    state = fresh_play_state()
    player = state.players[0]
    player.resources["LUMBER"] = 3

    action = TradeBank(give={"LUMBER": 3}, receive={"ORE": 1})
    assert not state.is_action_legal(action)

    any_port = next(port for port in state.board.ports if port.kind == "ANY")
    player.settlements = [any_port.vertices[0]]

    assert state.is_action_legal(action)

    bank_before = dict(state.bank_resources)
    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert new_player.resources["LUMBER"] == 0
    assert new_player.resources["ORE"] == 1
    assert new_state.bank_resources["LUMBER"] == bank_before["LUMBER"] + 3
    assert new_state.bank_resources["ORE"] == bank_before["ORE"] - 1


def test_trade_bank_two_to_one_requires_matching_specific_port():
    """2:1 trades are only legal for the resource tied to the owned specific port."""

    state = fresh_play_state()
    player = state.players[0]
    player.resources["WOOL"] = 2

    action = TradeBank(give={"WOOL": 2}, receive={"BRICK": 1})
    assert not state.is_action_legal(action)

    any_port = next(port for port in state.board.ports if port.kind == "ANY")
    player.settlements = [any_port.vertices[0]]
    assert not state.is_action_legal(action)

    wool_port = next(port for port in state.board.ports if port.kind == "WOOL")
    player.settlements = [wool_port.vertices[0]]
    assert state.is_action_legal(action)

    bank_before = dict(state.bank_resources)
    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert new_player.resources["WOOL"] == 0
    assert new_player.resources["BRICK"] == 1
    assert new_state.bank_resources["WOOL"] == bank_before["WOOL"] + 2
    assert new_state.bank_resources["BRICK"] == bank_before["BRICK"] - 1


def test_trade_bank_requires_bank_to_have_requested_resource():
    """Trading is illegal if the bank cannot provide the requested resource."""

    state = fresh_play_state()
    player = state.players[0]
    player.resources["BRICK"] = 4
    state.bank_resources["ORE"] = 0

    action = TradeBank(give={"BRICK": 4}, receive={"ORE": 1})
    assert not state.is_action_legal(action)

