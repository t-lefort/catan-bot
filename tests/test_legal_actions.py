"""Tests pour ENG-011 — Générateur de coups légaux (partie 1).

Cette première vague couvre:
- setup round 1 / round 2 (placements gratuits)
- début de tour en phase PLAY (lancer de dés obligatoire)
- actions de base après le lancer (routes/colonies/villes possibles)
"""

from __future__ import annotations

from typing import List

from catan.engine.actions import (
    AcceptPlayerTrade,
    DeclinePlayerTrade,
    DiscardResources,
    MoveRobber,
    PlaceRoad,
    PlaceSettlement,
    RollDice,
)
from catan.engine.state import GameState, PendingPlayerTrade, SetupPhase, TurnSubPhase


def _complete_setup(state: GameState) -> GameState:
    """Termine la phase de setup via 4 placements serpent."""

    placements: List[int] = [10, 20, 30, 40]
    for vertex_id in placements:
        state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
        edge_id = state.board.vertices[vertex_id].edges[0]
        state = state.apply_action(PlaceRoad(edge_id=edge_id, free=True))
    assert state.phase == SetupPhase.PLAY
    return state


def _base_play_state() -> GameState:
    """Construit un état jouable après setup avec ressources prêtes."""

    state = _complete_setup(GameState.new_1v1_game())

    # Préparer un état cohérent pour le joueur 0
    state.turn_subphase = TurnSubPhase.MAIN
    state.dice_rolled_this_turn = True
    state.last_dice_roll = 8
    player0 = state.players[0]
    player1 = state.players[1]

    # Nettoyer réseau initial pour un setup contrôlé
    player0.roads = [8, 16, 24]  # réseau connecté vers le sommet 22
    player0.settlements = [10]
    player0.cities = []
    player0.victory_points = 1

    player1.roads = [35]
    player1.settlements = [30]
    player1.cities = []
    player1.victory_points = 1

    # Ressources disponibles
    for resource in ("BRICK", "LUMBER", "WOOL", "GRAIN", "ORE"):
        player0.resources[resource] = 2
        player1.resources[resource] = 0
    player1.resources["BRICK"] = 1

    return state


class TestSetupEnumerations:
    """Couverture de la génération d'actions pendant le setup."""

    def test_initial_state_offers_free_settlements_only(self):
        state = GameState.new_1v1_game()
        actions = state.legal_actions()

        assert actions, "La liste d'actions ne devrait pas être vide."
        assert all(isinstance(action, PlaceSettlement) for action in actions)
        assert all(action.free for action in actions)

        vertex_ids = [action.vertex_id for action in actions]
        assert len(vertex_ids) == len(set(vertex_ids)), "Pas de doublons attendus."

        for action in actions:
            assert state.is_action_legal(action), f"Action illégale détectée: {action}"

    def test_after_first_settlement_only_adjacent_roads_are_available(self):
        state = GameState.new_1v1_game()
        chosen_vertex = next(iter(state.board.vertices))
        state = state.apply_action(PlaceSettlement(vertex_id=chosen_vertex, free=True))

        actions = state.legal_actions()
        assert actions, "Le joueur doit pouvoir placer une route gratuite."
        assert all(isinstance(action, PlaceRoad) for action in actions)
        assert all(action.free for action in actions)

        expected_edges = set(state.board.vertices[chosen_vertex].edges)
        edge_ids = {action.edge_id for action in actions}
        assert edge_ids == expected_edges

        for action in actions:
            assert state.is_action_legal(action)


class TestPlayPhaseEnumerations:
    """Couverture partielle de la phase PLAY (début de tour)."""

    def test_turn_start_requires_dice_roll(self):
        state = _complete_setup(GameState.new_1v1_game())
        state.dice_rolled_this_turn = False
        state.turn_subphase = TurnSubPhase.MAIN
        state.current_player_id = 0

        actions = state.legal_actions()
        assert actions == [RollDice()], "Seul RollDice doit être légal avant le lancer."

    def test_after_dice_roll_includes_build_options(self):
        state = _base_play_state()

        actions = state.legal_actions()
        assert all(state.is_action_legal(action) for action in actions)
        # Le lancer de dés ne doit plus être disponible
        assert RollDice() not in actions

        # Attendu: route connectée ou colonie si ressources suffisantes
        assert PlaceRoad(edge_id=15) in actions  # connecté via edge 8 -> 15
        assert PlaceSettlement(vertex_id=22) in actions


class TestRobberSubphases:
    """Vérifie la génération pendant les sous-phases du voleur."""

    def test_discard_generates_all_resource_splits(self):
        state = _base_play_state()
        state.turn_subphase = TurnSubPhase.ROBBER_DISCARD
        state.current_player_id = 0
        state.pending_discards = {0: 2}
        state.pending_discard_queue = [0]

        player = state.players[0]
        player.resources.update({"BRICK": 2, "LUMBER": 1, "WOOL": 0, "GRAIN": 0, "ORE": 0})

        actions = state.legal_actions()
        assert actions
        assert all(isinstance(action, DiscardResources) for action in actions)
        payloads = {
            tuple(sorted((resource, amount) for resource, amount in action.resources.items() if amount > 0))
            for action in actions
        }
        expected = {(("BRICK", 2),), (("BRICK", 1), ("LUMBER", 1))}
        assert payloads == expected
        assert all(state.is_action_legal(action) for action in actions)

    def test_move_robber_lists_tiles_and_steal_targets(self):
        state = _base_play_state()
        state.turn_subphase = TurnSubPhase.ROBBER_MOVE
        state.current_player_id = 0
        state.robber_tile_id = 0

        opponent_vertex = state.players[1].settlements[0]
        target_tile = next(
            tile_id
            for tile_id in state.board.vertices[opponent_vertex].adjacent_tiles
            if state.board.tiles[tile_id].resource != "DESERT"
        )

        actions = state.legal_actions()
        move_actions = [action for action in actions if isinstance(action, MoveRobber)]
        assert move_actions

        assert target_tile in {action.tile_id for action in move_actions}
        assert any(
            action.tile_id == target_tile and action.steal_from == 1 for action in move_actions
        )
        assert all(action.tile_id != 0 for action in move_actions)


class TestTradeResponses:
    """Génération des actions pendant la réponse à un commerce joueur↔joueur."""

    def test_pending_trade_offers_accept_and_decline(self):
        state = _base_play_state()
        state.turn_subphase = TurnSubPhase.TRADE_RESPONSE
        state.current_player_id = 1
        state.pending_player_trade = PendingPlayerTrade(
            proposer_id=0,
            responder_id=1,
            give={"BRICK": 1},
            receive={"WOOL": 1},
        )

        state.players[0].resources["BRICK"] = 1
        state.players[1].resources["WOOL"] = 1

        actions = state.legal_actions()
        assert set(actions) == {AcceptPlayerTrade(), DeclinePlayerTrade()}
        assert all(state.is_action_legal(action) for action in actions)


class TestLegalActionMask:
    """Validation du masque booléen aligné sur un catalogue d'actions."""

    def test_mask_aligns_with_catalog(self):
        state = _complete_setup(GameState.new_1v1_game())
        state.dice_rolled_this_turn = False
        state.turn_subphase = TurnSubPhase.MAIN
        catalog = [
            RollDice(),
            PlaceRoad(edge_id=15),
            PlaceSettlement(vertex_id=22),
        ]

        mask = state.legal_actions_mask(catalog)
        assert mask == [True, False, False]
