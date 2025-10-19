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
