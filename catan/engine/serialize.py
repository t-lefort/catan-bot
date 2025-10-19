"""Outils de sérialisation pour GameState (ENG-012).

Conformité minimale avec docs/schemas.md :
- Snapshot JSON-friendly (listes/dicts primitifs)
- Restauration complète de GameState, y compris RNG seedable
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Iterable, List, Mapping

from catan.engine.board import Board
from catan.engine.rules import DISCARD_THRESHOLD, VP_TO_WIN
from catan.engine.state import (
    GameState,
    PendingPlayerTrade,
    Player,
    RngState,
    SetupPhase,
    TurnSubPhase,
)

SCHEMA_VERSION = "0.1.0"
BOARD_SCHEMA = "standard.v1"


def state_to_snapshot(state: GameState) -> Dict[str, Any]:
    """Convertit un GameState en snapshot JSON-friendly."""

    snapshot: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "variant": {"vp_to_win": VP_TO_WIN, "discard_threshold": DISCARD_THRESHOLD},
        "board": {
            "schema": BOARD_SCHEMA,
            "robber_tile_id": state.robber_tile_id,
        },
        "phase": state.phase.value,
        "turn_subphase": state.turn_subphase.value,
        "turn_number": state.turn_number,
        "current_player_id": state.current_player_id,
        "_setup_settlements_placed": state._setup_settlements_placed,
        "_setup_roads_placed": state._setup_roads_placed,
        "_waiting_for_road": state._waiting_for_road,
        "last_dice_roll": state.last_dice_roll,
        "dice_rolled_this_turn": state.dice_rolled_this_turn,
        "pending_discards": _serialize_pending_discards(state.pending_discards),
        "pending_discard_queue": list(state.pending_discard_queue),
        "pending_player_trade": _serialize_pending_trade(state.pending_player_trade),
        "robber_tile_id": state.robber_tile_id,
        "robber_roller_id": state.robber_roller_id,
        "dev_deck": list(state.dev_deck),
        "bank_resources": dict(state.bank_resources),
        "rng_state": _serialize_rng_state(state.rng_state),
        "longest_road_owner": state.longest_road_owner,
        "longest_road_length": state.longest_road_length,
        "largest_army_owner": state.largest_army_owner,
        "largest_army_size": state.largest_army_size,
        "is_game_over": state.is_game_over,
        "winner_id": state.winner_id,
        "players": [_serialize_player(player) for player in state.players],
    }
    return snapshot


def snapshot_to_state(snapshot: Mapping[str, Any]) -> GameState:
    """Reconstruit un GameState à partir d'un snapshot."""

    version = snapshot.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema_version: {version!r}")

    board_info = snapshot.get("board", {})
    robber_tile_id = int(board_info.get("robber_tile_id", snapshot.get("robber_tile_id", 0)))
    board = _board_with_robber(robber_tile_id)

    players = [_deserialize_player(data) for data in snapshot["players"]]

    phase = SetupPhase(snapshot["phase"])
    turn_subphase = TurnSubPhase(snapshot["turn_subphase"])

    rng_state = _deserialize_rng_state(snapshot.get("rng_state"))

    pending_discards = _deserialize_pending_discards(snapshot.get("pending_discards", []))
    pending_discard_queue = [
        int(player_id) for player_id in snapshot.get("pending_discard_queue", [])
    ]
    pending_trade = _deserialize_pending_trade(snapshot.get("pending_player_trade"))

    state = GameState(
        board=board,
        players=players,
        phase=phase,
        current_player_id=int(snapshot["current_player_id"]),
        turn_number=int(snapshot["turn_number"]),
        _setup_settlements_placed=int(snapshot.get("_setup_settlements_placed", 0)),
        _setup_roads_placed=int(snapshot.get("_setup_roads_placed", 0)),
        _waiting_for_road=bool(snapshot.get("_waiting_for_road", False)),
        last_dice_roll=snapshot.get("last_dice_roll"),
        dice_rolled_this_turn=bool(snapshot.get("dice_rolled_this_turn", False)),
        turn_subphase=turn_subphase,
        pending_discards=pending_discards,
        pending_discard_queue=pending_discard_queue,
        pending_player_trade=pending_trade,
        robber_tile_id=robber_tile_id,
        robber_roller_id=snapshot.get("robber_roller_id"),
        dev_deck=list(snapshot.get("dev_deck", [])),
        bank_resources=dict(snapshot.get("bank_resources", {})),
        rng_state=rng_state,
        longest_road_owner=snapshot.get("longest_road_owner"),
        longest_road_length=int(snapshot.get("longest_road_length", 0)),
        largest_army_owner=snapshot.get("largest_army_owner"),
        largest_army_size=int(snapshot.get("largest_army_size", 0)),
        is_game_over=bool(snapshot.get("is_game_over", False)),
        winner_id=snapshot.get("winner_id"),
    )
    return state


