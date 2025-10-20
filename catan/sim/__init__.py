"""Simulation headless et parallélisation (SIM-001 / SIM-003)."""

from .parallel import ParallelRolloutRunner, RolloutSummary, WorkerSummary
from .runner import HeadlessEnv, StepResult, build_default_action_catalog

__all__ = [
    "HeadlessEnv",
    "StepResult",
    "build_default_action_catalog",
    "ParallelRolloutRunner",
    "RolloutSummary",
    "WorkerSummary",
]
