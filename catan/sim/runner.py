"""Boucle headless pour le moteur Catane (SIM-001).

Ce module expose un environnement minimaliste pour piloter le moteur via une
API `reset()` / `step()` et fournir un masque d'actions stable. Il servira de
base aux tâches SIM-001+ et RL-00X.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from itertools import combinations, combinations_with_replacement
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from catan.engine.actions import (
    AcceptPlayerTrade,
    Action,
    BuyDevelopment,
    BuildCity,
    DeclinePlayerTrade,
    EndTurn,
    MoveRobber,
    OfferPlayerTrade,
    PlaceRoad,
    PlaceSettlement,
    PlayKnight,
    PlayProgress,
    RollDice,
    TradeBank,
)
from catan.engine.board import Board
from catan.engine.state import GameState, RESOURCE_TYPES

ActionKey = Tuple[str, Tuple[Tuple[str, Any], ...]]


def _normalize_value(value: Any) -> Any:
    """Transforme récursivement une valeur potentiellement mutable en forme hashable."""

    if isinstance(value, dict):
        return tuple(sorted((k, _normalize_value(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_normalize_value(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_normalize_value(v) for v in value)
    return value


def _action_key(action: Action) -> ActionKey:
    """Crée une clé hashable pour un objet Action."""

    fields = dataclasses.fields(action)
    payload = tuple(
        (field.name, _normalize_value(getattr(action, field.name)))
        for field in fields
    )
    return (action.__class__.__name__, payload)


class ActionSpace:
    """Maintient un catalogue d'actions unique et fournit des masques."""

    def __init__(self, initial_actions: Sequence[Action] | None = None) -> None:
        self._catalog: List[Action] = []
        self._keys: List[ActionKey] = []
        self._key_to_index: Dict[ActionKey, int] = {}
        if initial_actions:
            self.register(initial_actions)

    @property
    def catalog(self) -> List[Action]:
        """Retourne une copie du catalogue courant."""

        return list(self._catalog)

    def register(self, actions: Iterable[Action]) -> None:
        """Ajoute les actions au catalogue si elles n'y figurent pas déjà."""

        for action in actions:
            key = _action_key(action)
            if key in self._key_to_index:
                continue
            index = len(self._catalog)
            self._catalog.append(action)
            self._keys.append(key)
            self._key_to_index[key] = index

    def mask(self, legal_actions: Iterable[Action]) -> List[bool]:
        """Construit le masque booléen aligné sur le catalogue courant."""

        legal_keys = {_action_key(action) for action in legal_actions}
        return [key in legal_keys for key in self._keys]


