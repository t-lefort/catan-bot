"""Tests for ENG-008 — player-to-player trading (1v1).

Specs references (docs/specs.md):
- Commerce joueur↔joueur avec acceptation explicite.
- Variante 1v1: ressources transférées uniquement entre les deux joueurs.
"""

from __future__ import annotations

from typing import Dict

from catan.engine.actions import (
    AcceptPlayerTrade,
    DeclinePlayerTrade,
    OfferPlayerTrade,
)
from catan.engine.state import (
    GameState,
    PendingPlayerTrade,
    SetupPhase,
    TurnSubPhase,
)


RESOURCE_ZEROES: Dict[str, int] = {
    "BRICK": 0,
    "LUMBER": 0,
    "WOOL": 0,
    "GRAIN": 0,
    "ORE": 0,
}


def make_play_state(*, dice_rolled: bool = True) -> GameState:
    """Return a PLAY-phase state prepared for player trading."""

    state = GameState.new_1v1_game()
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 1
    state.current_player_id = 0
    state.dice_rolled_this_turn = dice_rolled

    for player in state.players:
        player.resources = dict(RESOURCE_ZEROES)
        player.settlements = []
        player.cities = []
        player.roads = []

    return state


def test_offer_player_trade_requires_dice_roll_and_positive_resources():
    """Offering a trade requires dice rolled and positive resource quantities."""

    state = make_play_state(dice_rolled=False)
    state.players[0].resources["BRICK"] = 1
    state.players[1].resources["WOOL"] = 1

    offer = OfferPlayerTrade(give={"BRICK": 1}, receive={"WOOL": 1})
    assert not state.is_action_legal(offer)

    state.dice_rolled_this_turn = True

    assert state.is_action_legal(offer)
    assert not state.is_action_legal(OfferPlayerTrade(give={}, receive={"WOOL": 1}))
    assert not state.is_action_legal(OfferPlayerTrade(give={"BRICK": 1}, receive={}))
    assert not state.is_action_legal(OfferPlayerTrade(give={"BRICK": 0}, receive={"WOOL": 1}))


def test_offer_player_trade_requires_proposer_resources():
    """Proposer must own all resources they offer to trade."""

    state = make_play_state()
    state.players[1].resources["WOOL"] = 1

    offer = OfferPlayerTrade(give={"BRICK": 1}, receive={"WOOL": 1})
    assert not state.is_action_legal(offer)

    state.players[0].resources["BRICK"] = 1
    assert state.is_action_legal(offer)


def test_accept_player_trade_requires_responder_resources():
    """Responder must own the requested resources to accept the trade."""

    state = make_play_state()
    state.players[0].resources["BRICK"] = 1
    state.players[1].resources["WOOL"] = 1

    pending_state = state.apply_action(
        OfferPlayerTrade(give={"BRICK": 1}, receive={"WOOL": 1})
    )

    assert pending_state.turn_subphase == TurnSubPhase.TRADE_RESPONSE
    assert pending_state.current_player_id == 1
    assert isinstance(pending_state.pending_player_trade, PendingPlayerTrade)

    pending_state.players[1].resources["WOOL"] = 0
    assert not pending_state.is_action_legal(AcceptPlayerTrade())

    pending_state.players[1].resources["WOOL"] = 1
    assert pending_state.is_action_legal(AcceptPlayerTrade())


def test_accept_player_trade_transfers_resources_and_resets_turn():
    """Accepting a trade moves resources and resets turn control to proposer."""

    state = make_play_state()
    state.players[0].resources.update({"BRICK": 2, "WOOL": 0})
    state.players[1].resources.update({"BRICK": 0, "WOOL": 2})

    pending_state = state.apply_action(
        OfferPlayerTrade(give={"BRICK": 1}, receive={"WOOL": 1})
    )
    accepted_state = pending_state.apply_action(AcceptPlayerTrade())

    assert accepted_state.turn_subphase == TurnSubPhase.MAIN
    assert accepted_state.current_player_id == 0
    assert accepted_state.pending_player_trade is None

    proposer = accepted_state.players[0]
    responder = accepted_state.players[1]

    assert proposer.resources["BRICK"] == 1
    assert proposer.resources["WOOL"] == 1
    assert responder.resources["BRICK"] == 1
    assert responder.resources["WOOL"] == 1


def test_decline_player_trade_keeps_resources_and_turn_state():
    """Declining a trade leaves resources untouched and returns to MAIN phase."""

    state = make_play_state()
    state.players[0].resources.update({"BRICK": 1})
    state.players[1].resources.update({"WOOL": 1})

    pending_state = state.apply_action(
        OfferPlayerTrade(give={"BRICK": 1}, receive={"WOOL": 1})
    )
    declined_state = pending_state.apply_action(DeclinePlayerTrade())

    assert declined_state.turn_subphase == TurnSubPhase.MAIN
    assert declined_state.current_player_id == 0
    assert declined_state.pending_player_trade is None

    proposer = declined_state.players[0]
    responder = declined_state.players[1]

    assert proposer.resources["BRICK"] == 1
    assert proposer.resources["WOOL"] == 0
    assert responder.resources["BRICK"] == 0
    assert responder.resources["WOOL"] == 1
