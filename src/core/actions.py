"""Action representation for the game.

Toutes les actions possibles dans Catan sont représentées ici.
Conçu pour être:
- Type-safe avec des classes distinctes par action
- Sérialisable pour l'entraînement RL
- Efficace pour le masking des actions invalides
"""

from dataclasses import dataclass
from typing import Union
from enum import IntEnum

from .board import VertexCoord, EdgeCoord, HexCoord
from .constants import ResourceType, DevelopmentCardType


class ActionType(IntEnum):
    """Types d'actions possibles."""
    # Phase de lancer de dés
    ROLL_DICE = 0

    # Constructions
    BUILD_SETTLEMENT = 1
    BUILD_CITY = 2
    BUILD_ROAD = 3
    BUY_DEV_CARD = 4

    # Commerce
    TRADE_WITH_BANK = 5
    TRADE_WITH_PORT = 6
    # TRADE_WITH_PLAYER = 7  # Pour plus tard

    # Cartes développement
    PLAY_KNIGHT = 8
    PLAY_ROAD_BUILDING = 9
    PLAY_YEAR_OF_PLENTY = 10
    PLAY_MONOPOLY = 11

    # Voleur (robber)
    MOVE_ROBBER = 12
    STEAL_FROM_PLAYER = 13

    # Défausse (quand dé = 7 et trop de cartes)
    DISCARD_RESOURCES = 14

    # Fin de tour
    END_TURN = 15


@dataclass(frozen=True)
class RollDiceAction:
    """Lance les dés."""
    pass


@dataclass(frozen=True)
class BuildSettlementAction:
    """Construire une colonie."""
    vertex: VertexCoord


@dataclass(frozen=True)
class BuildCityAction:
    """Améliorer une colonie en ville."""
    vertex: VertexCoord


@dataclass(frozen=True)
class BuildRoadAction:
    """Construire une route."""
    edge: EdgeCoord


@dataclass(frozen=True)
class BuyDevCardAction:
    """Acheter une carte développement."""
    pass


@dataclass(frozen=True)
class TradeWithBankAction:
    """
    Échanger avec la banque (ratio 4:1 par défaut).

    give: ressource à donner
    receive: ressource à recevoir
    amount: nombre de ressources données (4 par défaut)
    """
    give: ResourceType
    receive: ResourceType
    amount: int = 4


@dataclass(frozen=True)
class TradeWithPortAction:
    """
    Échanger avec un port (ratio 3:1 ou 2:1).

    give: ressource à donner
    receive: ressource à recevoir
    amount: nombre de ressources données (2 ou 3)
    """
    give: ResourceType
    receive: ResourceType
    amount: int  # 2 ou 3


@dataclass(frozen=True)
class PlayKnightAction:
    """
    Jouer une carte Chevalier.

    new_robber_hex: hexagone où placer le voleur
    steal_from_player: joueur à voler (None si pas de joueur adjacent)
    """
    new_robber_hex: HexCoord
    steal_from_player: int | None


@dataclass(frozen=True)
class PlayRoadBuildingAction:
    """
    Jouer une carte Construction de routes.

    edge1, edge2: les 2 routes à construire
    """
    edge1: EdgeCoord
    edge2: EdgeCoord | None  # None si une seule route possible


@dataclass(frozen=True)
class PlayYearOfPlentyAction:
    """
    Jouer une carte Invention (Year of Plenty).

    resource1, resource2: les 2 ressources à prendre
    """
    resource1: ResourceType
    resource2: ResourceType


@dataclass(frozen=True)
class PlayMonopolyAction:
    """
    Jouer une carte Monopole.

    resource: la ressource à monopoliser
    """
    resource: ResourceType


@dataclass(frozen=True)
class MoveRobberAction:
    """
    Déplacer le voleur (quand on fait 7).

    new_hex: hexagone où placer le voleur
    steal_from_player: joueur à voler (None si pas de joueur)
    """
    new_hex: HexCoord
    steal_from_player: int | None


@dataclass(frozen=True)
class DiscardResourcesAction:
    """
    Défausser des ressources (quand dé = 7 et > 7 cartes).

    resources: dictionnaire {ResourceType: quantité à défausser}
    """
    resources: dict[ResourceType, int]


@dataclass(frozen=True)
class EndTurnAction:
    """Terminer le tour."""
    pass


# Type union de toutes les actions
Action = Union[
    RollDiceAction,
    BuildSettlementAction,
    BuildCityAction,
    BuildRoadAction,
    BuyDevCardAction,
    TradeWithBankAction,
    TradeWithPortAction,
    PlayKnightAction,
    PlayRoadBuildingAction,
    PlayYearOfPlentyAction,
    PlayMonopolyAction,
    MoveRobberAction,
    DiscardResourcesAction,
    EndTurnAction,
]


def get_action_type(action: Action) -> ActionType:
    """Retourne le type d'une action."""
    action_type_map = {
        RollDiceAction: ActionType.ROLL_DICE,
        BuildSettlementAction: ActionType.BUILD_SETTLEMENT,
        BuildCityAction: ActionType.BUILD_CITY,
        BuildRoadAction: ActionType.BUILD_ROAD,
        BuyDevCardAction: ActionType.BUY_DEV_CARD,
        TradeWithBankAction: ActionType.TRADE_WITH_BANK,
        TradeWithPortAction: ActionType.TRADE_WITH_PORT,
        PlayKnightAction: ActionType.PLAY_KNIGHT,
        PlayRoadBuildingAction: ActionType.PLAY_ROAD_BUILDING,
        PlayYearOfPlentyAction: ActionType.PLAY_YEAR_OF_PLENTY,
        PlayMonopolyAction: ActionType.PLAY_MONOPOLY,
        MoveRobberAction: ActionType.MOVE_ROBBER,
        DiscardResourcesAction: ActionType.DISCARD_RESOURCES,
        EndTurnAction: ActionType.END_TURN,
    }
    return action_type_map[type(action)]
