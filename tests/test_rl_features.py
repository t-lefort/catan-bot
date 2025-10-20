"""Tests pour l'encodage ObservationTensor (RL-001)."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pytest

from catan.engine.actions import PlaceRoad, PlaceSettlement
from catan.engine.state import GameState, RESOURCE_TYPES, SetupPhase
from catan.rl.features import ObservationTensor, build_observation
from catan.sim.runner import ActionSpace, build_default_action_catalog


def _complete_setup(state: GameState) -> GameState:
    """Avance automatiquement jusqu'à la phase PLAY (helper tests)."""

    while state.phase != SetupPhase.PLAY:
        settlement = _first_of_type(state.legal_actions(), PlaceSettlement)
        state = state.apply_action(settlement)
        road = _first_of_type(state.legal_actions(), PlaceRoad)
        state = state.apply_action(road)
    return state


def _first_of_type(actions: Iterable[object], expected_type: type):
    for action in actions:
        if isinstance(action, expected_type):
            return action
    raise AssertionError(f"Aucune action du type {expected_type} disponible")


def _resource_index(resource: str) -> int:
    try:
        return RESOURCE_TYPES.index(resource)
    except ValueError as exc:  # pragma: no cover - devrait rester limité aux ressources standards
        raise AssertionError(f"Ressource inattendue: {resource}") from exc


