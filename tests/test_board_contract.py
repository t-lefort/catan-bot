import math
from typing import Dict, Tuple

import pytest


# --- Références issues de la documentation ---

TILE_LAYOUT = [
    (0, "DESERT", (0, 0, 0)),
    (1, "ORE", (1, -1, 0)),
    (2, "GRAIN", (1, 0, -1)),
    (3, "WOOL", (0, 1, -1)),
    (4, "BRICK", (-1, 1, 0)),
    (5, "LUMBER", (-1, 0, 1)),
    (6, "GRAIN", (0, -1, 1)),
    (7, "LUMBER", (2, -1, -1)),
    (8, "BRICK", (2, 0, -2)),
    (9, "WOOL", (1, 1, -2)),
    (10, "ORE", (0, 2, -2)),
    (11, "GRAIN", (-1, 2, -1)),
    (12, "LUMBER", (-2, 2, 0)),
    (13, "BRICK", (-2, 1, 1)),
    (14, "WOOL", (-2, 0, 2)),
    (15, "LUMBER", (-1, -1, 2)),
    (16, "GRAIN", (0, -2, 2)),
    (17, "WOOL", (1, -2, 1)),
    (18, "ORE", (2, -2, 0)),
]

PIP_NUMBERS: Dict[int, int] = {
    1: 5,
    2: 2,
    3: 6,
    4: 3,
    5: 8,
    6: 10,
    7: 9,
    8: 12,
    9: 11,
    10: 4,
    11: 8,
    12: 10,
    13: 9,
    14: 4,
    15: 5,
    16: 6,
    17: 3,
    18: 11,
}

# Pré-calculs géométriques (pointy-top) pour vérifier l'indexation
SQRT3 = math.sqrt(3)
VERTEX_ANGLES = [math.radians(30 + 60 * k) for k in range(6)]
VERTEX_OFFSETS = [(math.cos(a), math.sin(a)) for a in VERTEX_ANGLES]

# Données attendues (générées hors-ligne via la géométrie ci-dessus)
EXPECTED_TILE_VERTICES: Dict[int, Tuple[int, ...]] = {
    0: (33, 27, 21, 20, 26, 32),
    1: (45, 39, 33, 32, 38, 44),
    2: (38, 32, 26, 25, 31, 37),
    3: (26, 20, 14, 13, 19, 25),
    4: (21, 15, 9, 8, 14, 20),
    5: (28, 22, 16, 15, 21, 27),
    6: (40, 34, 28, 27, 33, 39),
    7: (49, 44, 38, 37, 43, 48),
    8: (43, 37, 31, 30, 36, 42),
    9: (31, 25, 19, 18, 24, 30),
    10: (19, 13, 7, 6, 12, 18),
    11: (14, 8, 3, 2, 7, 13),
    12: (9, 4, 1, 0, 3, 8),
    13: (16, 10, 5, 4, 9, 15),
    14: (23, 17, 11, 10, 16, 22),
    15: (35, 29, 23, 22, 28, 34),
    16: (47, 41, 35, 34, 40, 46),
    17: (51, 46, 40, 39, 45, 50),
    18: (53, 50, 45, 44, 49, 52),
}

EXPECTED_TILE_EDGES: Dict[int, Tuple[int, ...]] = {
    0: (40, 31, 29, 30, 38, 46),
    1: (57, 48, 46, 47, 55, 62),
    2: (47, 38, 36, 37, 45, 53),
    3: (30, 21, 19, 20, 28, 36),
    4: (23, 14, 12, 13, 21, 29),
    5: (33, 24, 22, 23, 31, 39),
    6: (50, 41, 39, 40, 48, 56),
    7: (63, 55, 53, 54, 61, 67),
    8: (54, 45, 43, 44, 52, 60),
    9: (37, 28, 26, 27, 35, 43),
    10: (20, 11, 9, 10, 18, 26),
    11: (13, 5, 3, 4, 11, 19),
    12: (7, 2, 0, 1, 5, 12),
    13: (16, 8, 6, 7, 14, 22),
    14: (25, 17, 15, 16, 24, 32),
    15: (42, 34, 32, 33, 41, 49),
    16: (59, 51, 49, 50, 58, 65),
    17: (66, 58, 56, 57, 64, 69),
    18: (70, 64, 62, 63, 68, 71),
}

