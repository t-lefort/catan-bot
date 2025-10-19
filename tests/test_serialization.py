"""Tests de sérialisation (ENG-012).

Objectifs:
- Sérialiser un GameState complet vers un snapshot JSON-friendly.
- Désérialiser un snapshot pour retrouver un GameState équivalent.
- Préserver l'état du RNG pour garantir le même lancer de dés après reprise.
"""

import json
from typing import Iterable

import pytest

from catan.engine.actions import PlaceRoad, PlaceSettlement, RollDice
from catan.engine.state import GameState, SetupPhase, TurnSubPhase
from catan.engine.serialize import snapshot_to_state, state_to_snapshot


def _complete_setup(state: GameState) -> GameState:
    """Avance automatiquement le jeu jusqu'à la phase PLAY."""

    while state.phase != SetupPhase.PLAY:
        settlement = _first_of_type(state.legal_actions(), PlaceSettlement)
        state = state.apply_action(settlement)
        road = _first_of_type(state.legal_actions(), PlaceRoad)
        state = state.apply_action(road)
    return state


def _first_of_type(actions: Iterable[object], expected_type: type):
    """Renvoie la première action d'un type donné dans une séquence."""
    for action in actions:
        if isinstance(action, expected_type):
            return action
    raise AssertionError(f"Aucune action du type {expected_type} disponible")


class TestStateSerialization:
    """Tests de round-trip entre GameState et snapshot sérialisé."""

    def test_round_trip_preserves_core_fields(self):
        """La sérialisation conserve les champs clés de l'état."""
        state = GameState.new_1v1_game(seed=123)
        state = _complete_setup(state)

        # Forcer un lancer pour remplir last_dice_roll sans déclencher le voleur.
        state = state.apply_action(RollDice(forced_value=(2, 3)))
        assert state.turn_subphase == TurnSubPhase.MAIN

        snapshot = state_to_snapshot(state)
        # Le snapshot doit être JSON-serialisable
        json.dumps(snapshot, sort_keys=True)

        restored = snapshot_to_state(snapshot)

        assert restored.phase == state.phase
        assert restored.turn_number == state.turn_number
        assert restored.current_player_id == state.current_player_id
        assert restored.turn_subphase == state.turn_subphase
        assert restored.last_dice_roll == state.last_dice_roll
        assert restored.dice_rolled_this_turn == state.dice_rolled_this_turn
        assert restored.robber_tile_id == state.robber_tile_id
        assert restored.dev_deck == state.dev_deck
        assert restored.bank_resources == state.bank_resources
        assert restored.longest_road_owner == state.longest_road_owner
        assert restored.largest_army_owner == state.largest_army_owner
        assert restored.is_game_over == state.is_game_over
        assert [p.resources for p in restored.players] == [
            p.resources for p in state.players
        ]
        assert [p.settlements for p in restored.players] == [
            p.settlements for p in state.players
        ]
        assert snapshot["schema_version"] == "0.1.0"
        assert snapshot["variant"] == {"vp_to_win": 15, "discard_threshold": 9}
        assert snapshot["rng_state"]["type"] == "py_random"

    def test_rng_sequence_is_preserved_after_restore(self):
        """Après désérialisation, le RNG produit les mêmes lancers."""
        state = GameState.new_1v1_game(seed=999)
        state = _complete_setup(state)

        snapshot = state_to_snapshot(state)
        restored = snapshot_to_state(snapshot)

        # Lancer non forcé: la valeur doit être identique
        state_roll = state.apply_action(RollDice())
        restored_roll = restored.apply_action(RollDice())
        assert state_roll.last_dice_roll == restored_roll.last_dice_roll

        snapshot_after_roll = state_to_snapshot(state_roll)
        restored_snapshot_after_roll = state_to_snapshot(restored_roll)

        # L'état RNG doit diverger du snapshot initial et être identique entre les deux trajectoires.
        assert snapshot_after_roll["rng_state"]["state"] != snapshot["rng_state"]["state"]
        assert (
            snapshot_after_roll["rng_state"]["state"]
            == restored_snapshot_after_roll["rng_state"]["state"]
        )