def build_default_action_catalog(board: Board | None = None) -> List[Action]:
    """Construit le catalogue d'actions 1v1 utilisé par défaut.

    Les actions dynamiques (ex: défausses toutes combinaisons) seront ajoutées
    à la volée via ActionSpace.register.
    """

    board = board or Board.standard()
    catalog: List[Action] = []

    # Setup et constructions
    for vertex_id in board.vertices.keys():
        catalog.append(PlaceSettlement(vertex_id=vertex_id, free=True))
        catalog.append(PlaceSettlement(vertex_id=vertex_id, free=False))
        catalog.append(BuildCity(vertex_id=vertex_id))

    for edge_id in board.edges.keys():
        catalog.append(PlaceRoad(edge_id=edge_id, free=True))
        catalog.append(PlaceRoad(edge_id=edge_id, free=False))

    # Actions globales
    catalog.append(RollDice())
    catalog.append(EndTurn())
    catalog.append(BuyDevelopment())
    catalog.append(PlayKnight())

    # Progress cards
    edge_ids = list(board.edges.keys())
    for edge_a, edge_b in combinations(edge_ids, 2):
        catalog.append(
            PlayProgress(card="ROAD_BUILDING", edges=[edge_a, edge_b])
        )

    for res_a, res_b in combinations_with_replacement(RESOURCE_TYPES, 2):
        resources: Dict[str, int] = {}
        resources[res_a] = resources.get(res_a, 0) + 1
        resources[res_b] = resources.get(res_b, 0) + 1
        catalog.append(PlayProgress(card="YEAR_OF_PLENTY", resources=resources))

    for resource in RESOURCE_TYPES:
        catalog.append(PlayProgress(card="MONOPOLY", resource=resource))

    # Robber moves
    for tile_id in board.tiles.keys():
        catalog.append(MoveRobber(tile_id=tile_id, steal_from=None))
        for player_id in range(2):
            catalog.append(MoveRobber(tile_id=tile_id, steal_from=player_id))

    # Trades banque/ports
    for give_resource in RESOURCE_TYPES:
        for receive_resource in RESOURCE_TYPES:
            for rate in (4, 3, 2):
                for give_amount in range(rate, 19, rate):
                    receive_amount = give_amount // rate
                    catalog.append(
                        TradeBank(
                            give={give_resource: give_amount},
                            receive={receive_resource: receive_amount},
                        )
                    )

    # Trades joueur ↔ joueur (unitaires)
    for give_resource in RESOURCE_TYPES:
        for receive_resource in RESOURCE_TYPES:
            if give_resource == receive_resource:
                continue
            catalog.append(
                OfferPlayerTrade(
                    give={give_resource: 1},
                    receive={receive_resource: 1},
                )
            )

    catalog.append(AcceptPlayerTrade())
    catalog.append(DeclinePlayerTrade())

    return catalog


@dataclass(frozen=True)
class StepResult:
    """Résultat d'un appel à HeadlessEnv.step()."""

    state: GameState
    reward: Tuple[float, ...]
    done: bool
    info: Dict[str, Any]


class HeadlessEnv:
    """Environnement headless léger pour le moteur Catane."""

    def __init__(
        self,
        *,
        seed: int | None = None,
        action_catalog: Sequence[Action] | None = None,
    ) -> None:
        self._base_seed = seed
        self._state: GameState | None = None
        self._base_catalog = (
            list(action_catalog) if action_catalog is not None else build_default_action_catalog()
        )
        self._action_space = ActionSpace(self._base_catalog)

    @property
    def state(self) -> GameState:
        """Retourne l'état courant (reset doit avoir été appelé)."""

        if self._state is None:
            raise RuntimeError("reset() doit être appelé avant d'accéder à l'état")
        return self._state

    @property
    def action_catalog(self) -> List[Action]:
        """Retourne le catalogue courant."""

        return self._action_space.catalog

    def reset(
        self,
        *,
        seed: int | None = None,
        state: GameState | None = None,
    ) -> GameState:
        """Réinitialise l'environnement et renvoie l'état initial."""

        if state is not None:
            self._state = state
        else:
            effective_seed = seed if seed is not None else self._base_seed
            self._state = GameState.new_1v1_game(seed=effective_seed)

        # Réinitialiser l'espace d'actions
        self._action_space = ActionSpace(self._base_catalog)
        self._action_space.register(self._state.legal_actions())
        return self._state

    def legal_actions(self) -> List[Action]:
        """Retourne les actions légales de l'état courant."""

        return self.state.legal_actions()

    def legal_actions_mask(self) -> List[bool]:
        """Retourne un masque booléen aligné sur le catalogue courant."""

        legal = self.state.legal_actions()
        self._action_space.register(legal)
        return self._action_space.mask(legal)

    def step(self, action: Action) -> StepResult:
        """Applique une action et renvoie le résultat."""

        current_state = self.state
        if not current_state.is_action_legal(action):
            raise ValueError(f"Action illégale: {action}")

        new_state = current_state.apply_action(action)
        self._state = new_state
        self._action_space.register(new_state.legal_actions())

        reward = tuple(0.0 for _ in new_state.players)
        done = new_state.is_game_over
        info = {"last_action": action}

        return StepResult(state=new_state, reward=reward, done=done, info=info)
