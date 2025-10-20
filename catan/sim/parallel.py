"""Parallélisation des rollouts headless (SIM-003).

Ce module fournit une API simple pour lancer plusieurs parties Catane en
parallèle, en s'appuyant sur `catan.sim.runner.HeadlessEnv`. Les exigences
principales proviennent de `PLAN.yaml` (tâche SIM-003) :

- N workers indépendants (thread ou process) pouvant exécuter des parties.
- Agrégation de métriques de base (nombre d'épisodes, nombre d'actions).
- Reproductibilité via une seed de base.

La mise en œuvre privilégie un design testable et extensible : chaque worker
utilise sa propre instance d'environnement et de politique, et le résultat
exposé est une dataclass immuable résumant les métriques collectées.
"""

from __future__ import annotations

import time
import pickle
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Literal, Tuple

from catan.rl.policies import AgentPolicy
from catan.sim.runner import HeadlessEnv

ExecutorKind = Literal["thread", "process"]


@dataclass(frozen=True)
class EpisodeSummary:
    """Résume un épisode simulé par un worker."""

    seed: int
    steps: int
    done: bool
    winner_id: int | None


@dataclass(frozen=True)
class WorkerSummary:
    """Agrège les métriques d'un worker donné."""

    worker_id: int
    episode_summaries: Tuple[EpisodeSummary, ...]
    duration_seconds: float = field(default=0.0, compare=False)

    @property
    def episodes(self) -> int:
        return len(self.episode_summaries)

    @property
    def episode_seeds(self) -> Tuple[int, ...]:
        return tuple(summary.seed for summary in self.episode_summaries)

    @property
    def steps(self) -> int:
        return sum(summary.steps for summary in self.episode_summaries)


@dataclass(frozen=True)
class RolloutSummary:
    """Résumé global renvoyé par `ParallelRolloutRunner.run()`."""

    worker_summaries: Tuple[WorkerSummary, ...]
    duration_seconds: float = field(default=0.0, compare=False)

    @property
    def total_workers(self) -> int:
        return len(self.worker_summaries)

    @property
    def total_episodes(self) -> int:
        return sum(worker.episodes for worker in self.worker_summaries)

    @property
    def total_steps(self) -> int:
        return sum(worker.steps for worker in self.worker_summaries)


def _validate_positive(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} doit être strictement positif (reçu: {value})")


def _distribute_episodes(total_episodes: int, num_workers: int, base_seed: int) -> Tuple[Tuple[int, Tuple[int, ...]], ...]:
    """Répartit les seeds d'épisodes entre les workers."""

    base = total_episodes // num_workers
    remainder = total_episodes % num_workers
    current_seed = base_seed
    assignments = []

    for worker_id in range(num_workers):
        count = base + (1 if worker_id < remainder else 0)
        seeds = tuple(range(current_seed, current_seed + count)) if count else tuple()
        current_seed += count
        assignments.append((worker_id, seeds))

    return tuple(assignments)


def _run_worker(
    worker_id: int,
    episode_seeds: Tuple[int, ...],
    max_steps_per_episode: int,
    policy_factory: Callable[[int], AgentPolicy],
) -> WorkerSummary:
    """Exécute la boucle de simulation pour un worker donné."""

    start = time.perf_counter()
    if not episode_seeds:
        return WorkerSummary(worker_id=worker_id, episode_summaries=tuple(), duration_seconds=0.0)

    policy = policy_factory(worker_id)
    env = HeadlessEnv()
    episodes: list[EpisodeSummary] = []

    for seed in episode_seeds:
        state = env.reset(seed=seed)
        steps = 0
        done = False
        winner_id: int | None = None

        while steps < max_steps_per_episode:
            action = policy.select_action(state)
            result = env.step(action)
            steps += 1
            state = result.state

            if result.done:
                done = True
                winner_id = state.winner_id
                break

        episodes.append(
            EpisodeSummary(
                seed=seed,
                steps=steps,
                done=done,
                winner_id=winner_id,
            )
        )

    duration = time.perf_counter() - start
    return WorkerSummary(
        worker_id=worker_id,
        episode_summaries=tuple(episodes),
        duration_seconds=duration,
    )


class ParallelRolloutRunner:
    """Orchestre l'exécution de plusieurs rollouts Catane en parallèle."""

    def __init__(
        self,
        *,
        policy_factory: Callable[[int], AgentPolicy],
        total_episodes: int,
        num_workers: int,
        max_steps_per_episode: int,
        base_seed: int = 0,
        executor_kind: ExecutorKind = "process",
    ) -> None:
        _validate_positive("num_workers", num_workers)
        _validate_positive("total_episodes", total_episodes)
        _validate_positive("max_steps_per_episode", max_steps_per_episode)

        if executor_kind not in ("thread", "process"):
            raise ValueError("executor_kind doit valoir 'thread' ou 'process'")

        if executor_kind == "process":
            try:
                pickle.dumps(policy_factory)
            except Exception as exc:  # pragma: no cover - erreur anticipée
                raise TypeError(
                    "policy_factory doit être picklable pour executor_kind='process'"
                ) from exc

        self._policy_factory = policy_factory
        self._total_episodes = total_episodes
        self._num_workers = num_workers
        self._max_steps_per_episode = max_steps_per_episode
        self._base_seed = base_seed
        self._executor_kind = executor_kind

    def _compute_assignments(self) -> Tuple[Tuple[int, Tuple[int, ...]], ...]:
        return _distribute_episodes(self._total_episodes, self._num_workers, self._base_seed)

    def run(self) -> RolloutSummary:
        """Exécute les rollouts et renvoie un résumé agrégé."""

        assignments = self._compute_assignments()
        start = time.perf_counter()

        # Cas trivial: un seul worker → exécution synchrone.
        if self._num_workers == 1:
            worker_id, seeds = assignments[0]
            summary = _run_worker(worker_id, seeds, self._max_steps_per_episode, self._policy_factory)
            duration = time.perf_counter() - start
            return RolloutSummary(worker_summaries=(summary,), duration_seconds=duration)

        worker_summaries: list[WorkerSummary]

        if self._executor_kind == "thread":
            with ThreadPoolExecutor(max_workers=self._num_workers) as executor:
                futures = [
                    executor.submit(
                        _run_worker,
                        worker_id,
                        seeds,
                        self._max_steps_per_episode,
                        self._policy_factory,
                    )
                    for worker_id, seeds in assignments
                ]
                worker_summaries = [future.result() for future in futures]
        else:
            with ProcessPoolExecutor(max_workers=self._num_workers) as executor:
                futures = [
                    executor.submit(
                        _run_worker,
                        worker_id,
                        seeds,
                        self._max_steps_per_episode,
                        self._policy_factory,
                    )
                    for worker_id, seeds in assignments
                ]
                worker_summaries = [future.result() for future in futures]

        duration = time.perf_counter() - start
        return RolloutSummary(worker_summaries=tuple(worker_summaries), duration_seconds=duration)


__all__ = [
    "EpisodeSummary",
    "WorkerSummary",
    "RolloutSummary",
    "ParallelRolloutRunner",
]
