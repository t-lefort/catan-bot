"""Actions du jeu (ENG-002+).

Définit les actions possibles conformément aux schémas (docs/schemas.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Action:
    """Action de base."""

    pass


@dataclass(frozen=True)
class PlaceSettlement(Action):
    """Place une colonie sur un sommet.

    Args:
        vertex_id: ID du sommet
        free: True pendant setup (pas de coût)
    """

    vertex_id: int
    free: bool = False


@dataclass(frozen=True)
class PlaceRoad(Action):
    """Place une route sur une arête.

    Args:
        edge_id: ID de l'arête
        free: True pendant setup (pas de coût)
    """

    edge_id: int
    free: bool = False


@dataclass(frozen=True)
class BuildCity(Action):
    """Améliore une colonie en ville.

    Args:
        vertex_id: ID du sommet avec la colonie à améliorer
    """

    vertex_id: int


@dataclass(frozen=True)
class RollDice(Action):
    """Lance les dés.

    Args:
        forced_value: Valeur forcée pour les tests (optionnel)
    """

    forced_value: tuple[int, int] | None = None


@dataclass(frozen=True)
class MoveRobber(Action):
    """Déplace le voleur.

    Args:
        tile_id: ID de la tuile cible
        steal_from: ID du joueur à voler (optionnel)
    """

    tile_id: int
    steal_from: int | None = None


@dataclass(frozen=True)
class DiscardResources(Action):
    """Défausse des ressources lors d'un 7.

    Args:
        resources: Quantités à défausser par ressource.
    """

    resources: Dict[str, int]


@dataclass(frozen=True)
class EndTurn(Action):
    """Termine le tour du joueur actuel."""

    pass


__all__ = [
    "Action",
    "PlaceSettlement",
    "PlaceRoad",
    "BuildCity",
    "RollDice",
    "MoveRobber",
    "DiscardResources",
    "EndTurn",
]
