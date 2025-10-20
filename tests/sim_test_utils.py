"""Utilitaires spécifiques aux tests de simulation parallélisée.

Ce module regroupe des politiques déterministes simples afin de rendre les
rollouts prédictibles dans les tests liés à SIM-003.
"""

from __future__ import annotations

from typing import Sequence

from catan.engine.actions import Action
from catan.rl.policies import AgentPolicy


class FirstLegalPolicy(AgentPolicy):
    """Politique déterministe retournant la première action légale disponible."""

    def __init__(self) -> None:
        super().__init__(name="FirstLegal")

    def select_action(self, state) -> Action:  # type: ignore[override]
        legal: Sequence[Action] = tuple(state.legal_actions())
        if not legal:
            raise ValueError("Aucune action légale disponible pour FirstLegalPolicy")
        return legal[0]
