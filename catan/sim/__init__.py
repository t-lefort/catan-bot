"""Simulation headless et parallélisation (SIM-001 / SIM-003)."""

from .parallel import (
    EpisodeSummary,
    ParallelRolloutRunner,
    RolloutKPIs,
    RolloutSummary,
    WorkerSummary,
)
from .runner import HeadlessEnv, StepResult, build_default_action_catalog

__all__ = [
    "HeadlessEnv",
    "StepResult",
    "build_default_action_catalog",
    "EpisodeSummary",
    "ParallelRolloutRunner",
    "RolloutKPIs",
    "RolloutSummary",
    "WorkerSummary",
]
