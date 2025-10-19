"""Évènements publiés par la couche application (`catan.app`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from catan.engine.actions import Action
from catan.engine.state import GameState


@dataclass(frozen=True)
class GameStartedEvent:
    """Émis lorsqu'une nouvelle partie est initialisée."""

    state: GameState


@dataclass(frozen=True)
class ActionAppliedEvent:
    """Émis après qu'une action légale a été appliquée."""

    action: Action
    previous_state: GameState
    new_state: GameState


@dataclass(frozen=True)
class GameEndedEvent:
    """Émis quand `GameState.is_game_over` devient vrai."""

    state: GameState
    winner_id: Optional[int]
