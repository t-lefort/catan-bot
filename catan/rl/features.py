"""Encodage ObservationTensor pour l'entraînement RL (RL-001)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable

import numpy as np

from catan.engine.state import (
    DEFAULT_DEV_DECK,
    DEV_CARD_TYPES,
    GameState,
    RESOURCE_TYPES,
    SetupPhase,
    VP_TO_WIN,
)
from catan.rl.actions import ActionEncoder
from catan.sim.runner import ActionSpace, build_default_action_catalog

_RESOURCE_TO_INDEX: Dict[str, int] = {
    resource: idx for idx, resource in enumerate(RESOURCE_TYPES)
}
_DEV_TO_INDEX: Dict[str, int] = {card: idx for idx, card in enumerate(DEV_CARD_TYPES)}
_DEV_DECK_COUNTS = Counter(DEFAULT_DEV_DECK)
_DEV_DECK_TOTAL = float(len(DEFAULT_DEV_DECK))
_RESOURCE_NORMALIZER = 19.0
_TURN_NORMALIZER = 200.0


@dataclass(frozen=True)
class ObservationTensor:
    """Structure regroupant les tenseurs nécessaires au RL."""

    board: np.ndarray
    roads: np.ndarray
    settlements: np.ndarray
    hands: np.ndarray
    development_cards: np.ndarray
    bank: np.ndarray
    metadata: np.ndarray
    legal_actions_mask: np.ndarray


def build_observation(
    state: GameState,
    *,
    action_space: ActionSpace | None = None,
    action_encoder: ActionEncoder | None = None,
) -> ObservationTensor:
    """Construit un ObservationTensor normalisé à partir d'un GameState.

    L'encodage utilise une perspective ego-centrée : les informations du joueur
    actuel sont toujours encodées en premier (index 0), et l'adversaire en second
    (index 1). Cela permet à l'agent d'apprendre plus efficacement car il voit
    toujours "ses" ressources et pièces de la même manière.

    Args:
        state: état du jeu à encoder.
        action_space: espace d'actions partagé (muté pour rester synchronisé).

    Returns:
        ObservationTensor avec toutes les composantes attendues par le pipeline RL.
    """

    current_player = state.current_player_id
    board_tensor = _encode_board(state)
    roads_tensor = _encode_roads(state, current_player)
    settlements_tensor = _encode_settlements(state, current_player)
    hands_tensor = _encode_hands(state, current_player)
    dev_cards_tensor = _encode_dev_cards(state, current_player)
    bank_tensor = _encode_bank(state)
    metadata_tensor = _encode_metadata(state, current_player)
    legal_mask = _encode_legal_actions(state, action_space, action_encoder)

    return ObservationTensor(
        board=board_tensor,
        roads=roads_tensor,
        settlements=settlements_tensor,
        hands=hands_tensor,
        development_cards=dev_cards_tensor,
        bank=bank_tensor,
        metadata=metadata_tensor,
        legal_actions_mask=legal_mask,
    )


def _encode_board(state: GameState) -> np.ndarray:
    tiles = state.board.tiles
    num_tiles = max(tiles) + 1 if tiles else 0
    tensor = np.zeros((num_tiles, 6), dtype=np.float32)
    for tile_id, tile in tiles.items():
        resource_index = _RESOURCE_TO_INDEX.get(tile.resource)
        if resource_index is not None:
            tensor[tile_id, resource_index] = 1.0
        tensor[tile_id, 5] = 0.0 if tile.pip is None else tile.pip / 12.0
    return tensor


def _encode_roads(state: GameState, current_player: int) -> np.ndarray:
    """Encode roads with ego-centric perspective.

    Values: -1.0 (empty), 0.0 (current player), 1.0 (opponent)
    """
    edges = state.board.edges
    num_edges = max(edges) + 1 if edges else 0
    tensor = np.full(num_edges, -1.0, dtype=np.float32)
    for player_id, player in enumerate(state.players):
        ego_id = 0.0 if player_id == current_player else 1.0
        for edge_id in player.roads:
            tensor[edge_id] = ego_id
    return tensor


def _encode_settlements(state: GameState, current_player: int) -> np.ndarray:
    """Encode settlements and cities with ego-centric perspective.

    Values: -1.0 (empty), 0.0 (current player settlement), 1.0 (opponent settlement),
            2.0 (current player city), 3.0 (opponent city)
    """
    vertices = state.board.vertices
    num_vertices = max(vertices) + 1 if vertices else 0
    tensor = np.full(num_vertices, -1.0, dtype=np.float32)
    for player_id, player in enumerate(state.players):
        ego_id = 0 if player_id == current_player else 1
        for vertex_id in player.settlements:
            tensor[vertex_id] = float(ego_id)
        for vertex_id in player.cities:
            tensor[vertex_id] = float(2 + ego_id)
    return tensor


def _encode_hands(state: GameState, current_player: int) -> np.ndarray:
    """Encode player hands with ego-centric perspective.

    Returns (2, 5) tensor where index 0 is current player, index 1 is opponent.
    """
    tensor = np.zeros((len(state.players), len(RESOURCE_TYPES)), dtype=np.float32)
    for player_id, player in enumerate(state.players):
        ego_index = 0 if player_id == current_player else 1
        for resource, amount in player.resources.items():
            resource_index = _RESOURCE_TO_INDEX.get(resource)
            if resource_index is None:
                continue
            tensor[ego_index, resource_index] = amount / _RESOURCE_NORMALIZER
    return tensor


def _encode_dev_cards(state: GameState, current_player: int) -> np.ndarray:
    """Encode development cards with ego-centric perspective.

    Returns (2, 5) tensor where index 0 is current player, index 1 is opponent.
    """
    tensor = np.zeros((len(state.players), len(DEV_CARD_TYPES)), dtype=np.float32)
    for player_id, player in enumerate(state.players):
        ego_index = 0 if player_id == current_player else 1
        for card in DEV_CARD_TYPES:
            index = _DEV_TO_INDEX[card]
            max_count = float(_DEV_DECK_COUNTS.get(card, 1))
            count = player.dev_cards.get(card, 0) + player.new_dev_cards.get(card, 0)
            tensor[ego_index, index] = count / max_count
    return tensor


def _encode_bank(state: GameState) -> np.ndarray:
    tensor = np.zeros(len(RESOURCE_TYPES), dtype=np.float32)
    for resource, index in _RESOURCE_TO_INDEX.items():
        amount = state.bank_resources.get(resource, 0)
        tensor[index] = amount / _RESOURCE_NORMALIZER
    return tensor


def _encode_metadata(state: GameState, current_player: int) -> np.ndarray:
    """Encode game metadata with ego-centric perspective.

    Indices:
        0: Phase - SETUP_ROUND_1 (1.0 if true)
        1: Phase - SETUP_ROUND_2 (1.0 if true)
        2: Phase - PLAY (1.0 if true)
        3: Turn number (normalized)
        4: Longest road owner (0.0 = me, 1.0 = opponent, -1.0 = none)
        5: Largest army owner (0.0 = me, 1.0 = opponent, -1.0 = none)
        6: My victory points (normalized)
        7: Opponent victory points (normalized)
        8: Development deck remaining (normalized)
        9: Reserved for future use
    """
    metadata = np.zeros(10, dtype=np.float32)
    metadata[0] = 1.0 if state.phase == SetupPhase.SETUP_ROUND_1 else 0.0
    metadata[1] = 1.0 if state.phase == SetupPhase.SETUP_ROUND_2 else 0.0
    metadata[2] = 1.0 if state.phase == SetupPhase.PLAY else 0.0
    metadata[3] = state.turn_number / _TURN_NORMALIZER
    metadata[4] = _encode_owner_ego(state.longest_road_owner, current_player)
    metadata[5] = _encode_owner_ego(state.largest_army_owner, current_player)

    opponent_id = 1 - current_player
    metadata[6] = state.players[current_player].victory_points / VP_TO_WIN
    metadata[7] = state.players[opponent_id].victory_points / VP_TO_WIN
    metadata[8] = len(state.dev_deck) / _DEV_DECK_TOTAL
    # metadata[9] reserved
    return metadata


def _encode_owner_ego(owner_id: int | None, current_player: int) -> float:
    """Encode ownership with ego-centric perspective.

    Returns: 0.0 (current player), 1.0 (opponent), -1.0 (no owner)
    """
    if owner_id is None:
        return -1.0
    return 0.0 if owner_id == current_player else 1.0


def _encode_legal_actions(
    state: GameState,
    action_space: ActionSpace | None,
    action_encoder: ActionEncoder | None,
) -> np.ndarray:
    if action_encoder is not None:
        return action_encoder.build_mask(state)

    space = action_space or ActionSpace(build_default_action_catalog(state.board))
    legal_actions = state.legal_actions()
    space.register(legal_actions)
    mask = space.mask(legal_actions)
    return np.array(mask, dtype=np.bool_)
