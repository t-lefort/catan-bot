"""Tests pour le cadre self-play et le buffer de transitions (RL-004)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pytest

from catan.engine.actions import Action, RollDice
from catan.engine.state import GameState
from catan.rl.features import ObservationTensor
from catan.rl.policies import AgentPolicy
from catan.rl.self_play import (
    RolloutBuffer,
    SelfPlayEpisode,
    SelfPlayRunner,
    SelfPlayTransition,
)
from catan.sim.runner import HeadlessEnv


class _StubPolicy(AgentPolicy):
    """Politique déterministe utilisée par les tests."""

    def __init__(self, *, name: str, pick_last: bool = False) -> None:
        super().__init__(name=name)
        self._pick_last = pick_last

    def select_action(self, state: GameState) -> Action:  # type: ignore[override]
        legal: Sequence[Action] = tuple(state.legal_actions())
        if not legal:
            raise ValueError("Aucune action légale pour _StubPolicy")
        return legal[-1] if self._pick_last else legal[0]


def _make_dummy_observation() -> ObservationTensor:
    """Construit un ObservationTensor minimal pour les tests du buffer."""

    return ObservationTensor(
        board=np.zeros((1, 1), dtype=np.float32),
        roads=np.zeros((1,), dtype=np.float32),
        settlements=np.zeros((1,), dtype=np.float32),
        hands=np.zeros((2, 1), dtype=np.float32),
        development_cards=np.zeros((2, 1), dtype=np.float32),
        bank=np.zeros((1,), dtype=np.float32),
        metadata=np.zeros((1,), dtype=np.float32),
        legal_actions_mask=np.zeros((1,), dtype=np.bool_),
    )


def _make_dummy_episode(transitions_count: int, *, seed: int) -> SelfPlayEpisode:
    """Génère un épisode factice composé de transitions artificielles."""

    transitions = []
    for index in range(transitions_count):
        observation = _make_dummy_observation()
        transition = SelfPlayTransition(
            player_id=index % 2,
            policy_name=f"Policy-{index % 2}",
            observation=observation,
            action=RollDice(),
            action_index=0,
            legal_actions_mask=observation.legal_actions_mask,
            reward=float(index),
            done=index == transitions_count - 1,
        )
        transitions.append(transition)

    final_state = GameState.new_1v1_game(seed=seed)
    return SelfPlayEpisode(
        seed=seed,
        transitions=tuple(transitions),
        winner_id=None,
        done=bool(transitions and transitions[-1].done),
        steps=len(transitions),
        final_state=final_state,
        policy_names=("Policy-0", "Policy-1"),
    )


class TestRolloutBuffer:
    """Vérifie la collecte et la gestion des épisodes dans le buffer."""

    def test_add_and_pop_with_capacity(self):
        buffer = RolloutBuffer(capacity=2)
        episode_a = _make_dummy_episode(1, seed=10)
        episode_b = _make_dummy_episode(2, seed=11)
        episode_c = _make_dummy_episode(3, seed=12)

        buffer.add_episode(episode_a)
        assert len(buffer) == 1
        assert buffer.total_transitions == 1

        buffer.add_episode(episode_b)
        assert len(buffer) == 2
        assert buffer.total_transitions == 3

        # L'ajout d'un 3e épisode (capacité = 2) doit éjecter le plus ancien.
        buffer.add_episode(episode_c)
        assert len(buffer) == 2
        assert buffer.total_transitions == 5
        assert buffer.episodes()[0] == episode_b
        assert buffer.episodes()[1] == episode_c

        popped = buffer.pop_all()
        assert popped == (episode_b, episode_c)
        assert len(buffer) == 0
        assert buffer.total_transitions == 0


class TestSelfPlayRunner:
    """Tests d'intégration du runner self-play et du buffer."""

    def _make_runner(self) -> SelfPlayRunner:
        buffer = RolloutBuffer()
        runner = SelfPlayRunner(
            policy_factory=lambda player_id: _StubPolicy(
                name=f"TestPolicy-{player_id}",
                pick_last=bool(player_id),
            ),
            buffer=buffer,
            env_factory=lambda: HeadlessEnv(),
        )
        return runner

    def test_run_episode_records_transitions_and_policies(self):
        runner = self._make_runner()
        buffer = runner.buffer

        episode = runner.run_episode(seed=123, max_steps=4)

        assert isinstance(episode, SelfPlayEpisode)
        assert episode.steps == len(episode.transitions) == 4
        assert episode.done is False
        assert episode.winner_id is None
        assert episode.policy_names == ("TestPolicy-0", "TestPolicy-1")

        # Le buffer doit contenir exactement l'épisode exécuté.
        assert len(buffer) == 1
        assert buffer.total_transitions == 4
        stored_episode = buffer.episodes()[0]
        assert stored_episode is episode

        # Chaque transition doit refléter les informations collectées.
        for transition in episode.transitions:
            assert transition.policy_name in ("TestPolicy-0", "TestPolicy-1")
            assert transition.player_id in (0, 1)
            assert transition.legal_actions_mask.dtype == np.bool_

    def test_run_batch_assigns_incremental_seeds(self):
        runner = self._make_runner()
        buffer = runner.buffer

        episodes = runner.run_batch(num_episodes=3, base_seed=500, max_steps=1)

        assert len(episodes) == 3
        assert tuple(ep.seed for ep in episodes) == (500, 501, 502)
        assert len(buffer) == 3
        assert buffer.total_transitions == 3
        assert buffer.episodes() == episodes
