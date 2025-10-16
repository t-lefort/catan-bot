"""Tests pour le module board."""

import pytest
from src.core.board import HexCoord, VertexCoord, EdgeCoord, Board
from src.core.constants import TerrainType


def test_hex_coord_creation():
    """Test création de coordonnées hexagonales."""
    hex = HexCoord(0, 0)
    assert hex.q == 0
    assert hex.r == 0
    assert hex.s == 0


def test_hex_coord_neighbors():
    """Test voisins d'un hexagone."""
    hex = HexCoord(0, 0)
    neighbors = hex.neighbors()
    assert len(neighbors) == 6


def test_vertex_coord_adjacent_vertices():
    """Test sommets adjacents."""
    vertex = VertexCoord(HexCoord(0, 0), 0)
    adjacent = vertex.adjacent_vertices()
    assert len(adjacent) == 3


def test_vertex_coord_adjacent_hexes():
    """Test hexagones adjacents à un sommet."""
    vertex = VertexCoord(HexCoord(0, 0), 0)
    hexes = vertex.adjacent_hexes()
    assert len(hexes) == 3


def test_edge_coord_vertices():
    """Test sommets d'une arête."""
    edge = EdgeCoord(HexCoord(0, 0), 0)
    v1, v2 = edge.vertices()
    assert isinstance(v1, VertexCoord)
    assert isinstance(v2, VertexCoord)


def test_board_creation():
    """Test création d'un plateau."""
    board = Board.create_standard_board()
    assert len(board.hexes) > 0
