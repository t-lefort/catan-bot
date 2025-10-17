"""Plateau de jeu — contrat minimal pour tests.

Expose une classe `Board` avec:
- `Board.standard()` pour créer un plateau standard (19 tuiles)
- méthodes `tile_count()`, `vertex_count()`, `edge_count()`

Remarque: Il s'agit d'une implémentation minimale pour satisfaire les
tests de contrat. La modélisation détaillée (hex, ports, indexations) sera
introduite dans ENG-001.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Board:
    _tiles: int
    _vertices: int
    _edges: int

    @classmethod
    def standard(cls) -> "Board":
        # Comptages standard Catane: 19 tuiles, 54 sommets, 72 arêtes
        return cls(_tiles=19, _vertices=54, _edges=72)

    # Helpers de comptage (contrat minimal pour tests)
    def tile_count(self) -> int:
        return self._tiles

    def vertex_count(self) -> int:
        return self._vertices

    def edge_count(self) -> int:
        return self._edges

__all__ = ["Board"]

