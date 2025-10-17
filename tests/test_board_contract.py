import pytest


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

