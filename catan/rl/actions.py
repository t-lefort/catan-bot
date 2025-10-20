"""Utilitaires d'encodage d'actions pour le RL (tâche RL-002)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

from catan.engine.actions import (
    Action,
    AcceptPlayerTrade,
    DeclinePlayerTrade,
    MoveRobber,
    PlaceRoad,
    PlaceSettlement,
    RollDice,
)
from catan.engine.board import Board
from catan.engine.state import GameState, RESOURCE_TYPES
from catan.sim.runner import ActionSpace, build_default_action_catalog

CatanatronSignature = Tuple[str, Optional[object]]


@dataclass
class ActionEncoder:
    """Encapsule ActionSpace pour les besoins RL."""

    board: Board
    _space: ActionSpace

    def __init__(
        self,
        *,
        board: Board | None = None,
        catalog: Sequence[Action] | None = None,
    ) -> None:
        resolved_board = board or Board.standard()
        base_catalog = catalog or build_default_action_catalog(resolved_board)
        self.board = resolved_board
        self._space = ActionSpace(base_catalog)

    @property
    def size(self) -> int:
        """Taille actuelle du catalogue."""

        return len(self._space)

    def catalog(self) -> Sequence[Action]:
        """Renvoie une copie du catalogue courant."""

        return self._space.catalog

    def encode(self, action: Action) -> int:
        """Retourne l'index associé à une action (enregistrée si nécessaire)."""

        self._space.register([action])
        try:
            return self._space.index(action)
        except KeyError as exc:
            raise ValueError(f"Action inconnue pour l'encodeur: {action}") from exc

    def build_mask(self, state: GameState) -> np.ndarray:
        """Construit le masque booléen des actions légales."""

        legal = state.legal_actions()
        self._space.register(legal)
        mask = self._space.mask(legal)
        return np.array(mask, dtype=np.bool_)

    def decode(self, index: int, legal_actions: Iterable[Action]) -> Action:
        """Retrouve une action légale à partir de son index."""

        try:
            template = self._space.action_at(index)
        except IndexError as exc:  # pragma: no cover - invalide par usage normal
            raise ValueError(f"Index d'action invalide: {index}") from exc

        for action in legal_actions:
            if action == template:
                return action
        raise ValueError("Aucune action légale correspondante trouvée")


def action_to_catanatron_signature(board: Board, action: Action) -> CatanatronSignature:
    """Convertit une action en signature (type, valeur) proche de catanatron."""

    if isinstance(action, RollDice):
        return ("ROLL_DICE", None)

    if isinstance(action, PlaceSettlement):
        return ("BUILD_SETTLEMENT", action.vertex_id)

    if isinstance(action, PlaceRoad):
        edge = board.edges.get(action.edge_id)
        vertices = tuple(sorted(edge.vertices)) if edge else ()
        return ("BUILD_ROAD", vertices)

    if isinstance(action, MoveRobber):
        steal_target = action.steal_from
        return ("MOVE_ROBBER", (action.tile_id, steal_target))

    if isinstance(action, AcceptPlayerTrade):
        return ("ACCEPT_PLAYER_TRADE", None)

    if isinstance(action, DeclinePlayerTrade):
        return ("DECLINE_PLAYER_TRADE", None)

    if action.__class__.__name__.upper() in RESOURCE_TYPES:
        # Couvrir les cartes progrès (placeholder) — conversion plus fine ultérieure.
        return (action.__class__.__name__.upper(), None)

    return (action.__class__.__name__.upper(), None)


__all__ = ["ActionEncoder", "action_to_catanatron_signature"]