def _serialize_player(player: Player) -> Dict[str, Any]:
    return {
        "player_id": player.player_id,
        "name": player.name,
        "resources": dict(player.resources),
        "settlements": list(player.settlements),
        "cities": list(player.cities),
        "roads": list(player.roads),
        "dev_cards": dict(player.dev_cards),
        "new_dev_cards": dict(player.new_dev_cards),
        "played_dev_cards": dict(player.played_dev_cards),
        "victory_points": player.victory_points,
        "hidden_victory_points": player.hidden_victory_points,
    }


def _deserialize_player(data: Mapping[str, Any]) -> Player:
    return Player(
        player_id=int(data["player_id"]),
        name=str(data["name"]),
        resources=dict(data.get("resources", {})),
        settlements=list(data.get("settlements", [])),
        cities=list(data.get("cities", [])),
        roads=list(data.get("roads", [])),
        dev_cards=dict(data.get("dev_cards", {})),
        new_dev_cards=dict(data.get("new_dev_cards", {})),
        played_dev_cards=dict(data.get("played_dev_cards", {})),
        victory_points=int(data.get("victory_points", 0)),
        hidden_victory_points=int(data.get("hidden_victory_points", 0)),
    )


def _serialize_pending_discards(pending: Mapping[int, int]) -> List[Dict[str, int]]:
    return [{"player_id": pid, "amount": amount} for pid, amount in pending.items()]


def _deserialize_pending_discards(
    payload: Iterable[Mapping[str, Any]]
) -> Dict[int, int]:
    return {
        int(entry["player_id"]): int(entry["amount"])
        for entry in payload
    }


def _serialize_pending_trade(
    trade: PendingPlayerTrade | None,
) -> Dict[str, Any] | None:
    if trade is None:
        return None
    return {
        "proposer_id": trade.proposer_id,
        "responder_id": trade.responder_id,
        "give": dict(trade.give),
        "receive": dict(trade.receive),
    }


def _deserialize_pending_trade(
    payload: Mapping[str, Any] | None,
) -> PendingPlayerTrade | None:
    if not payload:
        return None
    return PendingPlayerTrade(
        proposer_id=int(payload["proposer_id"]),
        responder_id=int(payload["responder_id"]),
        give=dict(payload.get("give", {})),
        receive=dict(payload.get("receive", {})),
    )


def _serialize_rng_state(rng_state: RngState | None) -> Dict[str, Any]:
    return {
        "type": "py_random",
        "state": _tuple_to_list(rng_state) if rng_state is not None else None,
    }


def _deserialize_rng_state(payload: Mapping[str, Any] | None) -> RngState | None:
    if not payload:
        return None
    state = payload.get("state")
    if state is None:
        return None
    return _list_to_tuple(state)


def _tuple_to_list(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_tuple_to_list(item) for item in value]
    return value


def _list_to_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_list_to_tuple(item) for item in value)
    return value


def _board_with_robber(tile_id: int) -> Board:
    base = Board.standard()
    tiles = {
        t_id: replace(tile, has_robber=(t_id == tile_id))
        for t_id, tile in base.tiles.items()
    }
    return Board(
        tiles=tiles,
        vertices=base.vertices,
        edges=base.edges,
        ports=base.ports,
    )


__all__ = ["SCHEMA_VERSION", "state_to_snapshot", "snapshot_to_state"]
