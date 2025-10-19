"""Tests pour ENG-010 — Conditions de victoire (15 VP).

Objectifs:
- Déclencher la victoire dès qu'un joueur atteint le seuil de points (visibles + cachés).
- Interdire toute action supplémentaire une fois la partie terminée.
"""

from __future__ import annotations

from catan.engine.actions import BuyDevelopment, BuildCity, RollDice
from catan.engine.rules import VP_TO_WIN
from catan.engine.state import GameState, RESOURCE_TYPES, SetupPhase, TurnSubPhase


def _empty_resources() -> dict[str, int]:
    return {resource: 0 for resource in RESOURCE_TYPES}


def _make_play_state() -> GameState:
    """Construit un état prêt pour la phase de jeu principale."""
    state = GameState.new_1v1_game()
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 1
    state.current_player_id = 0
    state.dice_rolled_this_turn = True
    for player in state.players:
        player.resources = _empty_resources()
        player.settlements = []
        player.cities = []
        player.roads = []
        player.victory_points = 0
        player.hidden_victory_points = 0
    return state


def test_victory_triggers_when_visible_points_reach_threshold():
    state = _make_play_state()
    player = state.players[0]

    # Préparer une colonie à améliorer et suffisamment de points visibles existants.
    player.settlements = [10]
    player.resources["GRAIN"] = 2
    player.resources["ORE"] = 3
    player.victory_points = VP_TO_WIN - 1

    action = BuildCity(vertex_id=10)
    assert state.is_action_legal(action)
    state = state.apply_action(action)

    assert state.is_game_over is True
    assert state.winner_id == 0
    assert state.players[0].victory_points == VP_TO_WIN
    assert state.is_action_legal(RollDice()) is False


def test_hidden_victory_points_also_trigger_victory():
    state = _make_play_state()
    player = state.players[0]

    player.resources["WOOL"] = 1
    player.resources["GRAIN"] = 1
    player.resources["ORE"] = 1
    player.victory_points = VP_TO_WIN - 1
    state.dev_deck = ["VICTORY_POINT"]

    action = BuyDevelopment()
    assert state.is_action_legal(action)
    state = state.apply_action(action)
    updated_player = state.players[0]

    assert state.is_game_over is True
    assert state.winner_id == 0
    assert updated_player.hidden_victory_points == 1
    assert state.is_action_legal(RollDice()) is False