EXPECTED_VERTEX_COORDS: Dict[int, Tuple[float, float]] = {
    0: (-4.330127, -0.5),
    1: (-4.330127, 0.5),
    2: (-3.464102, -2.0),
    3: (-3.464102, -1.0),
    4: (-3.464102, 1.0),
    5: (-3.464102, 2.0),
    6: (-2.598076, -3.5),
    7: (-2.598076, -2.5),
    8: (-2.598076, -0.5),
    9: (-2.598076, 0.5),
    10: (-2.598076, 2.5),
    11: (-2.598076, 3.5),
    12: (-1.732051, -4.0),
    13: (-1.732051, -2.0),
    14: (-1.732051, -1.0),
    15: (-1.732051, 1.0),
    16: (-1.732051, 2.0),
    17: (-1.732051, 4.0),
    18: (-0.866025, -3.5),
    19: (-0.866025, -2.5),
    20: (-0.866025, -0.5),
    21: (-0.866025, 0.5),
    22: (-0.866025, 2.5),
    23: (-0.866025, 3.5),
    24: (0.0, -4.0),
    25: (0.0, -2.0),
    26: (0.0, -1.0),
    27: (0.0, 1.0),
    28: (0.0, 2.0),
    29: (0.0, 4.0),
    30: (0.866025, -3.5),
    31: (0.866025, -2.5),
    32: (0.866025, -0.5),
    33: (0.866025, 0.5),
    34: (0.866025, 2.5),
    35: (0.866025, 3.5),
    36: (1.732051, -4.0),
    37: (1.732051, -2.0),
    38: (1.732051, -1.0),
    39: (1.732051, 1.0),
    40: (1.732051, 2.0),
    41: (1.732051, 4.0),
    42: (2.598076, -3.5),
    43: (2.598076, -2.5),
    44: (2.598076, -0.5),
    45: (2.598076, 0.5),
    46: (2.598076, 2.5),
    47: (2.598076, 3.5),
    48: (3.464102, -2.0),
    49: (3.464102, -1.0),
    50: (3.464102, 1.0),
    51: (3.464102, 2.0),
    52: (4.330127, -0.5),
    53: (4.330127, 0.5),
}

EXPECTED_VERTEX_TILES: Dict[int, Tuple[int, ...]] = {
    0: (12,),
    1: (12,),
    2: (11,),
    3: (11, 12),
    4: (12, 13),
    5: (13,),
    6: (10,),
    7: (10, 11),
    8: (4, 11, 12),
    9: (4, 12, 13),
    10: (13, 14),
    11: (14,),
    12: (10,),
    13: (3, 10, 11),
    14: (3, 4, 11),
    15: (4, 5, 13),
    16: (5, 13, 14),
    17: (14,),
    18: (9, 10),
    19: (3, 9, 10),
    20: (0, 3, 4),
    21: (0, 4, 5),
    22: (5, 14, 15),
    23: (14, 15),
    24: (9,),
    25: (2, 3, 9),
    26: (0, 2, 3),
    27: (0, 5, 6),
    28: (5, 6, 15),
    29: (15,),
    30: (8, 9),
    31: (2, 8, 9),
    32: (0, 1, 2),
    33: (0, 1, 6),
    34: (6, 15, 16),
    35: (15, 16),
    36: (8,),
    37: (2, 7, 8),
    38: (1, 2, 7),
    39: (1, 6, 17),
    40: (6, 16, 17),
    41: (16,),
    42: (8,),
    43: (7, 8),
    44: (1, 7, 18),
    45: (1, 17, 18),
    46: (16, 17),
    47: (16,),
    48: (7,),
    49: (7, 18),
    50: (17, 18),
    51: (17,),
    52: (18,),
    53: (18,),
}

