"""Tests pour l'environnement headless (SIM-001).

Objectifs (docs/architecture.md, docs/schemas.md):
- Fournir une API reset()/step() basée sur GameState.
- Exposer un masque d'actions aligné sur un catalogue stable.
- Préserver la reproductibilité via les seeds.
"""

from __future__ import annotations

import dataclasses

import pytest

from catan.engine.actions import EndTurn
from catan.engine.state import GameState, SetupPhase, TurnSubPhase
from catan.engine.serialize import snapshot_to_state, state_to_snapshot


@pytest.fixture
def headless_env():
    """Instancie l'environnement headless (doit exister pour SIM-001)."""
    from catan.sim.runner import HeadlessEnv

    return HeadlessEnv(seed=123)


def test_reset_returns_initial_state(headless_env):
    """reset() doit produire un GameState en phase de setup avec RNG déterministe."""
    state = headless_env.reset()
    assert isinstance(state, GameState)
    assert state.phase == SetupPhase.SETUP_ROUND_1
    assert state.turn_subphase == TurnSubPhase.MAIN
    assert headless_env.state is state


def test_reset_reproducible_with_seed():
    """Deux environnements avec la même seed doivent générer le même deck de dev."""
    from catan.sim.runner import HeadlessEnv

    env_a = HeadlessEnv(seed=999)
    env_b = HeadlessEnv(seed=999)

    state_a = env_a.reset()
    state_b = env_b.reset()

    assert state_a.dev_deck == state_b.dev_deck
    assert state_a.bank_resources == state_b.bank_resources


def test_legal_actions_mask_matches_catalog(headless_env):
    """Le masque doit marquer True pour chaque action légale actuelle."""
    state = headless_env.reset()
    legal = state.legal_actions()
    mask = headless_env.legal_actions_mask()

    catalog = headless_env.action_catalog
    assert len(mask) == len(catalog)
    assert sum(mask) == len(legal)

    for action in legal:
        assert action in catalog
        idx = catalog.index(action)
        assert mask[idx] is True


def test_step_applies_action_and_updates_state(headless_env):
    """step() applique une action légale et renvoie un résultat cohérent."""
    state = headless_env.reset()
    first_action = state.legal_actions()[0]
    result = headless_env.step(first_action)

    # Le résultat doit être un dataclass StepResult (API stable)
    assert dataclasses.is_dataclass(result)
    assert hasattr(result, "state")
    assert hasattr(result, "reward")
    assert hasattr(result, "done")
    assert hasattr(result, "info")

    assert result.state is headless_env.state
    assert isinstance(result.reward, tuple)
    assert len(result.reward) == len(state.players)
    assert all(r == pytest.approx(0.0) for r in result.reward)
    assert result.done is False

    # La première action de setup est un placement de colonie gratuite
    assert headless_env.state.players[0].settlements, "Le joueur actif doit avoir une colonie"


def test_step_rejects_illegal_action(headless_env):
    """Une action illégale doit lever ValueError."""
    headless_env.reset()

    with pytest.raises(ValueError):
        headless_env.step(EndTurn())


def test_action_catalog_extends_when_new_actions_seen(headless_env):
    """Le catalogue doit intégrer les nouvelles actions rencontrées au fil du jeu."""
    state = headless_env.reset()
    initial_catalog_size = len(headless_env.action_catalog)

    # Après placement colonie, on devrait voir apparaître PlaceRoad (free)
    first_action = state.legal_actions()[0]
    headless_env.step(first_action)
    headless_env.legal_actions_mask()  # force l'actualisation du catalogue

    assert len(headless_env.action_catalog) >= initial_catalog_size


def _play_first_legal_actions(env, count: int) -> None:
    """Applique `count` actions en choisissant toujours la première action légale."""

    for _ in range(count):
        legal = env.legal_actions()
        assert legal, "Aucune action légale disponible pour poursuivre le scénario déterministe"
        env.step(legal[0])


def test_replay_sequence_is_identical_with_same_seed():
    """Deux environnements seedés identiquement doivent produire la même trajectoire."""
    from catan.sim.runner import HeadlessEnv

    env_a = HeadlessEnv(seed=2025)
    env_b = HeadlessEnv(seed=2025)

    env_a.reset()
    env_b.reset()

    # Avancer suffisamment loin pour inclure le lancer de dés aléatoire.
    steps_to_play_phase = 8  # 4 placements × (colonie+route) × 2 joueurs
    _play_first_legal_actions(env_a, steps_to_play_phase)
    _play_first_legal_actions(env_b, steps_to_play_phase)

    # Le prochain RollDice() utilise le RNG interne: vérifier qu'il reste identique.
    snapshot_before = state_to_snapshot(env_a.state)
    assert snapshot_before == state_to_snapshot(env_b.state)

    action_a = env_a.legal_actions()[0]
    action_b = env_b.legal_actions()[0]
    assert action_a == action_b

    result_a = env_a.step(action_a)
    result_b = env_b.step(action_b)
    assert state_to_snapshot(result_a.state) == state_to_snapshot(result_b.state)


def test_clone_preserves_future_sequence():
    """HeadlessEnv.clone() doit permettre de rejouer exactement la suite."""
    from catan.sim.runner import HeadlessEnv

    env = HeadlessEnv(seed=404)
    env.reset()
    _play_first_legal_actions(env, 10)

    clone = env.clone()
    assert state_to_snapshot(env.state) == state_to_snapshot(clone.state)
    assert len(env.action_catalog) == len(clone.action_catalog)
    assert env.legal_actions_mask() == clone.legal_actions_mask()

    # Poursuivre quelques actions (incluant potentiellement RNG) et comparer.
    for _ in range(5):
        action_original = env.legal_actions()[0]
        action_clone = clone.legal_actions()[0]
        assert action_original == action_clone
        state_original = env.step(action_original).state
        state_clone = clone.step(action_clone).state
        assert state_to_snapshot(state_original) == state_to_snapshot(state_clone)


def test_reset_from_snapshot_reproduces_state_and_rng():
    """reset(state=...) doit restaurer l'état et le RNG pour reproduire la suite."""
    from catan.sim.runner import HeadlessEnv

    env = HeadlessEnv(seed=777)
    env.reset()
    _play_first_legal_actions(env, 6)
    snapshot = state_to_snapshot(env.state)

    restored_state = snapshot_to_state(snapshot)
    replay_env = HeadlessEnv(seed=0)  # la seed est ignorée puisque l'état est injecté
    replay_env.reset(state=restored_state)

    assert state_to_snapshot(replay_env.state) == snapshot
    assert replay_env.legal_actions_mask() == env.legal_actions_mask()

    next_action_original = env.legal_actions()[0]
    next_action_replay = replay_env.legal_actions()[0]
    assert next_action_original == next_action_replay

    roll_original = env.step(next_action_original).state
    roll_replay = replay_env.step(next_action_replay).state
    assert state_to_snapshot(roll_original) == state_to_snapshot(roll_replay)