class TestObservationBuilder:
    """Couverture des cas principaux de l'encodage observation."""

    def test_initial_state_shapes_and_defaults(self):
        state = GameState.new_1v1_game(seed=123)
        action_space = ActionSpace(build_default_action_catalog(state.board))

        observation = build_observation(state, action_space=action_space)

        assert isinstance(observation, ObservationTensor)
        assert observation.board.shape == (19, 6)
        assert observation.roads.shape == (72,)
        assert observation.settlements.shape == (54,)
        assert observation.hands.shape == (2, 5)
        assert observation.development_cards.shape == (2, 5)
        assert observation.bank.shape == (5,)
        assert observation.metadata.shape == (10,)
        assert observation.legal_actions_mask.dtype == np.bool_

        # Tuile désert: aucun one-hot, pip normalisé nul
        desert_tile_id = next(
            tile_id
            for tile_id, tile in state.board.tiles.items()
            if tile.resource == "DESERT"
        )
        np.testing.assert_array_equal(
            observation.board[desert_tile_id, :5], np.zeros(5, dtype=np.float32)
        )
        assert observation.board[desert_tile_id, 5] == pytest.approx(0.0)

        # Tuile ressource: one-hot et pip normalisé
        resource_tile_id = next(
            tile_id
            for tile_id, tile in state.board.tiles.items()
            if tile.resource != "DESERT" and tile.pip is not None
        )
        resource_tile = state.board.tiles[resource_tile_id]
        res_index = _resource_index(resource_tile.resource)
        assert observation.board[resource_tile_id, res_index] == pytest.approx(1.0)
        assert observation.board[resource_tile_id, :5].sum() == pytest.approx(1.0)
        assert observation.board[resource_tile_id, 5] == pytest.approx(
            resource_tile.pip / 12.0
        )

        # Aucune pièce placée ni ressource en main
        assert np.all(observation.roads == -1.0)
        assert np.all(observation.settlements == -1.0)
        assert np.allclose(observation.hands, 0.0)
        assert np.allclose(observation.development_cards, 0.0)
        assert np.allclose(observation.bank, 1.0)

        # Métadonnées phase setup round 1 (ego-centric)
        assert observation.metadata[0] == pytest.approx(1.0)  # SETUP_ROUND_1
        assert observation.metadata[1] == pytest.approx(0.0)  # SETUP_ROUND_2
        assert observation.metadata[2] == pytest.approx(0.0)  # PLAY
        assert observation.metadata[3] == pytest.approx(state.turn_number / 200.0)
        assert observation.metadata[4] == pytest.approx(-1.0)  # Longest road owner
        assert observation.metadata[5] == pytest.approx(-1.0)  # Largest army owner
        assert observation.metadata[6] == pytest.approx(0.0)  # VP current player
        assert observation.metadata[7] == pytest.approx(0.0)  # VP opponent
        assert observation.metadata[8] == pytest.approx(len(state.dev_deck) / 25.0)

        expected_mask = np.array(
            action_space.mask(state.legal_actions()), dtype=np.bool_
        )
        np.testing.assert_array_equal(
            observation.legal_actions_mask, expected_mask
        )

    def test_state_after_setup_reflects_board_and_hands(self):
        state = _complete_setup(GameState.new_1v1_game(seed=123))
        action_space = ActionSpace(build_default_action_catalog(state.board))

        observation = build_observation(state, action_space=action_space)

        current_player_id = state.current_player_id
        opponent_id = 1 - current_player_id
        current_player = state.players[current_player_id]
        opponent_player = state.players[opponent_id]

        # Roads encodés en perspective ego-centrée : 0.0 = moi, 1.0 = adversaire
        for edge_id in current_player.roads:
            assert observation.roads[edge_id] == pytest.approx(0.0)
        for edge_id in opponent_player.roads:
            assert observation.roads[edge_id] == pytest.approx(1.0)

        free_edge = next(
            edge_id
            for edge_id in state.board.edges
            if edge_id not in current_player.roads and edge_id not in opponent_player.roads
        )
        assert observation.roads[free_edge] == pytest.approx(-1.0)

        # Settlements encodés en perspective ego-centrée
        for vertex_id in current_player.settlements:
            assert observation.settlements[vertex_id] == pytest.approx(0.0)
        for vertex_id in opponent_player.settlements:
            assert observation.settlements[vertex_id] == pytest.approx(1.0)

        # Hands encodés en perspective ego-centrée : index 0 = moi, index 1 = adversaire
        resource_to_index = {resource: idx for idx, resource in enumerate(RESOURCE_TYPES)}
        for resource, amount in current_player.resources.items():
            expected = amount / 19.0
            assert observation.hands[0, resource_to_index[resource]] == pytest.approx(
                expected
            )
        for resource, amount in opponent_player.resources.items():
            expected = amount / 19.0
            assert observation.hands[1, resource_to_index[resource]] == pytest.approx(
                expected
            )

        # Métadonnées phase PLAY (ego-centric)
        assert observation.metadata[2] == pytest.approx(1.0)  # PLAY
        assert observation.metadata[0] == pytest.approx(0.0)  # SETUP_ROUND_1
        assert observation.metadata[1] == pytest.approx(0.0)  # SETUP_ROUND_2
        assert observation.metadata[3] == pytest.approx(state.turn_number / 200.0)
        assert observation.metadata[4] == pytest.approx(-1.0)  # Longest road
        assert observation.metadata[5] == pytest.approx(-1.0)  # Largest army
        assert observation.metadata[6] == pytest.approx(current_player.victory_points / 15.0)
        assert observation.metadata[7] == pytest.approx(opponent_player.victory_points / 15.0)
        assert observation.metadata[8] == pytest.approx(len(state.dev_deck) / 25.0)

        expected_mask = np.array(
            action_space.mask(state.legal_actions()), dtype=np.bool_
        )
        np.testing.assert_array_equal(
            observation.legal_actions_mask, expected_mask
        )

    def test_ego_centric_perspective_consistency(self):
        """Vérifie que la perspective ego-centrée fonctionne pour les deux joueurs."""
        state = _complete_setup(GameState.new_1v1_game(seed=456))
        action_space = ActionSpace(build_default_action_catalog(state.board))

        # Ajouter des ressources différentes aux deux joueurs pour tester
        state.players[0].resources["LUMBER"] = 5
        state.players[0].resources["BRICK"] = 3
        state.players[1].resources["GRAIN"] = 7
        state.players[1].resources["WOOL"] = 2

        # Construire observations depuis la perspective des deux joueurs
        original_player = state.current_player_id

        # Observation du point de vue du joueur actuel
        obs_current = build_observation(state, action_space=action_space)

        # Changer de joueur actuel pour tester l'autre perspective
        state.current_player_id = 1 - original_player
        obs_other = build_observation(state, action_space=action_space)

        # Restaurer le joueur original
        state.current_player_id = original_player

        # Vérifier que les hands sont bien ego-centrées
        resource_to_index = {resource: idx for idx, resource in enumerate(RESOURCE_TYPES)}

        if original_player == 0:
            # obs_current[0] = player0, obs_current[1] = player1
            assert obs_current.hands[0, resource_to_index["LUMBER"]] == pytest.approx(5 / 19.0)
            assert obs_current.hands[0, resource_to_index["BRICK"]] == pytest.approx(3 / 19.0)
            assert obs_current.hands[1, resource_to_index["GRAIN"]] == pytest.approx(7 / 19.0)
            assert obs_current.hands[1, resource_to_index["WOOL"]] == pytest.approx(2 / 19.0)

            # obs_other[0] = player1, obs_other[1] = player0
            assert obs_other.hands[0, resource_to_index["GRAIN"]] == pytest.approx(7 / 19.0)
            assert obs_other.hands[0, resource_to_index["WOOL"]] == pytest.approx(2 / 19.0)
            assert obs_other.hands[1, resource_to_index["LUMBER"]] == pytest.approx(5 / 19.0)
            assert obs_other.hands[1, resource_to_index["BRICK"]] == pytest.approx(3 / 19.0)
        else:
            # obs_current[0] = player1, obs_current[1] = player0
            assert obs_current.hands[0, resource_to_index["GRAIN"]] == pytest.approx(7 / 19.0)
            assert obs_current.hands[0, resource_to_index["WOOL"]] == pytest.approx(2 / 19.0)
            assert obs_current.hands[1, resource_to_index["LUMBER"]] == pytest.approx(5 / 19.0)
            assert obs_current.hands[1, resource_to_index["BRICK"]] == pytest.approx(3 / 19.0)

            # obs_other[0] = player0, obs_other[1] = player1
            assert obs_other.hands[0, resource_to_index["LUMBER"]] == pytest.approx(5 / 19.0)
            assert obs_other.hands[0, resource_to_index["BRICK"]] == pytest.approx(3 / 19.0)
            assert obs_other.hands[1, resource_to_index["GRAIN"]] == pytest.approx(7 / 19.0)
            assert obs_other.hands[1, resource_to_index["WOOL"]] == pytest.approx(2 / 19.0)

        # Vérifier que les VP sont aussi ego-centrés
        vp0 = state.players[0].victory_points
        vp1 = state.players[1].victory_points

        if original_player == 0:
            assert obs_current.metadata[6] == pytest.approx(vp0 / 15.0)
            assert obs_current.metadata[7] == pytest.approx(vp1 / 15.0)
            assert obs_other.metadata[6] == pytest.approx(vp1 / 15.0)
            assert obs_other.metadata[7] == pytest.approx(vp0 / 15.0)
        else:
            assert obs_current.metadata[6] == pytest.approx(vp1 / 15.0)
            assert obs_current.metadata[7] == pytest.approx(vp0 / 15.0)
            assert obs_other.metadata[6] == pytest.approx(vp0 / 15.0)
            assert obs_other.metadata[7] == pytest.approx(vp1 / 15.0)
