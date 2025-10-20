"""Tests TDD pour le réseau de neurones RL (RL-005)."""

import numpy as np
import pytest
import torch

from catan.engine.board import Board
from catan.engine.state import GameState
from catan.rl.actions import ActionEncoder
from catan.rl.features import build_observation


# Tests-first pour RL-005 : architecture PyTorch policy/value network
# Ces tests définissent le contrat attendu avant l'implémentation.


def test_network_can_be_instantiated():
    """Le réseau peut être créé avec l'architecture de base."""
    from catan.rl.network import CatanPolicyValueNetwork

    board = Board.standard()
    action_encoder = ActionEncoder(board=board)
    network = CatanPolicyValueNetwork(action_size=action_encoder.size)

    assert network is not None
    assert isinstance(network, torch.nn.Module)


def test_network_forward_returns_policy_and_value():
    """Le forward pass renvoie des logits de politique et une valeur scalaire."""
    from catan.rl.network import CatanPolicyValueNetwork

    board = Board.standard()
    action_encoder = ActionEncoder(board=board)
    state = GameState.new_1v1_game(seed=42)
    obs = build_observation(state, action_encoder=action_encoder)

    network = CatanPolicyValueNetwork(action_size=action_encoder.size)

    # Préparer un batch avec une observation
    batch = _obs_to_tensor_dict(obs, batch_size=1)
    policy_logits, value = network(batch)

    # Vérifier les dimensions
    assert policy_logits.shape == (1, action_encoder.size)
    assert value.shape == (1,)

    # Vérifier les types
    assert policy_logits.dtype == torch.float32
    assert value.dtype == torch.float32


def test_network_forward_supports_batching():
    """Le réseau supporte des batchs de plusieurs observations."""
    from catan.rl.network import CatanPolicyValueNetwork

    board = Board.standard()
    action_encoder = ActionEncoder(board=board)
    state = GameState.new_1v1_game(seed=42)
    obs = build_observation(state, action_encoder=action_encoder)

    network = CatanPolicyValueNetwork(action_size=action_encoder.size)

    batch_size = 4
    batch = _obs_to_tensor_dict(obs, batch_size=batch_size)
    policy_logits, value = network(batch)

    assert policy_logits.shape == (batch_size, action_encoder.size)
    assert value.shape == (batch_size,)


def test_network_masked_softmax_filters_illegal_actions():
    """Les actions illégales reçoivent une probabilité nulle après masquage."""
    from catan.rl.network import CatanPolicyValueNetwork

    board = Board.standard()
    action_encoder = ActionEncoder(board=board)
    state = GameState.new_1v1_game(seed=42)
    obs = build_observation(state, action_encoder=action_encoder)

    network = CatanPolicyValueNetwork(action_size=action_encoder.size)

    batch = _obs_to_tensor_dict(obs, batch_size=1)
    policy_logits, _ = network(batch)

    # Appliquer le masque et vérifier que les actions illégales ont proba=0
    mask = torch.from_numpy(obs.legal_actions_mask).unsqueeze(0)
    probs = network.masked_softmax(policy_logits, mask)

    assert probs.shape == policy_logits.shape
    assert torch.allclose(probs.sum(dim=-1), torch.tensor(1.0), atol=1e-5)

    # Vérifier que les actions illégales ont proba nulle
    illegal_mask = ~mask
    assert torch.all(probs[illegal_mask] == 0.0)


def test_network_gradients_flow_through_policy_and_value():
    """Les gradients se propagent correctement dans le réseau."""
    from catan.rl.network import CatanPolicyValueNetwork

    board = Board.standard()
    action_encoder = ActionEncoder(board=board)
    state = GameState.new_1v1_game(seed=42)
    obs = build_observation(state, action_encoder=action_encoder)

    network = CatanPolicyValueNetwork(action_size=action_encoder.size)

    batch = _obs_to_tensor_dict(obs, batch_size=1)
    policy_logits, value = network(batch)

    # Simuler une perte simple
    loss = policy_logits.mean() + value.mean()
    loss.backward()

    # Vérifier que les gradients existent et ne sont pas nuls
    for name, param in network.named_parameters():
        assert param.grad is not None, f"Pas de gradient pour {name}"
        assert not torch.all(param.grad == 0.0), f"Gradient nul pour {name}"


def test_network_accepts_custom_hidden_sizes():
    """Le réseau accepte une configuration personnalisée de couches cachées."""
    from catan.rl.network import CatanPolicyValueNetwork

    board = Board.standard()
    action_encoder = ActionEncoder(board=board)

    network = CatanPolicyValueNetwork(
        action_size=action_encoder.size,
        hidden_sizes=[128, 64],
    )

    state = GameState.new_1v1_game(seed=42)
    obs = build_observation(state, action_encoder=action_encoder)
    batch = _obs_to_tensor_dict(obs, batch_size=1)

    policy_logits, value = network(batch)

    assert policy_logits.shape == (1, action_encoder.size)
    assert value.shape == (1,)


def test_network_works_with_real_game_state_during_play():
    """Le réseau peut traiter des observations depuis différentes phases du jeu."""
    from catan.rl.network import CatanPolicyValueNetwork
    from catan.engine.actions import PlaceSettlement, PlaceRoad

    board = Board.standard()
    action_encoder = ActionEncoder(board=board)
    network = CatanPolicyValueNetwork(action_size=action_encoder.size)

    state = GameState.new_1v1_game(seed=42)

    # Phase setup
    obs_setup = build_observation(state, action_encoder=action_encoder)
    batch_setup = _obs_to_tensor_dict(obs_setup, batch_size=1)
    policy_logits, value = network(batch_setup)
    assert policy_logits.shape[1] == action_encoder.size

    # Avancer jusqu'à la phase PLAY
    legal_actions = list(state.legal_actions())
    settlement_action = next((a for a in legal_actions if isinstance(a, PlaceSettlement)), None)
    if settlement_action:
        state = state.apply_action(settlement_action)

    legal_actions = list(state.legal_actions())
    road_action = next((a for a in legal_actions if isinstance(a, PlaceRoad)), None)
    if road_action:
        state = state.apply_action(road_action)

    obs_play = build_observation(state, action_encoder=action_encoder)
    batch_play = _obs_to_tensor_dict(obs_play, batch_size=1)
    policy_logits, value = network(batch_play)
    assert policy_logits.shape[1] == action_encoder.size


# Helpers


def _obs_to_tensor_dict(obs, batch_size: int = 1):
    """Convertit une ObservationTensor en dictionnaire de tenseurs PyTorch batchés."""
    return {
        "board": torch.from_numpy(np.stack([obs.board] * batch_size)),
        "roads": torch.from_numpy(np.stack([obs.roads] * batch_size)),
        "settlements": torch.from_numpy(np.stack([obs.settlements] * batch_size)),
        "hands": torch.from_numpy(np.stack([obs.hands] * batch_size)),
        "development_cards": torch.from_numpy(np.stack([obs.development_cards] * batch_size)),
        "bank": torch.from_numpy(np.stack([obs.bank] * batch_size)),
        "metadata": torch.from_numpy(np.stack([obs.metadata] * batch_size)),
    }
