"""Tests pour la parallélisation des rollouts (SIM-003).

Ces tests valident que nous pouvons exécuter plusieurs parties en parallèle tout
en conservant des métriques déterministes et agrégées. Les exigences proviennent
de `docs/architecture.md` (section catan.sim) et `docs/rl-objectives.md`
concernant le throughput et la reproductibilité.
"""

from __future__ import annotations

import dataclasses

import pytest

from catan.sim.parallel import (
    EpisodeSummary,
    ParallelRolloutRunner,
    RolloutSummary,
    WorkerSummary,
)
from .sim_test_utils import FirstLegalPolicy


def _make_runner(
    *,
    num_workers: int,
    total_episodes: int,
    max_steps: int,
    base_seed: int,
) -> ParallelRolloutRunner:
    return ParallelRolloutRunner(
        policy_factory=lambda worker_id: FirstLegalPolicy(),
        total_episodes=total_episodes,
        num_workers=num_workers,
        max_steps_per_episode=max_steps,
        base_seed=base_seed,
        executor_kind="thread",
    )


def test_parallel_runner_distributes_episodes_evenly():
    """Les épisodes doivent être répartis équitablement entre les workers."""

    runner = _make_runner(
        num_workers=3,
        total_episodes=9,
        max_steps=2,
        base_seed=120,
    )
    summary = runner.run()

    assert dataclasses.is_dataclass(summary)
    assert summary.total_episodes == 9
    assert summary.total_steps == 18
    assert len(summary.worker_summaries) == 3

    episode_counts = sorted(worker.episodes for worker in summary.worker_summaries)
    assert episode_counts == [3, 3, 3]

    for worker in summary.worker_summaries:
        assert dataclasses.is_dataclass(worker)
        assert worker.steps == worker.episodes * 2


def test_parallel_runner_generates_unique_seeds():
    """Chaque épisode devrait recevoir une seed unique dérivée de base_seed."""

    runner = _make_runner(
        num_workers=2,
        total_episodes=5,
        max_steps=1,
        base_seed=321,
    )
    summary = runner.run()

    seeds = [seed for worker in summary.worker_summaries for seed in worker.episode_seeds]
    assert len(seeds) == 5
    assert len(set(seeds)) == 5
    assert set(seeds) == set(range(321, 326))


def test_parallel_runner_is_reproducible_with_same_seed():
    """Deux exécutions avec les mêmes paramètres doivent produire le même résumé."""

    runner_a = _make_runner(
        num_workers=2,
        total_episodes=4,
        max_steps=3,
        base_seed=777,
    )
    runner_b = _make_runner(
        num_workers=2,
        total_episodes=4,
        max_steps=3,
        base_seed=777,
    )

    summary_a = runner_a.run()
    summary_b = runner_b.run()

    assert summary_a.total_episodes == summary_b.total_episodes
    assert summary_a.total_steps == summary_b.total_steps
    assert summary_a.worker_summaries == summary_b.worker_summaries


def test_parallel_runner_raises_if_workers_invalid():
    """La configuration doit valider le nombre de workers et d'épisodes."""

    with pytest.raises(ValueError):
        _make_runner(num_workers=0, total_episodes=1, max_steps=1, base_seed=0)

    with pytest.raises(ValueError):
        _make_runner(num_workers=1, total_episodes=0, max_steps=1, base_seed=0)

    with pytest.raises(ValueError):
        _make_runner(num_workers=1, total_episodes=1, max_steps=0, base_seed=0)


def test_rollout_summary_compact_traces_and_kpis():
    """Les résumés doivent fournir des traces compactes et des KPIs agrégés."""

    episodes = (
        EpisodeSummary(seed=1, steps=5, done=True, winner_id=0, duration_seconds=0.5),
        EpisodeSummary(seed=2, steps=7, done=True, winner_id=1, duration_seconds=0.7),
        EpisodeSummary(seed=3, steps=4, done=False, winner_id=None, duration_seconds=0.4),
    )
    worker = WorkerSummary(worker_id=0, episode_summaries=episodes, duration_seconds=1.6)
    summary = RolloutSummary(worker_summaries=(worker,), duration_seconds=1.6)

    traces = summary.compact_traces
    assert isinstance(traces, tuple)
    assert len(traces) == 3
    assert traces[0]["seed"] == 1
    assert traces[0]["steps"] == 5
    assert traces[0]["done"] is True
    assert traces[0]["winner_id"] == 0
    assert traces[0]["duration_seconds"] == pytest.approx(0.5)

    kpis = summary.kpis
    assert kpis.total_episodes == 3
    assert kpis.completed_episodes == 2
    assert kpis.mean_episode_steps == pytest.approx((5 + 7 + 4) / 3)
    assert kpis.mean_episode_duration_seconds == pytest.approx((0.5 + 0.7 + 0.4) / 3)
    assert kpis.wins_by_player == (1, 1)
    assert kpis.win_rate_by_player == pytest.approx((0.5, 0.5))


def test_rollout_summary_kpis_handle_zero_completed_games():
    """La victoire doit retourner 0 lorsque aucun épisode n'est terminé."""

    episodes = (
        EpisodeSummary(seed=10, steps=3, done=False, winner_id=None, duration_seconds=0.2),
    )
    worker = WorkerSummary(worker_id=0, episode_summaries=episodes, duration_seconds=0.2)
    summary = RolloutSummary(worker_summaries=(worker,), duration_seconds=0.2)

    kpis = summary.kpis
    assert kpis.total_episodes == 1
    assert kpis.completed_episodes == 0
    assert kpis.mean_episode_steps == pytest.approx(3)
    assert kpis.mean_episode_duration_seconds == pytest.approx(0.2)
    assert kpis.wins_by_player == (0, 0)
    assert kpis.win_rate_by_player == (0.0, 0.0)