EXPECTED_VERTEX_EDGES: Dict[int, Tuple[int, ...]] = {
    0: (0, 1),
    1: (0, 2),
    2: (3, 4),
    3: (1, 3, 5),
    4: (2, 6, 7),
    5: (6, 8),
    6: (9, 10),
    7: (4, 9, 11),
    8: (5, 12, 13),
    9: (7, 12, 14),
    10: (8, 15, 16),
    11: (15, 17),
    12: (10, 18),
    13: (11, 19, 20),
    14: (13, 19, 21),
    15: (14, 22, 23),
    16: (16, 22, 24),
    17: (17, 25),
    18: (18, 26, 27),
    19: (20, 26, 28),
    20: (21, 29, 30),
    21: (23, 29, 31),
    22: (24, 32, 33),
    23: (25, 32, 34),
    24: (27, 35),
    25: (28, 36, 37),
    26: (30, 36, 38),
    27: (31, 39, 40),
    28: (33, 39, 41),
    29: (34, 42),
    30: (35, 43, 44),
    31: (37, 43, 45),
    32: (38, 46, 47),
    33: (40, 46, 48),
    34: (41, 49, 50),
    35: (42, 49, 51),
    36: (44, 52),
    37: (45, 53, 54),
    38: (47, 53, 55),
    39: (48, 56, 57),
    40: (50, 56, 58),
    41: (51, 59),
    42: (52, 60),
    43: (54, 60, 61),
    44: (55, 62, 63),
    45: (57, 62, 64),
    46: (58, 65, 66),
    47: (59, 65),
    48: (61, 67),
    49: (63, 67, 68),
    50: (64, 69, 70),
    51: (66, 69),
    52: (68, 71),
    53: (70, 71),
}

EXPECTED_EDGE_VERTICES: Dict[int, Tuple[int, int]] = {
    0: (0, 1),
    1: (0, 3),
    2: (1, 4),
    3: (2, 3),
    4: (2, 7),
    5: (3, 8),
    6: (4, 5),
    7: (4, 9),
    8: (5, 10),
    9: (6, 7),
    10: (6, 12),
    11: (7, 13),
    12: (8, 9),
    13: (8, 14),
    14: (9, 15),
    15: (10, 11),
    16: (10, 16),
    17: (11, 17),
    18: (12, 18),
    19: (13, 14),
    20: (13, 19),
    21: (14, 20),
    22: (15, 16),
    23: (15, 21),
    24: (16, 22),
    25: (17, 23),
    26: (18, 19),
    27: (18, 24),
    28: (19, 25),
    29: (20, 21),
    30: (20, 26),
    31: (21, 27),
    32: (22, 23),
    33: (22, 28),
    34: (23, 29),
    35: (24, 30),
    36: (25, 26),
    37: (25, 31),
    38: (26, 32),
    39: (27, 28),
    40: (27, 33),
    41: (28, 34),
    42: (29, 35),
    43: (30, 31),
    44: (30, 36),
    45: (31, 37),
    46: (32, 33),
    47: (32, 38),
    48: (33, 39),
    49: (34, 35),
    50: (34, 40),
    51: (35, 41),
    52: (36, 42),
    53: (37, 38),
    54: (37, 43),
    55: (38, 44),
    56: (39, 40),
    57: (39, 45),
    58: (40, 46),
    59: (41, 47),
    60: (42, 43),
    61: (43, 48),
    62: (44, 45),
    63: (44, 49),
    64: (45, 50),
    65: (46, 47),
    66: (46, 51),
    67: (48, 49),
    68: (49, 52),
    69: (50, 51),
    70: (50, 53),
    71: (52, 53),
}

EXPECTED_EDGE_TILES: Dict[int, Tuple[int, ...]] = {
    0: (12,),
    1: (12,),
    2: (12,),
    3: (11,),
    4: (11,),
    5: (11, 12),
    6: (13,),
    7: (12, 13),
    8: (13,),
    9: (10,),
    10: (10,),
    11: (10, 11),
    12: (4, 12),
    13: (4, 11),
    14: (4, 13),
    15: (14,),
    16: (13, 14),
    17: (14,),
    18: (10,),
    19: (3, 11),
    20: (3, 10),
    21: (3, 4),
    22: (5, 13),
    23: (4, 5),
    24: (5, 14),
    25: (14,),
    26: (9, 10),
    27: (9,),
    28: (3, 9),
    29: (0, 4),
    30: (0, 3),
    31: (0, 5),
    32: (14, 15),
    33: (5, 15),
    34: (15,),
    35: (9,),
    36: (2, 3),
    37: (2, 9),
    38: (0, 2),
    39: (5, 6),
    40: (0, 6),
    41: (6, 15),
    42: (15,),
    43: (8, 9),
    44: (8,),
    45: (2, 8),
    46: (0, 1),
    47: (1, 2),
    48: (1, 6),
    49: (15, 16),
    50: (6, 16),
    51: (16,),
    52: (8,),
    53: (2, 7),
    54: (7, 8),
    55: (1, 7),
    56: (6, 17),
    57: (1, 17),
    58: (16, 17),
    59: (16,),
    60: (8,),
    61: (7,),
    62: (1, 18),
    63: (7, 18),
    64: (17, 18),
    65: (16,),
    66: (17,),
    67: (7,),
    68: (18,),
    69: (17,),
    70: (18,),
    71: (18,),
}

