"""Geometry utilities for board rendering.

Ce module fournit la classe BoardGeometry qui calcule les coordonnées écran
des éléments du plateau (sommets, arêtes, centres de tuiles) à partir de la
géométrie logique du Board.

Utilisé par BoardRenderer pour abstraire les calculs de transformation
logique -> écran et permettre le redimensionnement du plateau.
"""

from __future__ import annotations

from typing import Dict, Tuple

from catan.engine.board import Board


class BoardGeometry:
    """Compute screen coordinates from logical board positions.

    Cette classe prend en charge la transformation de coordonnées logiques
    (position des sommets dans le Board) vers coordonnées écran en pixels,
    avec marges et mise à l'échelle.
    """

    def __init__(self, board: Board, hex_radius: float, margin: float) -> None:
        """Initialize geometry calculator.

        Args:
            board: Game board
            hex_radius: Radius of a hexagon in pixels
            margin: Margin around the board in pixels
        """
        self.board = board
        self.hex_radius = hex_radius
        self.margin = margin

        # Precompute screen positions for all vertices
        self._vertex_positions: Dict[int, Tuple[float, float]] = {}
        self._compute_vertex_positions()

    def _compute_vertex_positions(self) -> None:
        """Compute screen positions for all vertices with margin alignment."""
        # First, scale all positions by hex_radius
        scaled_positions = {
            vid: (v.position[0] * self.hex_radius, v.position[1] * self.hex_radius)
            for vid, v in self.board.vertices.items()
        }

        # Find bounds
        min_x = min(x for x, _ in scaled_positions.values())
        min_y = min(y for _, y in scaled_positions.values())

        # Apply offset so that min position is at (margin, margin)
        self._vertex_positions = {
            vid: (x - min_x + self.margin, y - min_y + self.margin)
            for vid, (x, y) in scaled_positions.items()
        }

    def vertex_position(self, vertex_id: int) -> Tuple[float, float]:
        """Get screen position for a vertex.

        Args:
            vertex_id: ID of the vertex

        Returns:
            (x, y) screen coordinates in pixels
        """
        return self._vertex_positions[vertex_id]

    @property
    def surface_size(self) -> Tuple[float, float]:
        """Get the required surface size to contain the board.

        Returns:
            (width, height) in pixels
        """
        # Compute bounds from vertex positions
        min_x = min(x for x, _ in self._vertex_positions.values())
        max_x = max(x for x, _ in self._vertex_positions.values())
        min_y = min(y for _, y in self._vertex_positions.values())
        max_y = max(y for _, y in self._vertex_positions.values())

        width = max_x - min_x + 2 * self.margin
        height = max_y - min_y + 2 * self.margin

        return (width, height)


__all__ = ["BoardGeometry"]
