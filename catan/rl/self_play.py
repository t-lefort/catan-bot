"""Cadre self-play et buffer de transitions pour l'entraînement RL (RL-004)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence, Tuple

import numpy as np

from catan.engine.actions import Action
from catan.engine.state import GameState
from catan.rl.actions import ActionEncoder
from catan.rl.features import ObservationTensor, build_observation
from catan.rl.policies import AgentPolicy
from catan.sim.runner import HeadlessEnv


@dataclass(frozen=True)
class SelfPlayTransition:
    """Transition élémentaire collectée pendant une partie self-play."""

    player_id: int
    policy_name: str
    observation: ObservationTensor
    action: Action
    action_index: int
    legal_actions_mask: np.ndarray
    reward: float
    done: bool


@dataclass(frozen=True)
class SelfPlayEpisode:
    """Résumé d'un épisode self-play et de ses transitions."""

    seed: int | None
    transitions: Tuple[SelfPlayTransition, ...]
    winner_id: int | None
    done: bool
    steps: int
    final_state: GameState
    policy_names: Tuple[str, ...]


class RolloutBuffer:
    """Buffer circulaire stockant les épisodes self-play."""

    def __init__(self, *, capacity: int | None = None) -> None:
        if capacity is not None and capacity <= 0:
            raise ValueError("capacity doit être positif ou None")
        self._capacity = capacity
        self._episodes: List[SelfPlayEpisode] = []
        self._transition_count = 0

    @property
    def capacity(self) -> int | None:
        return self._capacity

    def __len__(self) -> int:
        return len(self._episodes)

    @property
    def total_transitions(self) -> int:
        return self._transition_count

    def episodes(self) -> Tuple[SelfPlayEpisode, ...]:
        return tuple(self._episodes)

    def add_episode(self, episode: SelfPlayEpisode) -> None:
        if self._capacity is not None and len(self._episodes) >= self._capacity:
            removed = self._episodes.pop(0)
            self._transition_count -= len(removed.transitions)
        self._episodes.append(episode)
        self._transition_count += len(episode.transitions)

    def extend(self, episodes: Iterable[SelfPlayEpisode]) -> None:
        for episode in episodes:
            self.add_episode(episode)

    def pop_all(self) -> Tuple[SelfPlayEpisode, ...]:
        episodes = self.episodes()
        self.clear()
        return episodes

    def clear(self) -> None:
        self._episodes.clear()
        self._transition_count = 0

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"RolloutBuffer(len={len(self)}, transitions={self.total_transitions})"


class SelfPlayRunner:
    """Orchestre des parties self-play et stocke les transitions dans un buffer."""

    def __init__(
        self,
        *,
        policy_factory: Callable[[int], AgentPolicy],
        buffer: RolloutBuffer | None = None,
        env_factory: Callable[[], HeadlessEnv] | None = None,
        action_encoder: ActionEncoder | None = None,
        num_players: int = 2,
    ) -> None:
        if num_players <= 0:
            raise ValueError("num_players doit être strictement positif")

        self._policy_factory = policy_factory
        self._buffer = buffer or RolloutBuffer()
        self._env_factory = env_factory or (lambda: HeadlessEnv())
        self._action_encoder = action_encoder or ActionEncoder()
        self._num_players = num_players

    @property
    def buffer(self) -> RolloutBuffer:
        return self._buffer

    @property
    def action_encoder(self) -> ActionEncoder:
        return self._action_encoder

    def _spawn_policies(self, overrides: Sequence[AgentPolicy] | None) -> Tuple[AgentPolicy, ...]:
        if overrides is not None:
            if len(overrides) != self._num_players:
                raise ValueError("Le nombre de politiques overrides doit correspondre à num_players")
            return tuple(overrides)

        return tuple(self._policy_factory(player_id) for player_id in range(self._num_players))

    def run_episode(
        self,
        *,
        seed: int | None = None,
        max_steps: int = 512,
        policies: Sequence[AgentPolicy] | None = None,
        store_in_buffer: bool = True,
    ) -> SelfPlayEpisode:
        if max_steps <= 0:
            raise ValueError("max_steps doit être strictement positif")

        env = self._env_factory()
        state = env.reset(seed=seed)
        active_policies = self._spawn_policies(policies)
        transitions: List[SelfPlayTransition] = []
        steps = 0

        while steps < max_steps and not state.is_game_over:
            legal_actions = tuple(state.legal_actions())
            if not legal_actions:
                break

            current_player = state.current_player_id
            policy = active_policies[current_player]

            observation = build_observation(state, action_encoder=self._action_encoder)
            action = policy.select_action(state)
            action_index = self._action_encoder.encode(action)

            step_result = env.step(action)
            reward = step_result.reward[current_player]
            done = step_result.done

            transition = SelfPlayTransition(
                player_id=current_player,
                policy_name=policy.name,
                observation=observation,
                action=action,
                action_index=action_index,
                legal_actions_mask=observation.legal_actions_mask.copy(),
                reward=reward,
                done=done,
            )
            transitions.append(transition)

            state = step_result.state
            steps += 1

            if done:
                break

        episode = SelfPlayEpisode(
            seed=seed,
            transitions=tuple(transitions),
            winner_id=state.winner_id,
            done=state.is_game_over,
            steps=len(transitions),
            final_state=state,
            policy_names=tuple(policy.name for policy in active_policies),
        )

        if store_in_buffer:
            self._buffer.add_episode(episode)

        return episode

    def run_batch(
        self,
        *,
        num_episodes: int,
        base_seed: int | None = None,
        max_steps: int = 512,
        policies: Sequence[AgentPolicy] | None = None,
        store_in_buffer: bool = True,
    ) -> Tuple[SelfPlayEpisode, ...]:
        if num_episodes <= 0:
            raise ValueError("num_episodes doit être strictement positif")

        episodes: List[SelfPlayEpisode] = []
        for index in range(num_episodes):
            seed = None if base_seed is None else base_seed + index
            episode = self.run_episode(
                seed=seed,
                max_steps=max_steps,
                policies=policies,
                store_in_buffer=store_in_buffer,
            )
            episodes.append(episode)
        return tuple(episodes)


__all__ = [
    "RolloutBuffer",
    "SelfPlayEpisode",
    "SelfPlayRunner",
    "SelfPlayTransition",
]
