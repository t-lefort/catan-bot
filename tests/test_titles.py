"""Tests pour ENG-009 — Titres spéciaux (Plus longue route, Plus grande armée).

Ces tests valident les règles:
- La plus longue route rapporte 2 VP à partir de 5 routes connectées, se transfère
  uniquement si un adversaire obtient une route strictement plus longue, et reste
  acquise en cas d'égalité.
- La plus grande armée s'obtient après 3 chevaliers joués, se transfère uniquement
  lorsqu'un adversaire en joue davantage.
"""

from __future__ import annotations

from typing import Sequence

from catan.engine.actions import MoveRobber, PlaceRoad, PlayKnight
from catan.engine.state import (
    DEV_CARD_TYPES,
    GameState,
    PROGRESS_CARD_TYPES,
    RESOURCE_TYPES,
    SetupPhase,
    TurnSubPhase,
)


def _empty_resources() -> dict[str, int]:
    return {resource: 0 for resource in RESOURCE_TYPES}


def _empty_dev_cards() -> dict[str, int]:
    cards = {card: 0 for card in DEV_CARD_TYPES}
    cards.update({card: 0 for card in PROGRESS_CARD_TYPES if card not in cards})
    return cards


def make_play_state() -> GameState:
    """Construit un état post-setup minimal pour les tests de titres."""

    state = GameState.new_1v1_game()
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 1
    state.current_player_id = 0
    state.dice_rolled_this_turn = True
    state._waiting_for_road = False
    state._setup_roads_placed = 0
    state._setup_settlements_placed = 0

    for player in state.players:
        player.resources = _empty_resources()
        player.roads = []
        player.settlements = []
        player.cities = []
        player.dev_cards = _empty_dev_cards()
        player.new_dev_cards = _empty_dev_cards()
        player.played_dev_cards = {
            card: 0 for card in ("KNIGHT",) + PROGRESS_CARD_TYPES
        }
        player.victory_points = 0
        player.hidden_victory_points = 0

    state.players[0].settlements = [10]
    state.players[0].roads = [8]  # (5, 10)
    state.players[0].victory_points = 1

    state.players[1].settlements = [30]
    state.players[1].roads = [35]  # (24, 30)
    state.players[1].victory_points = 1

    return state


def _grant_road_resources(state: GameState, player_id: int, road_count: int) -> None:
    player = state.players[player_id]
    player.resources["BRICK"] = max(player.resources["BRICK"], road_count)
    player.resources["LUMBER"] = max(player.resources["LUMBER"], road_count)


def _build_roads(state: GameState, player_id: int, edges: Sequence[int]) -> GameState:
    state.current_player_id = player_id
    state.dice_rolled_this_turn = True
    _grant_road_resources(state, player_id, len(edges))
    for edge_id in edges:
        action = PlaceRoad(edge_id=edge_id)
        assert state.is_action_legal(action)
        state = state.apply_action(action)
    return state


def _play_knight_and_move_robber(
    state: GameState, player_id: int, target_tile: int
) -> GameState:
    player = state.players[player_id]
    assert player.dev_cards.get("KNIGHT", 0) > 0

    state.current_player_id = player_id
    state.turn_subphase = TurnSubPhase.MAIN
    play_knight = PlayKnight()
    assert state.is_action_legal(play_knight)
    state = state.apply_action(play_knight)

    move_robber = MoveRobber(tile_id=target_tile, steal_from=None)
    assert state.is_action_legal(move_robber)
    state = state.apply_action(move_robber)

    # S'assurer que le joueur reprend la main et peut rejouer un chevalier si besoin.
    state.current_player_id = player_id
    state.turn_subphase = TurnSubPhase.MAIN
    return state


def _setup_longest_road_for_player0() -> GameState:
    """Attribue la plus longue route au joueur 0 (5 routes)."""

    state = make_play_state()
    state = _build_roads(state, 0, [15, 17, 25, 34])  # Ajoute 4 routes aux 1 déjà posée
    return state


def _setup_longest_road_for_player1() -> GameState:
    """Attribue d'abord le titre au joueur 0 puis transfert vers le joueur 1."""

    state = _setup_longest_road_for_player0()
    # Donne un réseau plus long au joueur 1 (incluant la route initiale 35)
    state = _build_roads(state, 1, [43, 45, 54, 61, 67, 68])
    return state


def test_longest_road_awarded_at_five_edges():
    state = _setup_longest_road_for_player0()

    assert state.longest_road_owner == 0
    assert state.longest_road_length == 5
    assert state.players[0].victory_points == 3  # 1 colonie + 2 VP longest road
    assert state.players[1].victory_points == 1


def test_longest_road_transfers_on_strictly_longer_path():
    state = _setup_longest_road_for_player1()

    assert state.longest_road_owner == 1
    assert state.longest_road_length == 7
    assert state.players[0].victory_points == 1
    assert state.players[1].victory_points == 3


def test_longest_road_tie_keeps_current_owner():
    state = _setup_longest_road_for_player1()

    # Joueur 0 étend sa route pour atteindre aussi 7 routes (sans dépasser)
    state = _build_roads(state, 0, [6, 42])

    assert state.longest_road_owner == 1
    assert state.longest_road_length == 7
    assert state.players[0].victory_points == 1
    assert state.players[1].victory_points == 3


def test_largest_army_awarded_at_three_knights():
    state = make_play_state()
    player = state.players[0]
    player.dev_cards["KNIGHT"] = 3

    tiles = [1, 2, 3]
    for tile_id in tiles:
        state = _play_knight_and_move_robber(state, 0, tile_id)

    assert state.largest_army_owner == 0
    assert state.largest_army_size == 3
    assert state.players[0].victory_points == 3
    assert state.players[1].victory_points == 1


def test_largest_army_transfers_only_when_strictly_greater():
    state = make_play_state()
    state.players[0].dev_cards["KNIGHT"] = 3
    state.players[1].dev_cards["KNIGHT"] = 4

    for tile_id in [1, 2, 3]:
        state = _play_knight_and_move_robber(state, 0, tile_id)

    # Joueur 1 joue 3 chevaliers -> égalité, le titre reste au joueur 0
    for tile_id in [4, 5, 6]:
        state = _play_knight_and_move_robber(state, 1, tile_id)

    assert state.largest_army_owner == 0
    assert state.players[0].victory_points == 3
    assert state.players[1].victory_points == 1

    # Quatrième chevalier: transfert du titre
    state = _play_knight_and_move_robber(state, 1, 7)

    assert state.largest_army_owner == 1
    assert state.largest_army_size == 4
    assert state.players[0].victory_points == 1
    assert state.players[1].victory_points == 3
