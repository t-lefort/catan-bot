"""État du jeu et logique de transition (ENG-002+).

Ce module définit l'état immuable d'une partie et les transitions d'état.
Conforme aux schémas (docs/schemas.md) et specs (docs/specs.md).
"""

from __future__ import annotations

import copy
import random
from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, cast

from catan.engine.board import Board
from catan.engine.rules import COSTS, DISCARD_THRESHOLD, VP_TO_WIN

RESOURCE_TYPES: tuple[str, ...] = ("BRICK", "LUMBER", "WOOL", "GRAIN", "ORE")
DEV_CARD_TYPES: tuple[str, ...] = (
    "KNIGHT",
    "ROAD_BUILDING",
    "YEAR_OF_PLENTY",
    "MONOPOLY",
    "VICTORY_POINT",
)
PROGRESS_CARD_TYPES: tuple[str, ...] = (
    "ROAD_BUILDING",
    "YEAR_OF_PLENTY",
    "MONOPOLY",
)
DEFAULT_DEV_DECK: tuple[str, ...] = (
    ("KNIGHT",) * 14
    + ("VICTORY_POINT",) * 5
    + ("ROAD_BUILDING",) * 2
    + ("YEAR_OF_PLENTY",) * 2
    + ("MONOPOLY",) * 2
)
BANK_STARTING_RESOURCES: Dict[str, int] = {
    "BRICK": 19,
    "LUMBER": 19,
    "WOOL": 19,
    "GRAIN": 19,
    "ORE": 19,
}

RngState = Tuple[Any, ...]


@dataclass
class Player:
    """Représentation d'un joueur."""

    player_id: int
    name: str
    resources: Dict[str, int] = field(
        default_factory=lambda: {resource: 0 for resource in RESOURCE_TYPES}
    )
    settlements: List[int] = field(default_factory=list)  # vertex_ids
    cities: List[int] = field(default_factory=list)  # vertex_ids
    roads: List[int] = field(default_factory=list)  # edge_ids
    dev_cards: Dict[str, int] = field(
        default_factory=lambda: {card: 0 for card in DEV_CARD_TYPES}
    )
    new_dev_cards: Dict[str, int] = field(
        default_factory=lambda: {card: 0 for card in DEV_CARD_TYPES}
    )
    played_dev_cards: Dict[str, int] = field(
        default_factory=lambda: {card: 0 for card in ("KNIGHT",) + PROGRESS_CARD_TYPES}
    )
    victory_points: int = 0
    hidden_victory_points: int = 0


@dataclass(frozen=True)
class PendingPlayerTrade:
    """Échange joueur↔joueur en attente de réponse."""

    proposer_id: int
    responder_id: int
    give: Dict[str, int]
    receive: Dict[str, int]


class SetupPhase(Enum):
    """Phases de setup."""

    SETUP_ROUND_1 = "SETUP_ROUND_1"
    SETUP_ROUND_2 = "SETUP_ROUND_2"
    PLAY = "PLAY"


class TurnSubPhase(Enum):
    """Sous-phases d'un tour en phase PLAY."""

    MAIN = "MAIN"
    ROBBER_DISCARD = "ROBBER_DISCARD"
    ROBBER_MOVE = "ROBBER_MOVE"
    TRADE_RESPONSE = "TRADE_RESPONSE"


