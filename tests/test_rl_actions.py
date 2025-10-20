"""Tests pour le module d'encodage d'actions RL (RL-002)."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pytest

from catan.engine.actions import (
    AcceptPlayerTrade,
    DeclinePlayerTrade,
    EndTurn,
    OfferPlayerTrade,
    PlaceRoad,
    PlaceSettlement,
    RollDice,
)
from catan.engine.state import GameState, SetupPhase, TurnSubPhase, RESOURCE_TYPES
from catan.rl.actions import ActionEncoder, action_to_catanatron_signature


def _first_of_type(actions: Iterable[object], expected_type: type):
    for action in actions:
        if isinstance(action, expected_type):
            return action
    raise AssertionError(f"Aucune action de type {expected_type} trouvée")


def _complete_setup(state: GameState) -> GameState:
    """Avance automatiquement jusqu'à la phase PLAY."""

    while state.phase != SetupPhase.PLAY:
        settlement = _first_of_type(state.legal_actions(), PlaceSettlement)
        state = state.apply_action(settlement)
        road = _first_of_type(state.legal_actions(), PlaceRoad)
        state = state.apply_action(road)
    return state


class TestActionEncoderMasks:
    """Vérifie la génération de masques sur les différentes phases du tour."""

    def test_setup_phase_initial_mask(self):
        state = GameState.new_1v1_game(seed=123)
        encoder = ActionEncoder(board=state.board)

        mask = encoder.build_mask(state)
        legal = state.legal_actions()

        assert mask.dtype == np.bool_
        assert mask.shape == (encoder.size,)
        assert mask.sum() == len(legal)

        for action in legal:
            idx = encoder.encode(action)
            assert mask[idx]

        # Une action non légale (RollDice) doit être absente du masque.
        roll_idx = encoder.encode(RollDice())
        assert not mask[roll_idx]

    def test_setup_phase_road_selection_mask(self):
        state = GameState.new_1v1_game(seed=456)
        encoder = ActionEncoder(board=state.board)

        settlement = _first_of_type(state.legal_actions(), PlaceSettlement)
        state = state.apply_action(settlement)

        mask = encoder.build_mask(state)
        legal = state.legal_actions()

        assert state.turn_subphase == TurnSubPhase.MAIN  # en setup, attente de route
        assert mask.sum() == len(legal)
        for action in legal:
            idx = encoder.encode(action)
            assert mask[idx]

        # L'action de colonie jouée précédemment ne doit plus être légale.
        settlement_idx = encoder.encode(settlement)
        assert not mask[settlement_idx]

    def test_main_phase_roll_and_end_turn(self):
        state = _complete_setup(GameState.new_1v1_game(seed=789))
        encoder = ActionEncoder(board=state.board)

        mask_before_roll = encoder.build_mask(state)
        roll_idx = encoder.encode(RollDice())
        end_turn_idx = encoder.encode(EndTurn())

        assert mask_before_roll[roll_idx]
        assert not mask_before_roll[end_turn_idx]

        # Lancer forcé (valeur != 7 pour éviter le voleur)
        state = state.apply_action(RollDice(forced_value=(3, 5)))
        mask_after_roll = encoder.build_mask(state)

        assert not mask_after_roll[roll_idx]
        assert mask_after_roll[end_turn_idx]

    def test_robber_discard_phase_mask(self):
        state = _complete_setup(GameState.new_1v1_game(seed=321))

        current = state.players[state.current_player_id]
        for resource in RESOURCE_TYPES:
            current.resources[resource] = 3

        encoder = ActionEncoder(board=state.board)
        state = state.apply_action(RollDice(forced_value=(3, 4)))  # 7 déclenché

        assert state.turn_subphase == TurnSubPhase.ROBBER_DISCARD
        legal = state.legal_actions()
        assert legal, "Attendu au moins une action de défausse"

        mask = encoder.build_mask(state)
        assert mask.sum() == len(legal)
        for action in legal:
            idx = encoder.encode(action)
            assert mask[idx]

    def test_trade_response_mask(self):
        state = _complete_setup(GameState.new_1v1_game(seed=654))
        encoder = ActionEncoder(board=state.board)

        # Préparer des ressources pour un échange 1↔1
        current = state.players[state.current_player_id]
        opponent = state.players[1 - state.current_player_id]
        current.resources["BRICK"] = 1
        opponent.resources["ORE"] = 1

        # Lancer les dés (pas de voleur) afin d'autoriser les échanges
        state = state.apply_action(RollDice(forced_value=(4, 4)))
        offer = OfferPlayerTrade(give={"BRICK": 1}, receive={"ORE": 1})
        state = state.apply_action(offer)

        assert state.turn_subphase == TurnSubPhase.TRADE_RESPONSE
        legal = state.legal_actions()
        mask = encoder.build_mask(state)

        assert mask.sum() == len(legal)
        decline_idx = encoder.encode(DeclinePlayerTrade())
        assert mask[decline_idx]

        accept = AcceptPlayerTrade()
        if accept in legal:
            accept_idx = encoder.encode(accept)
            assert mask[accept_idx]


class TestCatanatronAlignment:
    """Couverture des signatures compatibles catanatron."""

    def test_basic_signatures(self):
        state = GameState.new_1v1_game(seed=999)
        encoder = ActionEncoder(board=state.board)

        signatures = {
            "roll": action_to_catanatron_signature(state.board, RollDice()),
            "settlement": action_to_catanatron_signature(
                state.board, PlaceSettlement(vertex_id=0, free=True)
            ),
            "road": action_to_catanatron_signature(
                state.board, PlaceRoad(edge_id=0, free=True)
            ),
        }

        assert signatures["roll"] == ("ROLL_DICE", None)
        assert signatures["settlement"] == ("BUILD_SETTLEMENT", 0)
        assert signatures["road"][0] == "BUILD_ROAD"
        assert isinstance(signatures["road"][1], tuple)
        assert len(signatures["road"][1]) == 2
