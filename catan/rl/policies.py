"""Politiques de base pour la simulation et l'évaluation (tâche RL-003)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Mapping, MutableMapping, Optional, Sequence

from catan.engine.actions import (
    AcceptPlayerTrade,
    Action,
    BuildCity,
    BuyDevelopment,
    DeclinePlayerTrade,
    DiscardResources,
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
from catan.engine.rules import COSTS
from catan.engine.state import GameState, Player, SetupPhase, TurnSubPhase, RESOURCE_TYPES

ResourceMap = Mapping[str, int]
MutableResourceMap = MutableMapping[str, int]


class AgentPolicy:
    """Interface minimale utilisée par la simulation headless."""

    def __init__(self, *, name: str | None = None) -> None:
        self._name = name or self.__class__.__name__

    @property
    def name(self) -> str:
        return self._name

    def select_action(self, state: GameState) -> Action:
        raise NotImplementedError


class RandomLegalPolicy(AgentPolicy):
    """Politique uniformément aléatoire sur les actions légales."""

    def __init__(
        self,
        *,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(name="RandomLegal")
        self._random = rng or random.Random(seed)

    def select_action(self, state: GameState) -> Action:
        legal = list(state.legal_actions())
        if not legal:
            raise ValueError("Aucune action légale disponible pour RandomLegalPolicy")
        return self._random.choice(legal)


@dataclass(frozen=True)
class _HeuristicContext:
    state: GameState
    legal: Sequence[Action]
    board: Board
    current: Player
    opponent: Player


class HeuristicPolicy(AgentPolicy):
    """Politique heuristique v1 inspirée des priorités humaines classiques."""

    _RESOURCE_PRIORITY: Dict[str, int] = {
        "ORE": 5,
        "GRAIN": 4,
        "BRICK": 3,
        "LUMBER": 2,
        "WOOL": 1,
    }

    def __init__(self) -> None:
        super().__init__(name="HeuristicV1")

    def select_action(self, state: GameState) -> Action:
        legal = tuple(state.legal_actions())
        if not legal:
            raise ValueError("Aucune action légale disponible pour HeuristicPolicy")

        context = _HeuristicContext(
            state=state,
            legal=legal,
            board=state.board,
            current=state.players[state.current_player_id],
            opponent=state.players[1 - state.current_player_id],
        )

        if state.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2):
            return self._select_setup_action(context)

        if state.turn_subphase == TurnSubPhase.ROBBER_DISCARD:
            return min(legal, key=self._score_discard_action)

        if state.turn_subphase == TurnSubPhase.ROBBER_MOVE:
            return max(legal, key=lambda action: self._score_robber_move(context, action))

        if state.turn_subphase == TurnSubPhase.TRADE_RESPONSE:
            return max(
                legal,
                key=lambda action: self._score_trade_response(context, action),
            )

        return max(
            legal,
            key=lambda action: self._score_main_phase_action(context, action),
        )

    # -- Setup -----------------------------------------------------------------

    def _select_setup_action(self, context: _HeuristicContext) -> Action:
        settlements = [action for action in context.legal if isinstance(action, PlaceSettlement)]
        if settlements:
            return max(
                settlements,
                key=lambda action: self._vertex_value(context.board, action.vertex_id),
            )

        roads = [action for action in context.legal if isinstance(action, PlaceRoad)]
        if roads:
            return max(
                roads,
                key=lambda action: self._road_value(context.board, action.edge_id),
            )

        return context.legal[0]

    @staticmethod
    def _vertex_value(board: Board, vertex_id: int) -> float:
        vertex = board.vertices[vertex_id]
        return sum((board.tiles[tile_id].pip or 0.0) for tile_id in vertex.adjacent_tiles)

    def _road_value(self, board: Board, edge_id: int) -> float:
        edge = board.edges[edge_id]
        return sum(self._vertex_value(board, vertex_id) for vertex_id in edge.vertices)

    # -- Phase principale ------------------------------------------------------

    def _score_main_phase_action(self, context: _HeuristicContext, action: Action) -> float:
        state = context.state
        current = context.current

        if isinstance(action, RollDice):
            return 1000.0 if not state.dice_rolled_this_turn else 0.0

        if isinstance(action, BuildCity):
            return 900.0 + self._vertex_value(context.board, action.vertex_id)

        if isinstance(action, PlaceSettlement):
            base = 800.0 if not action.free else 850.0
            return base + self._vertex_value(context.board, action.vertex_id)

        if isinstance(action, PlaceRoad):
            return 600.0 + self._road_value(context.board, action.edge_id)

        if isinstance(action, TradeBank):
            return self._score_trade_bank(context, action)

        if isinstance(action, BuyDevelopment):
            return 550.0

        if isinstance(action, PlayKnight):
            return 520.0

        if isinstance(action, PlayProgress):
            return self._score_progress_card(context, action)

        if isinstance(action, OfferPlayerTrade):
            return self._score_offer_trade(context, action)

        if isinstance(action, EndTurn):
            return 5.0

        # Actions par défaut (acceptations, etc.)
        return 10.0

    def _score_trade_bank(self, context: _HeuristicContext, action: TradeBank) -> float:
        projected = self._resources_after_trade(context.current.resources, action)
        if self._would_enable_city(context, projected):
            return 880.0
        if self._would_enable_settlement(projected, context):
            return 750.0
        if self._can_afford(projected, COSTS["road"]):
            return 620.0

        desirability = sum(
            self._RESOURCE_PRIORITY.get(resource, 0) * amount
            for resource, amount in action.receive.items()
        )
        penalty = sum(action.give.values())
        return 400.0 + desirability * 8.0 - penalty * 2.0

    def _score_progress_card(self, context: _HeuristicContext, action: PlayProgress) -> float:
        if action.card == "ROAD_BUILDING":
            return 610.0
        if action.card == "YEAR_OF_PLENTY":
            desirability = sum(
                self._RESOURCE_PRIORITY.get(res, 0) * amount
                for res, amount in (action.resources or {}).items()
            )
            return 500.0 + desirability * 5.0
        if action.card == "MONOPOLY":
            priority = self._RESOURCE_PRIORITY.get(action.resource or "", 0)
            return 480.0 + priority * 10.0
        return 450.0

    def _score_offer_trade(self, context: _HeuristicContext, action: OfferPlayerTrade) -> float:
        desirability = sum(
            self._RESOURCE_PRIORITY.get(res, 0) * amount
            for res, amount in action.receive.items()
        )
        cost = sum(
            self._RESOURCE_PRIORITY.get(res, 0) * amount
            for res, amount in action.give.items()
        )
        return 150.0 + desirability * 5.0 - cost * 3.0

    def _resources_after_trade(
        self,
        resources: MutableResourceMap,
        action: TradeBank,
    ) -> Dict[str, int]:
        updated = {resource: resources.get(resource, 0) for resource in RESOURCE_TYPES}
        for resource, amount in action.give.items():
            updated[resource] = max(0, updated.get(resource, 0) - amount)
        for resource, amount in action.receive.items():
            updated[resource] = updated.get(resource, 0) + amount
        return updated

    def _would_enable_city(
        self,
        context: _HeuristicContext,
        projected: ResourceMap,
    ) -> bool:
        if not context.current.settlements:
            return False
        return self._can_afford(projected, COSTS["city"])

    def _would_enable_settlement(
        self,
        projected: ResourceMap,
        context: _HeuristicContext,
    ) -> bool:
        if not self._can_afford(projected, COSTS["settlement"]):
            return False
        # Vérifie qu'au moins une action de colonie reste potentiellement disponible
        return any(
            isinstance(action, PlaceSettlement) and not action.free
            for action in context.legal
        )

    @staticmethod
    def _can_afford(resources: ResourceMap, cost: Mapping[str, int]) -> bool:
        return all(resources.get(resource, 0) >= amount for resource, amount in cost.items())

    # -- Robber ----------------------------------------------------------------

    def _score_robber_move(self, context: _HeuristicContext, action: Action) -> float:
        if not isinstance(action, MoveRobber):
            return 0.0
        tile = context.board.tiles.get(action.tile_id)
        pip_value = float(tile.pip or 0)
        steal_bonus = 0.0
        if action.steal_from is not None:
            victim = context.state.players[action.steal_from]
            steal_bonus = sum(victim.resources.values()) * 2.0
        return pip_value * 5.0 + steal_bonus

    def _score_trade_response(self, context: _HeuristicContext, action: Action) -> float:
        pending = context.state.pending_player_trade
        if pending is None:
            return 0.0
        if isinstance(action, AcceptPlayerTrade):
            gain = sum(
                self._RESOURCE_PRIORITY.get(res, 0) * amount
                for res, amount in pending.receive.items()
            )
            cost = sum(
                self._RESOURCE_PRIORITY.get(res, 0) * amount
                for res, amount in pending.give.items()
            )
            return 50.0 + gain * 4.0 - cost * 3.0
        if isinstance(action, DeclinePlayerTrade):
            return 40.0
        return 0.0

    def _score_discard_action(self, action: Action) -> float:
        if not isinstance(action, DiscardResources):
            return 0.0
        return sum(
            self._RESOURCE_PRIORITY.get(resource, 0) * amount
            for resource, amount in action.resources.items()
        )


__all__ = ["AgentPolicy", "RandomLegalPolicy", "HeuristicPolicy"]