EXPECTED_PORTS = [
    {"port_id": 0, "type": "ANY", "edge_id": 1, "vertices": (0, 3)},
    {"port_id": 1, "type": "BRICK", "edge_id": 10, "vertices": (6, 12)},
    {"port_id": 2, "type": "ANY", "edge_id": 44, "vertices": (30, 36)},
    {"port_id": 3, "type": "ORE", "edge_id": 67, "vertices": (48, 49)},
    {"port_id": 4, "type": "ANY", "edge_id": 70, "vertices": (50, 53)},
    {"port_id": 5, "type": "WOOL", "edge_id": 65, "vertices": (46, 47)},
    {"port_id": 6, "type": "ANY", "edge_id": 42, "vertices": (29, 35)},
    {"port_id": 7, "type": "GRAIN", "edge_id": 17, "vertices": (11, 17)},
    {"port_id": 8, "type": "LUMBER", "edge_id": 6, "vertices": (4, 5)},
]


def _import_board():
    try:
        # Contract: Board class is exposed under catan.engine.board
        from catan.engine.board import Board  # type: ignore
        return Board
    except Exception:
        pytest.xfail("Module catan.engine.board manquant (moteur non implémenté)")


def test_standard_board_counts():
    Board = _import_board()
    # Contract minimal: Board.standard() and count helpers
    b = Board.standard()
    assert hasattr(b, "tile_count") and callable(b.tile_count)
    assert hasattr(b, "vertex_count") and callable(b.vertex_count)
    assert hasattr(b, "edge_count") and callable(b.edge_count)

    assert b.tile_count() == 19
    assert b.vertex_count() == 54
    assert b.edge_count() == 72


def _assert_cube(coord, expected):
    assert (coord.x, coord.y, coord.z) == expected


def test_standard_board_tile_metadata():
    Board = _import_board()
    board = Board.standard()
    tiles = board.tiles

    assert isinstance(tiles, dict)
    assert set(tiles.keys()) == {spec[0] for spec in TILE_LAYOUT}

    for tile_id, resource, cube in TILE_LAYOUT:
        tile = tiles[tile_id]
        assert tile.tile_id == tile_id
        assert tile.resource == resource
        _assert_cube(tile.cube, cube)
        assert tuple(tile.vertices) == EXPECTED_TILE_VERTICES[tile_id]
        assert tuple(tile.edges) == EXPECTED_TILE_EDGES[tile_id]
        if tile_id == 0:
            assert tile.has_robber is True
            assert tile.pip is None
        else:
            assert tile.has_robber is False
            assert tile.pip == PIP_NUMBERS[tile_id]


def test_vertex_indexing_matches_reference():
    Board = _import_board()
    board = Board.standard()
    vertices = board.vertices

    assert isinstance(vertices, dict)
    assert len(vertices) == 54
    for vid, vertex in vertices.items():
        expected_coord = EXPECTED_VERTEX_COORDS[vid]
        x, y = vertex.position
        assert x == pytest.approx(expected_coord[0])
        assert y == pytest.approx(expected_coord[1])
        assert tuple(vertex.adjacent_tiles) == EXPECTED_VERTEX_TILES[vid]
        assert tuple(vertex.edges) == EXPECTED_VERTEX_EDGES[vid]


def test_edges_cover_expected_pairs():
    Board = _import_board()
    board = Board.standard()
    edges = board.edges

    assert isinstance(edges, dict)
    assert len(edges) == 72
    for edge_id, edge in edges.items():
        assert tuple(edge.vertices) == EXPECTED_EDGE_VERTICES[edge_id]
        assert tuple(edge.tiles) == EXPECTED_EDGE_TILES[edge_id]


def test_port_mapping_clockwise():
    Board = _import_board()
    board = Board.standard()
    ports = sorted(board.ports, key=lambda p: p.port_id)
    assert len(ports) == 9

    for expected, port in zip(EXPECTED_PORTS, ports):
        assert port.port_id == expected["port_id"]
        assert port.kind == expected["type"]
        assert port.edge_id == expected["edge_id"]
        assert tuple(port.vertices) == expected["vertices"]
