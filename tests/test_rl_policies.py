"""Tests pour les politiques RL de base (tâche RL-003)."""

from __future__ import annotations

from typing import Iterable, TypeVar

import pytest

from catan.engine.actions import (
    BuildCity,
    MoveRobber,
    PlaceRoad,
    PlaceSettlement,
    RollDice,
    TradeBank,
)
from catan.engine.state import GameState, SetupPhase, TurnSubPhase, RESOURCE_TYPES
from catan.rl.policies import HeuristicPolicy, RandomLegalPolicy


ActionT = TypeVar("ActionT")


def _first_of_type(actions: Iterable[object], expected_type: type[ActionT]) -> ActionT:
    for action in actions:
        if isinstance(action, expected_type):
            return action
    raise AssertionError(f"Aucune action du type {expected_type} disponible")


def _complete_setup(state: GameState) -> GameState:
    """Avance l'état jusqu'à la phase PLAY en plaçant colonies et routes."""

    while state.phase != SetupPhase.PLAY:
        settlement = _first_of_type(state.legal_actions(), PlaceSettlement)
        state = state.apply_action(settlement)
        road = _first_of_type(state.legal_actions(), PlaceRoad)
        state = state.apply_action(road)
    return state


class TestRandomLegalPolicy:
    """Couverture du comportement déterministe (seed) de RandomLegalPolicy."""

    def test_reproducible_with_same_seed(self):
        state = _complete_setup(GameState.new_1v1_game(seed=1234))
        legal = tuple(state.legal_actions())

        policy_a = RandomLegalPolicy(seed=42)
        policy_b = RandomLegalPolicy(seed=42)
        policy_c = RandomLegalPolicy(seed=43)

        action_a = policy_a.select_action(state)
        action_b = policy_b.select_action(state)
        action_c = policy_c.select_action(state)

        assert action_a in legal
        assert action_b in legal
        assert action_c in legal
        assert action_a == action_b
        if len(legal) > 1:
            assert action_c != action_a


class TestHeuristicPolicy:
    """Couverture des choix stratégiques de la politique heuristique."""

    def test_rolls_dice_at_start_of_turn(self):
        state = _complete_setup(GameState.new_1v1_game(seed=2025))
        policy = HeuristicPolicy()

        chosen = policy.select_action(state)

        assert isinstance(chosen, RollDice)

    def test_prefers_building_city_when_affordable(self):
        state = _complete_setup(GameState.new_1v1_game(seed=97))
        state = state.apply_action(RollDice(forced_value=(2, 3)))

        current = state.players[state.current_player_id]
        for resource in RESOURCE_TYPES:
            current.resources[resource] = 0
        current.resources["ORE"] = 3
        current.resources["GRAIN"] = 2

        policy = HeuristicPolicy()
        chosen = policy.select_action(state)

        assert isinstance(chosen, BuildCity)
        assert chosen.vertex_id in current.settlements

    def test_trades_via_port_to_enable_city(self):
        state = _complete_setup(GameState.new_1v1_game(seed=654))
        state = state.apply_action(RollDice(forced_value=(4, 4)))

        current = state.players[state.current_player_id]
        opponent = state.players[1 - state.current_player_id]

        # Donne accès au port bois (2:1) pour tester la logique "gestion ports"
        if 4 not in current.settlements:
            current.settlements.append(4)
        if 4 in opponent.settlements:
            opponent.settlements.remove(4)

        for resource in RESOURCE_TYPES:
            current.resources[resource] = 0
        current.resources["ORE"] = 2
        current.resources["GRAIN"] = 2
        current.resources["LUMBER"] = 2

        legal_trades = [
            action
            for action in state.legal_actions()
            if isinstance(action, TradeBank)
        ]
        assert legal_trades, "Attendu au moins un échange banque légal"

        policy = HeuristicPolicy()
        chosen = policy.select_action(state)

        assert isinstance(chosen, TradeBank)
        assert chosen.give == {"LUMBER": 2}
        assert chosen.receive == {"ORE": 1}

    def test_handles_robber_move_by_targeting_best_tile(self):
        state = _complete_setup(GameState.new_1v1_game(seed=777))

        # Force la phase déplacement du voleur
        state.turn_subphase = TurnSubPhase.ROBBER_MOVE
        state.robber_roller_id = state.current_player_id
        state.robber_tile_id = 0  # désert actuel

        # S'assurer qu'un adversaire peut être volé sur une tuile riche
        opponent = state.players[1 - state.current_player_id]
        opponent.resources["ORE"] = 3
        current = state.players[state.current_player_id]
        high_pip_tile_id = max(
            (tile_id for tile_id in state.board.tiles if tile_id != state.robber_tile_id),
            key=lambda tid: state.board.tiles[tid].pip or 0,
        )
        tile_vertices = state.board.tiles[high_pip_tile_id].vertices
        opponent.settlements.append(tile_vertices[0])
        if tile_vertices[0] in current.settlements:
            current.settlements.remove(tile_vertices[0])

        legal_moves = [
            action for action in state.legal_actions() if isinstance(action, MoveRobber)
        ]
        assert legal_moves, "Attendu au moins un déplacement de voleur légal"

        policy = HeuristicPolicy()
        chosen = policy.select_action(state)

        assert chosen.tile_id == high_pip_tile_id
        assert chosen.steal_from == opponent.player_id
