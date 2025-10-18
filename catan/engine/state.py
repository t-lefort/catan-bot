"""État du jeu et logique de transition (ENG-002+).

Ce module définit l'état immuable d'une partie et les transitions d'état.
Conforme aux schémas (docs/schemas.md) et specs (docs/specs.md).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, Iterable, List, Optional, Set

from catan.engine.rules import COSTS, DISCARD_THRESHOLD

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

    @classmethod
    def new_1v1_game(
        cls,
        player_names: List[str] | None = None,
        *,
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
        import random

        from catan.engine.board import Board

        if player_names is None:
            player_names = ["Player 0", "Player 1"]

        board = Board.standard()
        players = [
            Player(player_id=i, name=name) for i, name in enumerate(player_names)
        ]

        if dev_deck is None:
            shuffled_deck = list(DEFAULT_DEV_DECK)
            random.Random().shuffle(shuffled_deck)
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
        )

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
        import random

        if not self.is_action_legal(action):
            raise ValueError(f"Action illégale: {action}")

        # Copier les joueurs pour modification immuable
        new_players = [copy.deepcopy(p) for p in self.players]
        current_player = new_players[self.current_player_id]

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

        elif isinstance(action, PlayProgress):
            card_type = action.card
            current_player.dev_cards[card_type] -= 1
            if card_type == "ROAD_BUILDING":
                for edge_id in action.edges or []:
                    current_player.roads.append(edge_id)
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
                die1 = random.randint(1, 6)
                die2 = random.randint(1, 6)

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