@dataclass
class GameState:
    """État immuable du jeu.

    Toutes les modifications doivent retourner un nouvel état.
    """

    board: "Board"  # type: ignore
    players: List[Player]
    phase: SetupPhase
    current_player_id: int
    turn_number: int = 0
    # Compteurs de placements pendant setup
    _setup_settlements_placed: int = 0
    _setup_roads_placed: int = 0
    _waiting_for_road: bool = False  # True si colonie placée, en attente de route
    # État du lancer de dés
    last_dice_roll: int | None = None
    dice_rolled_this_turn: bool = False
    turn_subphase: "TurnSubPhase" = TurnSubPhase.MAIN
    pending_discards: Dict[int, int] = field(default_factory=dict)
    pending_discard_queue: List[int] = field(default_factory=list)
    pending_player_trade: PendingPlayerTrade | None = None
    robber_tile_id: int = 0
    robber_roller_id: int | None = None
    dev_deck: List[str] = field(default_factory=list)
    bank_resources: Dict[str, int] = field(
        default_factory=lambda: dict(BANK_STARTING_RESOURCES)
    )
    rng_state: RngState | None = None
    longest_road_owner: int | None = None
    longest_road_length: int = 0
    largest_army_owner: int | None = None
    largest_army_size: int = 0
    is_game_over: bool = False
    winner_id: int | None = None

    @classmethod
    def new_1v1_game(
        cls,
        player_names: List[str] | None = None,
        *,
        seed: int | None = None,
        dev_deck: List[str] | None = None,
        bank_resources: Dict[str, int] | None = None,
    ) -> "GameState":
        """Crée un nouveau jeu 1v1 avec plateau standard.

        Args:
            player_names: Noms des joueurs (par défaut ["Player 0", "Player 1"])
            dev_deck: Ordre initial des cartes de développement (optionnel)
            bank_resources: Inventaire initial de la banque (optionnel)

        Returns:
            État initial en phase SETUP_ROUND_1
        """

        if player_names is None:
            player_names = ["Player 0", "Player 1"]

        board = Board.standard()
        players = [
            Player(player_id=i, name=name) for i, name in enumerate(player_names)
        ]

        rng = random.Random(seed)

        if dev_deck is None:
            shuffled_deck = list(DEFAULT_DEV_DECK)
            rng.shuffle(shuffled_deck)
        else:
            shuffled_deck = list(dev_deck)

        if bank_resources is None:
            bank = dict(BANK_STARTING_RESOURCES)
        else:
            bank = dict(bank_resources)

        robber_tile_id = next(
            (tile_id for tile_id, tile in board.tiles.items() if tile.has_robber),
            0,
        )

        return cls(
            board=board,
            players=players,
            phase=SetupPhase.SETUP_ROUND_1,
            current_player_id=0,
            turn_number=0,
            robber_tile_id=robber_tile_id,
            dev_deck=shuffled_deck,
            bank_resources=bank,
            rng_state=rng.getstate(),
        )

    def _rng(self) -> random.Random:
        """Retourne un générateur pseudo-aléatoire initialisé avec l'état courant."""
        rng = random.Random()
        if self.rng_state is not None:
            rng.setstate(self.rng_state)
        return rng

    def legal_actions(self) -> List["Action"]:  # type: ignore[name-defined]
        """Retourne la liste des actions légales pour l'état courant."""
        if self.is_game_over:
            return []

        if self.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2):
            return self._legal_actions_setup_phase()

        if self.turn_subphase == TurnSubPhase.ROBBER_DISCARD:
            return self._legal_actions_robber_discard_phase()

        if self.turn_subphase == TurnSubPhase.ROBBER_MOVE:
            return self._legal_actions_robber_move_phase()

        if self.turn_subphase == TurnSubPhase.TRADE_RESPONSE:
            return self._legal_actions_trade_response_phase()

        return self._legal_actions_main_phase()

    def legal_actions_mask(
        self,
        catalog: Iterable["Action"],  # type: ignore[name-defined]
    ) -> List[bool]:
        """Retourne un masque booléen aligné sur un catalogue d'actions."""

        legal = self.legal_actions()
        mask: List[bool] = []
        for template in catalog:
            mask.append(any(template == action for action in legal))
        return mask

    def _legal_actions_setup_phase(self) -> List["Action"]:  # type: ignore[name-defined]
        from catan.engine.actions import PlaceRoad, PlaceSettlement

        actions: List["Action"] = []
        if self._waiting_for_road:
            current_player = self.players[self.current_player_id]
            if current_player.settlements:
                last_settlement = current_player.settlements[-1]
                for edge_id in self.board.vertices[last_settlement].edges:
                    action = PlaceRoad(edge_id=edge_id, free=True)
                    if self.is_action_legal(action):
                        actions.append(action)
        else:
            for vertex_id in self.board.vertices.keys():
                action = PlaceSettlement(vertex_id=vertex_id, free=True)
                if self.is_action_legal(action):
                    actions.append(action)
        return actions

    def _legal_actions_robber_discard_phase(self) -> List["Action"]:  # type: ignore[name-defined]
        from catan.engine.actions import DiscardResources

        required = self.pending_discards.get(self.current_player_id)
        if not required:
            return []

        player = self.players[self.current_player_id]
        actions: List["Action"] = []
        for split in self._generate_discard_splits(player.resources, required):
            action = DiscardResources(resources=split)
            if self.is_action_legal(action):
                actions.append(action)
        return actions

    def _legal_actions_robber_move_phase(self) -> List["Action"]:  # type: ignore[name-defined]
        from catan.engine.actions import MoveRobber

        mover_id = (
            self.robber_roller_id
            if self.robber_roller_id is not None
            else self.current_player_id
        )
        if self.current_player_id != mover_id:
            return []

        actions: List["Action"] = []
        for tile_id in self.board.tiles.keys():
            if tile_id == self.robber_tile_id:
                continue
            valid_targets = self._robber_steal_targets(tile_id, mover_id)
            if not valid_targets:
                candidate = MoveRobber(tile_id=tile_id, steal_from=None)
                if self.is_action_legal(candidate):
                    actions.append(candidate)
                continue
            for target in valid_targets:
                candidate = MoveRobber(tile_id=tile_id, steal_from=target)
                if self.is_action_legal(candidate):
                    actions.append(candidate)
        return actions

    def _legal_actions_trade_response_phase(self) -> List["Action"]:  # type: ignore[name-defined]
        from catan.engine.actions import AcceptPlayerTrade, DeclinePlayerTrade

        pending = self.pending_player_trade
        if pending is None:
            return []
        candidates = [DeclinePlayerTrade()]
        accept = AcceptPlayerTrade()
        if self.is_action_legal(accept):
            candidates.append(accept)
        return [action for action in candidates if self.is_action_legal(action)]

    def _legal_actions_main_phase(self) -> List["Action"]:  # type: ignore[name-defined]
        from itertools import combinations

        from catan.engine.actions import (
            BuyDevelopment,
            BuildCity,
            EndTurn,
            OfferPlayerTrade,
            PlaceRoad,
            PlaceSettlement,
            PlayKnight,
            PlayProgress,
            RollDice,
            TradeBank,
        )

        actions: List["Action"] = []

        def append_if_legal(candidate: "Action") -> None:  # type: ignore[name-defined]
            if self.is_action_legal(candidate):
                # Éviter les doublons en comparant avec les actions déjà ajoutées
                if not any(existing == candidate for existing in actions):
                    actions.append(candidate)

        # Roll dice (début de tour)
        append_if_legal(RollDice())

        current_player = self.players[self.current_player_id]

        # Constructions
        for edge_id in self.board.edges.keys():
            append_if_legal(PlaceRoad(edge_id=edge_id))
        for vertex_id in self.board.vertices.keys():
            append_if_legal(PlaceSettlement(vertex_id=vertex_id))
        for vertex_id in current_player.settlements:
            append_if_legal(BuildCity(vertex_id=vertex_id))

        # Commerce banque/ports
        for give_resource in RESOURCE_TYPES:
            player_amount = current_player.resources.get(give_resource, 0)
            if player_amount <= 0:
                continue
            rate = self._trade_rate_for_resource(current_player, give_resource)
            if rate <= 0:
                continue
            for give_total in range(rate, player_amount + 1, rate):
                receive_amount = give_total // rate
                for receive_resource in RESOURCE_TYPES:
                    trade = TradeBank(
                        give={give_resource: give_total},
                        receive={receive_resource: receive_amount},
                    )
                    append_if_legal(trade)

        # Achat carte développement
        append_if_legal(BuyDevelopment())

        # Cartes chevalier + progrès
        append_if_legal(PlayKnight())

        if current_player.dev_cards.get("ROAD_BUILDING", 0) > 0:
            free_edges = [
                edge_id
                for edge_id in self.board.edges.keys()
                if edge_id not in self._occupied_edges()
            ]
            for edge_a, edge_b in combinations(free_edges, 2):
                action = PlayProgress(card="ROAD_BUILDING", edges=[edge_a, edge_b])
                append_if_legal(action)

        if current_player.dev_cards.get("YEAR_OF_PLENTY", 0) > 0:
            for res_a in RESOURCE_TYPES:
                for res_b in RESOURCE_TYPES:
                    resources: Dict[str, int] = {}
                    resources[res_a] = resources.get(res_a, 0) + 1
                    resources[res_b] = resources.get(res_b, 0) + 1
                    action = PlayProgress(card="YEAR_OF_PLENTY", resources=resources)
                    append_if_legal(action)

        if current_player.dev_cards.get("MONOPOLY", 0) > 0:
            for resource in RESOURCE_TYPES:
                action = PlayProgress(card="MONOPOLY", resource=resource)
                append_if_legal(action)

        # Offres joueur↔joueur (limitées aux échanges unitaires pour éviter explosion combinatoire)
        opponent_id = self._opponent_id(self.current_player_id)
        if opponent_id is not None and self.pending_player_trade is None:
            for give_resource in RESOURCE_TYPES:
                if current_player.resources.get(give_resource, 0) <= 0:
                    continue
                for receive_resource in RESOURCE_TYPES:
                    if receive_resource == give_resource:
                        continue
                    offer = OfferPlayerTrade(
                        give={give_resource: 1},
                        receive={receive_resource: 1},
                    )
                    append_if_legal(offer)

        # Fin de tour (si déjà implémentée)
        append_if_legal(EndTurn())

        return actions

    @staticmethod
    def _generate_discard_splits(
        resource_counts: Dict[str, int],
        total: int,
    ) -> List[Dict[str, int]]:
        """Génère toutes les combinaisons de défausse possibles."""

        results: List[Dict[str, int]] = []

        def backtrack(index: int, remaining: int, current: Dict[str, int]) -> None:
            if remaining == 0:
                results.append(dict(current))
                return
            if index >= len(RESOURCE_TYPES):
                return

            resource = RESOURCE_TYPES[index]
            max_use = min(resource_counts.get(resource, 0), remaining)
            for amount in range(max_use + 1):
                if amount > 0:
                    current[resource] = amount
                elif resource in current:
                    current.pop(resource, None)
                backtrack(index + 1, remaining - amount, current)
            if resource in current:
                current.pop(resource, None)

        backtrack(0, total, {})
        return results

    def is_action_legal(self, action: "Action") -> bool:  # type: ignore
        """Vérifie si une action est légale dans l'état actuel.

        Args:
            action: Action à vérifier

        Returns:
            True si l'action est légale
        """
        from catan.engine.actions import (
            AcceptPlayerTrade,
            BuyDevelopment,
            BuildCity,
            DeclinePlayerTrade,
            DiscardResources,
            MoveRobber,
            OfferPlayerTrade,
            PlaceRoad,
            PlaceSettlement,
            PlayKnight,
            PlayProgress,
            RollDice,
            TradeBank,
        )

        if self.is_game_over:
            return False

        # Pendant setup, les règles sont spécifiques
        if self.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2):
            if isinstance(action, PlaceSettlement):
                # Vérifier que le sommet est libre
                vertex_id = action.vertex_id
                if vertex_id not in self.board.vertices:
                    return False
                # Vérifier qu'aucun joueur n'a déjà construit ici
                for player in self.players:
                    if vertex_id in player.settlements or vertex_id in player.cities:
                        return False
                # Pendant setup, on attend une colonie seulement si pas en attente de route
                return not self._waiting_for_road

            elif isinstance(action, PlaceRoad):
                # Doit être en attente de route après placement de colonie
                if not self._waiting_for_road:
                    return False
                # Vérifier que l'arête est libre
                edge_id = action.edge_id
                if edge_id not in self.board.edges:
                    return False
                for player in self.players:
                    if edge_id in player.roads:
                        return False
                # Vérifier que l'arête est adjacente à la dernière colonie placée
                current_player = self.players[self.current_player_id]
                if not current_player.settlements:
                    return False
                last_settlement = current_player.settlements[-1]
                edge = self.board.edges[edge_id]
                return last_settlement in edge.vertices

            # Pas de lancer de dés pendant setup
            return False

        # Phase PLAY
        if self.phase != SetupPhase.PLAY:
            return False

        if self.turn_subphase == TurnSubPhase.ROBBER_DISCARD:
            if not isinstance(action, DiscardResources):
                return False
            required = self.pending_discards.get(self.current_player_id)
            if required is None:
                return False
            total = sum(action.resources.values())
            if total != required:
                return False
            player = self.players[self.current_player_id]
            for resource, amount in action.resources.items():
                if amount < 0:
                    return False
                if player.resources.get(resource, 0) < amount:
                    return False
            return True

        if self.turn_subphase == TurnSubPhase.ROBBER_MOVE:
            if not isinstance(action, MoveRobber):
                return False
            if action.tile_id not in self.board.tiles:
                return False
            if action.tile_id == self.robber_tile_id:
                return False
            roller_id = (
                self.robber_roller_id
                if self.robber_roller_id is not None
                else self.current_player_id
            )
            if self.current_player_id != roller_id:
                return False
            valid_targets = self._robber_steal_targets(action.tile_id, roller_id)
            if not valid_targets:
                return action.steal_from is None
            if action.steal_from not in valid_targets:
                return False
            return self._player_has_resources(action.steal_from)

        if self.turn_subphase == TurnSubPhase.TRADE_RESPONSE:
            pending = self.pending_player_trade
            if pending is None:
                return False
            if self.current_player_id != pending.responder_id:
                return False
            if isinstance(action, AcceptPlayerTrade):
                proposer = self.players[pending.proposer_id]
                responder = self.players[pending.responder_id]
                if not self._player_can_afford(proposer, pending.give):
                    return False
                if not self._player_can_afford(responder, pending.receive):
                    return False
                return True
            if isinstance(action, DeclinePlayerTrade):
                return True
            return False

        # Sous-phase principale: gérer les actions de construction
        if isinstance(action, RollDice):
            return not self.dice_rolled_this_turn

        current_player = self.players[self.current_player_id]

        if isinstance(action, OfferPlayerTrade):
            if self.turn_subphase != TurnSubPhase.MAIN:
                return False
            if not self.dice_rolled_this_turn:
                return False
            if self.pending_player_trade is not None:
                return False
            if not action.give or not action.receive:
                return False
            if any(amount <= 0 for amount in action.give.values()):
                return False
            if any(amount <= 0 for amount in action.receive.values()):
                return False
            if any(resource not in RESOURCE_TYPES for resource in action.give):
                return False
            if any(resource not in RESOURCE_TYPES for resource in action.receive):
                return False
            if not self._player_can_afford(current_player, action.give):
                return False
            opponent_id = self._opponent_id(self.current_player_id)
            if opponent_id is None:
                return False
            return True

        if isinstance(action, BuyDevelopment):
            if self.turn_subphase != TurnSubPhase.MAIN:
                return False
            if not self.dice_rolled_this_turn:
                return False
            if not self.dev_deck:
                return False
            if not self._player_can_afford(current_player, COSTS["development"]):
                return False
            return True

        if isinstance(action, PlayKnight):
            if self.turn_subphase != TurnSubPhase.MAIN:
                return False
            if current_player.new_dev_cards.get("KNIGHT", 0) > 0:
                return False
            return current_player.dev_cards.get("KNIGHT", 0) > 0

        if isinstance(action, PlayProgress):
            if self.turn_subphase != TurnSubPhase.MAIN:
                return False
            card_type = action.card
            if card_type not in PROGRESS_CARD_TYPES:
                return False
            if current_player.new_dev_cards.get(card_type, 0) > 0:
                return False
            if current_player.dev_cards.get(card_type, 0) <= 0:
                return False

            if card_type == "ROAD_BUILDING":
                if action.edges is None or len(action.edges) != 2:
                    return False
                if len(set(action.edges)) != len(action.edges):
                    return False
                occupied = self._occupied_edges()
                staged: Set[int] = set()
                for edge_id in action.edges:
                    if edge_id not in self.board.edges:
                        return False
                    if edge_id in occupied or edge_id in staged:
                        return False
                    if not self._edge_connected_to_player(
                        current_player, edge_id, staged
                    ):
                        return False
                    staged.add(edge_id)
                return True

            if card_type == "YEAR_OF_PLENTY":
                if not action.resources:
                    return False
                if any(resource not in RESOURCE_TYPES for resource in action.resources):
                    return False
                total = sum(action.resources.values())
                if total != 2:
                    return False
                return self._bank_has_resources(action.resources)

            if card_type == "MONOPOLY":
                return action.resource in RESOURCE_TYPES

            return False

        if isinstance(action, PlaceRoad):
            if action.edge_id not in self.board.edges:
                return False
            if self._edge_is_occupied(action.edge_id):
                return False
            if not self._edge_connected_to_player(current_player, action.edge_id):
                return False
            if not action.free and not self.dice_rolled_this_turn:
                return False
            if not action.free and not self._player_can_afford(current_player, COSTS["road"]):
                return False
            return True

        if isinstance(action, PlaceSettlement):
            if action.vertex_id not in self.board.vertices:
                return False
            if self._vertex_is_occupied(action.vertex_id):
                return False
            if not self._vertex_respects_distance_rule(action.vertex_id):
                return False
            if not action.free:
                if not self.dice_rolled_this_turn:
                    return False
                if not self._player_can_afford(current_player, COSTS["settlement"]):
                    return False
            if not self._vertex_adjacent_to_player_road(current_player, action.vertex_id):
                return False
            return True

        if isinstance(action, BuildCity):
            if action.vertex_id not in self.board.vertices:
                return False
            if not self.dice_rolled_this_turn:
                return False
            if action.vertex_id not in current_player.settlements:
                return False
            if not self._player_can_afford(current_player, COSTS["city"]):
                return False
            return True

        if isinstance(action, TradeBank):
            if self.turn_subphase != TurnSubPhase.MAIN:
                return False
            if not self.dice_rolled_this_turn:
                return False
            if not action.give or not action.receive:
                return False
            if len(action.give) != 1 or len(action.receive) != 1:
                return False

            give_resource, give_amount = next(iter(action.give.items()))
            receive_resource, receive_amount = next(iter(action.receive.items()))

            if (
                give_resource not in RESOURCE_TYPES
                or receive_resource not in RESOURCE_TYPES
            ):
                return False
            if give_amount <= 0 or receive_amount <= 0:
                return False
            if not self._player_can_afford(current_player, action.give):
                return False
            if not self._bank_has_resources(action.receive):
                return False

            rate = self._trade_rate_for_resource(current_player, give_resource)
            if give_amount % rate != 0:
                return False
            if give_amount // rate != receive_amount:
                return False
            return True

        return False

    def apply_action(self, action: "Action") -> "GameState":  # type: ignore
        """Applique une action et retourne le nouvel état.

        Args:
            action: Action à appliquer

        Returns:
            Nouvel état après application de l'action

        Raises:
            ValueError: Si l'action n'est pas légale
        """
        from catan.engine.actions import (
            AcceptPlayerTrade,
            BuyDevelopment,
            BuildCity,
            DeclinePlayerTrade,
            DiscardResources,
            MoveRobber,
            OfferPlayerTrade,
            PlaceRoad,
            PlaceSettlement,
            PlayKnight,
            PlayProgress,
            RollDice,
            TradeBank,
        )

        if not self.is_action_legal(action):
            raise ValueError(f"Action illégale: {action}")

        # Copier les joueurs pour modification immuable
        new_players = [copy.deepcopy(p) for p in self.players]
        current_player = new_players[self.current_player_id]

        recompute_longest_road = False
        recompute_largest_army = False

        new_state_fields = {
            "board": self.board,
            "players": new_players,
            "phase": self.phase,
            "current_player_id": self.current_player_id,
            "turn_number": self.turn_number,
            "_setup_settlements_placed": self._setup_settlements_placed,
            "_setup_roads_placed": self._setup_roads_placed,
            "_waiting_for_road": self._waiting_for_road,
            "last_dice_roll": self.last_dice_roll,
            "dice_rolled_this_turn": self.dice_rolled_this_turn,
            "turn_subphase": self.turn_subphase,
            "pending_discards": copy.deepcopy(self.pending_discards),
            "pending_discard_queue": list(self.pending_discard_queue),
            "pending_player_trade": self.pending_player_trade,
            "robber_tile_id": self.robber_tile_id,
            "robber_roller_id": self.robber_roller_id,
            "dev_deck": list(self.dev_deck),
            "bank_resources": copy.deepcopy(self.bank_resources),
            "rng_state": self.rng_state,
            "longest_road_owner": self.longest_road_owner,
            "longest_road_length": self.longest_road_length,
            "largest_army_owner": self.largest_army_owner,
            "largest_army_size": self.largest_army_size,
            "is_game_over": self.is_game_over,
            "winner_id": self.winner_id,
        }

        if isinstance(action, PlaceSettlement):
            # Placer la colonie
            current_player.settlements.append(action.vertex_id)
            current_player.victory_points += 1
            if not action.free:
                self._deduct_resources(current_player, COSTS["settlement"])
                self._add_resources_to_bank(
                    new_state_fields["bank_resources"], COSTS["settlement"]
                )

            if (
                self.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2)
                and action.free
            ):
                new_state_fields["_setup_settlements_placed"] = (
                    self._setup_settlements_placed + 1
                )
                new_state_fields["_waiting_for_road"] = True
            else:
                new_state_fields["_waiting_for_road"] = False
            recompute_longest_road = True

        elif isinstance(action, PlaceRoad):
            # Placer la route
            current_player.roads.append(action.edge_id)
            if not action.free:
                self._deduct_resources(current_player, COSTS["road"])
                self._add_resources_to_bank(
                    new_state_fields["bank_resources"], COSTS["road"]
                )

            if (
                self.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2)
                and action.free
            ):
                new_state_fields["_setup_roads_placed"] = self._setup_roads_placed + 1
                new_state_fields["_waiting_for_road"] = False

                # Distribution de ressources UNIQUEMENT après le 2e placement (SETUP_ROUND_2)
                if self.phase == SetupPhase.SETUP_ROUND_2:
                    # Récupérer la dernière colonie placée
                    last_settlement = current_player.settlements[-1]
                    vertex = self.board.vertices[last_settlement]
                    # Distribuer une ressource de chaque tuile adjacente (sauf désert)
                    for tile_id in vertex.adjacent_tiles:
                        tile = self.board.tiles[tile_id]
                        if tile.resource != "DESERT":
                            current_player.resources[tile.resource] += 1

                # Avancer le jeu après placement de la route (setup uniquement)
                new_state_fields.update(self._advance_setup_turn())
            else:
                new_state_fields["_waiting_for_road"] = False
            recompute_longest_road = True

        elif isinstance(action, BuildCity):
            # Améliorer une colonie en ville
            if action.vertex_id in current_player.settlements:
                current_player.settlements.remove(action.vertex_id)
            current_player.cities.append(action.vertex_id)
            current_player.victory_points += 1
            self._deduct_resources(current_player, COSTS["city"])
            self._add_resources_to_bank(
                new_state_fields["bank_resources"], COSTS["city"]
            )

        elif isinstance(action, TradeBank):
            self._deduct_resources(current_player, action.give)
            self._add_resources_to_bank(
                new_state_fields["bank_resources"], action.give
            )
            self._remove_resources_from_bank(
                new_state_fields["bank_resources"], action.receive
            )
            for resource, amount in action.receive.items():
                current_player.resources[resource] += amount

        elif isinstance(action, OfferPlayerTrade):
            opponent_id = self._opponent_id(self.current_player_id)
            if opponent_id is None:
                raise ValueError("No opponent available for player trade")
            new_state_fields["pending_player_trade"] = PendingPlayerTrade(
                proposer_id=self.current_player_id,
                responder_id=opponent_id,
                give=dict(action.give),
                receive=dict(action.receive),
            )
            new_state_fields["turn_subphase"] = TurnSubPhase.TRADE_RESPONSE
            new_state_fields["current_player_id"] = opponent_id

        elif isinstance(action, AcceptPlayerTrade):
            pending = self.pending_player_trade
            if pending is None:
                raise ValueError("No pending player trade to accept")
            proposer = new_players[pending.proposer_id]
            responder = new_players[pending.responder_id]

            self._deduct_resources(proposer, pending.give)
            self._deduct_resources(responder, pending.receive)
            self._add_resources_to_player(responder, pending.give)
            self._add_resources_to_player(proposer, pending.receive)

            new_state_fields["pending_player_trade"] = None
            new_state_fields["turn_subphase"] = TurnSubPhase.MAIN
            new_state_fields["current_player_id"] = pending.proposer_id

        elif isinstance(action, DeclinePlayerTrade):
            pending = self.pending_player_trade
            if pending is None:
                raise ValueError("No pending player trade to decline")
            new_state_fields["pending_player_trade"] = None
            new_state_fields["turn_subphase"] = TurnSubPhase.MAIN
            new_state_fields["current_player_id"] = pending.proposer_id

        elif isinstance(action, BuyDevelopment):
            if not new_state_fields["dev_deck"]:
                raise ValueError("Pioche de développement vide")
            card = new_state_fields["dev_deck"].pop(0)
            self._deduct_resources(current_player, COSTS["development"])
            self._add_resources_to_bank(
                new_state_fields["bank_resources"], COSTS["development"]
            )
            self._grant_new_dev_card(current_player, card)
            if card == "VICTORY_POINT":
                self._grant_hidden_victory_point(current_player)

        elif isinstance(action, PlayKnight):
            current_player.dev_cards["KNIGHT"] -= 1
            current_player.played_dev_cards["KNIGHT"] += 1
            new_state_fields["turn_subphase"] = TurnSubPhase.ROBBER_MOVE
            new_state_fields["pending_discards"] = {}
            new_state_fields["pending_discard_queue"] = []
            new_state_fields["robber_roller_id"] = self.current_player_id
            new_state_fields["current_player_id"] = self.current_player_id
            recompute_largest_army = True

        elif isinstance(action, PlayProgress):
            card_type = action.card
            current_player.dev_cards[card_type] -= 1
            if card_type == "ROAD_BUILDING":
                for edge_id in action.edges or []:
                    current_player.roads.append(edge_id)
                recompute_longest_road = True
            elif card_type == "YEAR_OF_PLENTY":
                resources = action.resources or {}
                self._remove_resources_from_bank(
                    new_state_fields["bank_resources"], resources
                )
                for resource, amount in resources.items():
                    current_player.resources[resource] += amount
            elif card_type == "MONOPOLY":
                resource = action.resource or ""
                total_collected = 0
                for player in new_players:
                    if player.player_id == self.current_player_id:
                        continue
                    amount = player.resources.get(resource, 0)
                    if amount > 0:
                        total_collected += amount
                        player.resources[resource] = 0
                current_player.resources[resource] += total_collected
            current_player.played_dev_cards[card_type] += 1

        elif isinstance(action, RollDice):
            # Lancer les dés
            if action.forced_value is not None:
                die1, die2 = action.forced_value
            else:
                rng = self._rng()
                die1 = rng.randint(1, 6)
                die2 = rng.randint(1, 6)
                new_state_fields["rng_state"] = rng.getstate()

            dice_total = die1 + die2
            new_state_fields["last_dice_roll"] = dice_total
            new_state_fields["dice_rolled_this_turn"] = True

            if dice_total == 7:
                requirements = self._compute_discard_requirements(new_players)
                ordered_players = list(requirements.keys())
                new_state_fields["pending_discards"] = requirements
                new_state_fields["pending_discard_queue"] = ordered_players
                new_state_fields["robber_roller_id"] = self.current_player_id

                if ordered_players:
                    new_state_fields["turn_subphase"] = TurnSubPhase.ROBBER_DISCARD
                    new_state_fields["current_player_id"] = ordered_players[0]
                else:
                    new_state_fields["turn_subphase"] = TurnSubPhase.ROBBER_MOVE
                    new_state_fields["current_player_id"] = self.current_player_id
            else:
                new_state_fields["pending_discards"] = {}
                new_state_fields["pending_discard_queue"] = []
                new_state_fields["turn_subphase"] = TurnSubPhase.MAIN
                new_state_fields["robber_roller_id"] = None
                self._distribute_resources(dice_total, new_players)

        elif isinstance(action, DiscardResources):
            pending_discards: Dict[int, int] = new_state_fields["pending_discards"]
            pending_queue: List[int] = new_state_fields["pending_discard_queue"]
            required = pending_discards.get(self.current_player_id, 0)

            discarded_total = sum(action.resources.values())
            if discarded_total != required:
                raise ValueError("Quantité de défausse incorrecte")

            for resource, amount in action.resources.items():
                if amount == 0:
                    continue
                current_player.resources[resource] -= amount
            self._add_resources_to_bank(
                new_state_fields["bank_resources"], action.resources
            )

            if self.current_player_id in pending_discards:
                del pending_discards[self.current_player_id]

            if pending_queue and pending_queue[0] == self.current_player_id:
                pending_queue.pop(0)

            if pending_queue:
                new_state_fields["current_player_id"] = pending_queue[0]
            else:
                new_state_fields["turn_subphase"] = TurnSubPhase.ROBBER_MOVE
                roller_id = (
                    self.robber_roller_id
                    if self.robber_roller_id is not None
                    else self.current_player_id
                )
                new_state_fields["current_player_id"] = roller_id

        elif isinstance(action, MoveRobber):
            roller_id = (
                self.robber_roller_id
                if self.robber_roller_id is not None
                else self.current_player_id
            )
            mover = new_players[roller_id]

            new_state_fields["board"] = self._board_with_robber(action.tile_id)
            new_state_fields["robber_tile_id"] = action.tile_id
            new_state_fields["turn_subphase"] = TurnSubPhase.MAIN
            new_state_fields["pending_discards"] = {}
            new_state_fields["pending_discard_queue"] = []
            new_state_fields["current_player_id"] = roller_id
            new_state_fields["robber_roller_id"] = None

            if action.steal_from is not None:
                stolen = self._steal_resource(new_players[action.steal_from])
                if stolen is not None:
                    mover.resources[stolen] += 1

        if recompute_longest_road:
            self._apply_longest_road_update(new_state_fields, new_players)
        if recompute_largest_army:
            self._apply_largest_army_update(new_state_fields, new_players)

        self._check_victory(new_state_fields, new_players)

        return GameState(**new_state_fields)

    def _player_can_afford(self, player: Player, cost: Dict[str, int]) -> bool:
        """Vérifie que le joueur possède les ressources nécessaires."""
        return all(player.resources.get(resource, 0) >= amount for resource, amount in cost.items())

    def _deduct_resources(self, player: Player, cost: Dict[str, int]) -> None:
        """Soustrait les ressources correspondant au coût fourni."""
        for resource, amount in cost.items():
            if amount == 0:
                continue
            player.resources[resource] -= amount

    @staticmethod
    def _add_resources_to_player(player: Player, resources: Dict[str, int]) -> None:
        """Ajoute des ressources à un joueur."""
        for resource, amount in resources.items():
            if amount == 0:
                continue
            player.resources[resource] += amount

    @staticmethod
    def _add_resources_to_bank(bank: Dict[str, int], resources: Dict[str, int]) -> None:
        """Ajoute des ressources à la banque (ex: achat de carte)."""
        for resource, amount in resources.items():
            if amount == 0:
                continue
            bank[resource] += amount

    @staticmethod
    def _remove_resources_from_bank(
        bank: Dict[str, int], resources: Dict[str, int]
    ) -> None:
        """Retire des ressources à la banque (ex: Year of Plenty)."""
        for resource, amount in resources.items():
            if amount == 0:
                continue
            available = bank.get(resource, 0)
            if available < amount:
                raise ValueError("Bank cannot provide requested resources")
            bank[resource] = available - amount

    def _bank_has_resources(self, resources: Dict[str, int]) -> bool:
        """Vérifie que la banque possède les ressources demandées."""
        for resource, amount in resources.items():
            if self.bank_resources.get(resource, 0) < amount:
                return False
        return True

    def _player_port_kinds(self, player: Player) -> Set[str]:
        """Retourne les types de ports accessibles par le joueur."""
        owned_vertices = set(player.settlements) | set(player.cities)
        if not owned_vertices:
            return set()

        kinds: Set[str] = set()
        for port in self.board.ports:
            if any(vertex in owned_vertices for vertex in port.vertices):
                kinds.add(port.kind)
        return kinds

    def _trade_rate_for_resource(self, player: Player, resource: str) -> int:
        """Calcule le taux de commerce applicable pour une ressource donnée."""
        rate = 4
        port_kinds = self._player_port_kinds(player)
        if "ANY" in port_kinds:
            rate = min(rate, 3)
        if resource in port_kinds:
            rate = min(rate, 2)
        return rate

    def _grant_new_dev_card(self, player: Player, card: str) -> None:
        """Ajoute une carte de développement fraîchement achetée."""
        if card not in player.new_dev_cards:
            player.new_dev_cards[card] = 0
        player.new_dev_cards[card] += 1

    @staticmethod
    def _grant_hidden_victory_point(player: Player) -> None:
        """Ajoute un point de victoire caché à un joueur."""
        player.hidden_victory_points += 1

    def _check_victory(
        self,
        new_state_fields: Dict[str, object],
        players: List[Player],
    ) -> None:
        """Détermine si un joueur atteint le seuil de victoire."""
        if new_state_fields.get("is_game_over", False):
            return

        totals = {
            player.player_id: player.victory_points + player.hidden_victory_points
            for player in players
        }
        eligible = {
            player_id: total for player_id, total in totals.items() if total >= VP_TO_WIN
        }
        if not eligible:
            return

        winner_id = max(eligible.items(), key=lambda item: (item[1], -item[0]))[0]
        new_state_fields["is_game_over"] = True
        new_state_fields["winner_id"] = winner_id
        new_state_fields["pending_player_trade"] = None
        new_state_fields["pending_discards"] = {}
        new_state_fields["pending_discard_queue"] = []
        new_state_fields["robber_roller_id"] = None
        new_state_fields["turn_subphase"] = TurnSubPhase.MAIN

    def _apply_longest_road_update(
        self,
        new_state_fields: Dict[str, object],
        players: List[Player],
    ) -> None:
        """Recalcule la plus longue route et met à jour les points."""

        board = cast(Board, new_state_fields.get("board", self.board))
        vertex_owner = self._vertex_owner_map(players)
        lengths = {
            player.player_id: self._longest_road_length_for_player(
                board, player, vertex_owner
            )
            for player in players
        }
        best_length = max(lengths.values(), default=0)
        best_players = [
            player_id for player_id, length in lengths.items() if length == best_length
        ]

        current_owner = self.longest_road_owner
        current_length = (
            lengths.get(current_owner, 0) if current_owner is not None else 0
        )
        new_owner = current_owner
        new_length = current_length

        if best_length < 5:
            new_owner = None
            new_length = 0
        else:
            if len(best_players) == 1:
                candidate = best_players[0]
                if current_owner is None or candidate == current_owner:
                    new_owner = candidate
                    new_length = best_length
                else:
                    if best_length > current_length:
                        new_owner = candidate
                        new_length = best_length
            else:
                if (
                    current_owner is not None
                    and current_owner in best_players
                    and current_length >= 5
                ):
                    new_owner = current_owner
                    new_length = current_length
                else:
                    new_owner = None
                    new_length = 0

        previous_owner = self.longest_road_owner
        if previous_owner != new_owner:
            if previous_owner is not None:
                players[previous_owner].victory_points -= 2
            if new_owner is not None:
                players[new_owner].victory_points += 2

        new_state_fields["longest_road_owner"] = new_owner
        new_state_fields["longest_road_length"] = new_length if new_owner is not None else 0

    def _apply_largest_army_update(
        self,
        new_state_fields: Dict[str, object],
        players: List[Player],
    ) -> None:
        """Recalcule la plus grande armée et met à jour les points."""

        counts = {
            player.player_id: player.played_dev_cards.get("KNIGHT", 0)
            for player in players
        }
        best_count = max(counts.values(), default=0)
        best_players = [
            player_id for player_id, count in counts.items() if count == best_count
        ]

        current_owner = self.largest_army_owner
        current_size = counts.get(current_owner, 0) if current_owner is not None else 0
        new_owner = current_owner
        new_size = current_size

        if best_count < 3:
            new_owner = None
            new_size = 0
        else:
            if len(best_players) == 1:
                candidate = best_players[0]
                if current_owner is None or candidate == current_owner:
                    new_owner = candidate
                    new_size = best_count
                else:
                    if best_count > current_size:
                        new_owner = candidate
                        new_size = best_count
            else:
                if (
                    current_owner is not None
                    and current_owner in best_players
                    and current_size >= 3
                ):
                    new_owner = current_owner
                    new_size = current_size
                else:
                    new_owner = None
                    new_size = 0

        previous_owner = self.largest_army_owner
        if previous_owner != new_owner:
            if previous_owner is not None:
                players[previous_owner].victory_points -= 2
            if new_owner is not None:
                players[new_owner].victory_points += 2

        new_state_fields["largest_army_owner"] = new_owner
        new_state_fields["largest_army_size"] = new_size if new_owner is not None else 0

    @staticmethod
    def _vertex_owner_map(players: List[Player]) -> Dict[int, int]:
        """Associe chaque sommet occupé à son propriétaire."""

        owner_map: Dict[int, int] = {}
        for player in players:
            for vertex_id in player.settlements:
                owner_map[vertex_id] = player.player_id
            for vertex_id in player.cities:
                owner_map[vertex_id] = player.player_id
        return owner_map

    def _longest_road_length_for_player(
        self,
        board: Board,
        player: Player,
        vertex_owner: Dict[int, int],
    ) -> int:
        """Calcule la longueur maximale de route pour un joueur."""

        roads = set(player.roads)
        if not roads:
            return 0

        adjacency_by_vertex: Dict[int, List[int]] = defaultdict(list)
        for edge_id in roads:
            edge = board.edges.get(edge_id)
            if edge is None:
                continue
            for vertex_id in edge.vertices:
                adjacency_by_vertex[vertex_id].append(edge_id)

        neighbors: Dict[int, Set[int]] = {edge_id: set() for edge_id in roads}
        for vertex_id, edges_at_vertex in adjacency_by_vertex.items():
            owner = vertex_owner.get(vertex_id)
            if owner is not None and owner != player.player_id:
                continue
            if len(edges_at_vertex) < 2:
                continue
            for edge_a, edge_b in combinations(edges_at_vertex, 2):
                neighbors[edge_a].add(edge_b)
                neighbors[edge_b].add(edge_a)

        best = 0
        visited: Set[int] = set()

        def dfs(edge_id: int) -> None:
            nonlocal best
            visited.add(edge_id)
            best = max(best, len(visited))
            for neighbor in neighbors[edge_id]:
                if neighbor in visited:
                    continue
                dfs(neighbor)
            visited.remove(edge_id)

        for edge_id in roads:
            dfs(edge_id)

        return best

    def _edge_is_occupied(self, edge_id: int) -> bool:
        """Indique si une arête est déjà occupée par une route."""
        return any(edge_id in player.roads for player in self.players)

    def _occupied_edges(self) -> Set[int]:
        """Retourne l'ensemble des arêtes occupées par au moins une route."""
        occupied: Set[int] = set()
        for player in self.players:
            occupied.update(player.roads)
        return occupied

    def _edge_connected_to_player(
        self,
        player: Player,
        edge_id: int,
        additional_edges: Optional[Iterable[int]] = None,
    ) -> bool:
        """Vérifie qu'une arête est connectée au réseau du joueur."""
        edge = self.board.edges[edge_id]
        player_vertices = set(player.settlements + player.cities)
        if player_vertices.intersection(edge.vertices):
            return True

        player_edges = set(player.roads)
        if additional_edges:
            player_edges.update(additional_edges)

        for owned_edge_id in player_edges:
            owned_edge = self.board.edges[owned_edge_id]
            if set(owned_edge.vertices).intersection(edge.vertices):
                return True
        return False

    def _vertex_is_occupied(self, vertex_id: int) -> bool:
        """True si le sommet est occupé par une colonie ou une ville."""
        for player in self.players:
            if vertex_id in player.settlements or vertex_id in player.cities:
                return True
        return False

    def _vertex_adjacent_vertices(self, vertex_id: int) -> List[int]:
        """Retourne les sommets adjacents (distance 1) à un sommet donné."""
        vertex = self.board.vertices[vertex_id]
        neighbors: List[int] = []
        for edge_id in vertex.edges:
            edge = self.board.edges[edge_id]
            a, b = edge.vertices
            neighbor = b if a == vertex_id else a
            neighbors.append(neighbor)
        return neighbors

    def _opponent_id(self, player_id: int) -> int | None:
        """Retourne l'identifiant de l'adversaire (1v1)."""

        player_count = len(self.players)
        if player_count <= 1:
            return None
        for candidate in range(player_count):
            if candidate != player_id:
                return candidate
        return None

    def _vertex_respects_distance_rule(self, vertex_id: int) -> bool:
        """Applique la règle de distance: aucun voisin ne doit être occupé."""
        for neighbor in self._vertex_adjacent_vertices(vertex_id):
            if self._vertex_is_occupied(neighbor):
                return False
        return True

    def _vertex_adjacent_to_player_road(self, player: Player, vertex_id: int) -> bool:
        """Vérifie qu'au moins une route du joueur aboutit sur le sommet."""
        vertex = self.board.vertices[vertex_id]
        player_edges = set(player.roads)
        return any(edge_id in player_edges for edge_id in vertex.edges)

    def _distribute_resources(self, dice_value: int, players: List[Player]) -> None:
        """Distribue les ressources selon le lancer de dés.

        Args:
            dice_value: Valeur du lancer de dés
            players: Liste modifiable des joueurs (pour mutation)
        """
        # Parcourir toutes les tuiles du plateau
        for tile_id, tile in self.board.tiles.items():
            # Ignorer si pas de numéro (pip) ou désert
            if tile.pip is None or tile.resource == "DESERT":
                continue

            # Ignorer si le numéro ne correspond pas
            if tile.pip != dice_value:
                continue

            # Ignorer si le voleur bloque cette tuile
            if tile_id == self.robber_tile_id:
                continue

            # Distribuer aux colonies/villes sur les sommets adjacents
            for vertex_id in tile.vertices:
                for player in players:
                    # Colonie = 1 ressource
                    if vertex_id in player.settlements:
                        player.resources[tile.resource] += 1
                    # Ville = 2 ressources
                    elif vertex_id in player.cities:
                        player.resources[tile.resource] += 2

    def _compute_discard_requirements(self, players: List[Player]) -> Dict[int, int]:
        """Calcule les quantités à défausser pour chaque joueur après un 7."""
        requirements: Dict[int, int] = {}
        for player in players:
            total_cards = sum(player.resources.values())
            if total_cards > DISCARD_THRESHOLD:
                requirements[player.player_id] = total_cards - DISCARD_THRESHOLD
        # Garantir un ordre déterministe (ID croissant)
        return dict(sorted(requirements.items()))

    def _player_has_resources(self, player_id: int) -> bool:
        """Indique si un joueur possède au moins une carte ressource."""
        player = self.players[player_id]
        return any(amount > 0 for amount in player.resources.values())

    def _robber_steal_targets(self, tile_id: int, roller_id: int) -> List[int]:
        """Retourne les joueurs adverses volables sur une tuile."""
        tile = self.board.tiles[tile_id]
        targets: List[int] = []
        for player in self.players:
            if player.player_id == roller_id:
                continue
            if any(
                vertex in player.settlements or vertex in player.cities
                for vertex in tile.vertices
            ):
                if self._player_has_resources(player.player_id):
                    targets.append(player.player_id)
        return targets

    def _steal_resource(self, victim: Player) -> str | None:
        """Retire une ressource au hasard déterministe (ordre alphabétique)."""
        for resource in sorted(victim.resources.keys()):
            if victim.resources[resource] > 0:
                victim.resources[resource] -= 1
                return resource
        return None

    def _board_with_robber(self, target_tile_id: int) -> "Board":
        """Retourne un plateau avec le voleur repositionné sur la tuile cible."""
        tiles = dict(self.board.tiles)
        if self.robber_tile_id in tiles:
            tiles[self.robber_tile_id] = replace(
                tiles[self.robber_tile_id], has_robber=False
            )
        tiles[target_tile_id] = replace(tiles[target_tile_id], has_robber=True)
        board_cls = self.board.__class__
        return board_cls(
            tiles=tiles,
            vertices=self.board.vertices,
            edges=self.board.edges,
            ports=self.board.ports,
        )

    def _advance_setup_turn(self) -> dict:
        """Calcule le prochain état après un placement complet (colonie + route).

        Returns:
            Dictionnaire avec les champs à mettre à jour
        """
        updates = {}

        # Compter les placements complets (1 colonie + 1 route = 1 placement)
        total_placements = self._setup_roads_placed + 1  # +1 car on vient de placer

        if self.phase == SetupPhase.SETUP_ROUND_1:
            # Round 1: ordre normal (0, 1)
            if total_placements < 2:
                # Passer au joueur suivant
                updates["current_player_id"] = (self.current_player_id + 1) % 2
            else:
                # Passer au round 2, ordre inverse (commence par joueur 1)
                updates["phase"] = SetupPhase.SETUP_ROUND_2
                updates["current_player_id"] = 1

        elif self.phase == SetupPhase.SETUP_ROUND_2:
            # Round 2: ordre inverse (1, 0)
            if total_placements < 4:
                # Passer au joueur précédent (ordre inverse)
                player_count = len(self.players)
                previous_player = (self.current_player_id - 1) % player_count
                updates["current_player_id"] = previous_player
            else:
                # Setup terminé, passer en phase PLAY
                updates["phase"] = SetupPhase.PLAY
                updates["current_player_id"] = 0  # Le premier joueur commence
                updates["turn_number"] = 1

        return updates


__all__ = [
    "GameState",
    "Player",
    "PendingPlayerTrade",
    "SetupPhase",
    "TurnSubPhase",
]
