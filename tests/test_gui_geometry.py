import math

from catan.engine.board import Board
from catan.gui.geometry import BoardGeometry

# Tests écrits avant implémentation (TDD) pour `catan.gui.geometry.BoardGeometry`.


def test_board_geometry_margin_alignment() -> None:
    board = Board.standard()
    geometry = BoardGeometry(board, hex_radius=80.0, margin=24.0)

    positions = [geometry.vertex_position(vertex_id) for vertex_id in board.vertices.keys()]

    min_x = min(pos[0] for pos in positions)
    min_y = min(pos[1] for pos in positions)

    assert math.isclose(min_x, 24.0, abs_tol=1e-6)
    assert math.isclose(min_y, 24.0, abs_tol=1e-6)


def test_board_geometry_relative_distance_scaling() -> None:
    board = Board.standard()
    radius = 70.0
    geometry = BoardGeometry(board, hex_radius=radius, margin=20.0)

    vertex_a = board.vertices[0].position
    vertex_b = board.vertices[1].position

    screen_a = geometry.vertex_position(0)
    screen_b = geometry.vertex_position(1)

    assert math.isclose(screen_b[0] - screen_a[0], (vertex_b[0] - vertex_a[0]) * radius, abs_tol=1e-6)
    assert math.isclose(screen_b[1] - screen_a[1], (vertex_b[1] - vertex_a[1]) * radius, abs_tol=1e-6)


def test_board_geometry_surface_size_matches_bounds() -> None:
    board = Board.standard()
    radius = 90.0
    margin = 30.0
    geometry = BoardGeometry(board, hex_radius=radius, margin=margin)

    width, height = geometry.surface_size

    scaled_positions = [
        (vertex.position[0] * radius, vertex.position[1] * radius)
        for vertex in board.vertices.values()
    ]
    min_x = min(x for x, _ in scaled_positions)
    max_x = max(x for x, _ in scaled_positions)
    min_y = min(y for _, y in scaled_positions)
    max_y = max(y for _, y in scaled_positions)

    expected_width = max_x - min_x + 2 * margin
    expected_height = max_y - min_y + 2 * margin

    assert math.isclose(width, expected_width, abs_tol=1e-6)
    assert math.isclose(height, expected_height, abs_tol=1e-6)
