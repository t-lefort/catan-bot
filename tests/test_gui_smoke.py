"""Tests smoke GUI (GUI-002) — rendu headless pygame.

Objectif: valider que les composants de rendu pygame peuvent être
construits et initialisés en mode headless (SDL_VIDEODRIVER=dummy).

Couverture:
- Surface principale créée
- Rendu du plateau (hexagones, numéros, ports) sans crash
- Rendu des pièces (routes, colonies, villes) sans crash
- Pas de validation pixel-perfect, seulement non-régression
"""

import os
import sys
import pytest

# Force headless mode
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from catan.engine.board import Board
from catan.engine.state import GameState
from catan.gui.renderer import BoardRenderer, SCREEN_WIDTH, SCREEN_HEIGHT


@pytest.fixture
def headless_pygame():
    """Initialize pygame in headless mode."""
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def test_board():
    """Provide a standard board for rendering tests."""
    return Board.standard()


@pytest.fixture
def test_game_state():
    """Provide a minimal game state."""
    return GameState.new_1v1_game(seed=42)


def test_pygame_headless_init(headless_pygame):
    """Vérifie que pygame s'initialise correctement en mode headless."""
    assert pygame.get_init()
    # Headless mode should be active
    assert os.environ.get("SDL_VIDEODRIVER") == "dummy"


def test_screen_surface_creation(headless_pygame):
    """Vérifie qu'une surface pygame peut être créée."""
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    assert screen is not None
    assert screen.get_width() == SCREEN_WIDTH
    assert screen.get_height() == SCREEN_HEIGHT


def test_board_renderer_init(headless_pygame, test_board):
    """Vérifie que BoardRenderer peut être instancié."""
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer = BoardRenderer(screen, test_board)
    assert renderer is not None
    assert renderer.board == test_board


def test_render_board_no_crash(headless_pygame, test_board):
    """Vérifie que render_board() s'exécute sans crash."""
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer = BoardRenderer(screen, test_board)

    # Should not raise
    renderer.render_board()


def test_render_pieces_no_crash(headless_pygame, test_board, test_game_state):
    """Vérifie que render_pieces() s'exécute sans crash."""
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer = BoardRenderer(screen, test_board)

    # Should not raise
    renderer.render_pieces(test_game_state)


def test_render_full_frame_no_crash(headless_pygame, test_board, test_game_state):
    """Vérifie qu'un frame complet peut être rendu."""
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer = BoardRenderer(screen, test_board)

    # Clear screen
    screen.fill((30, 60, 90))

    # Render board + pieces
    renderer.render_board()
    renderer.render_pieces(test_game_state)

    # Update display (no-op in headless, but should not crash)
    pygame.display.flip()


def test_hex_vertices_computed(headless_pygame, test_board):
    """Vérifie que les coordonnées des hexagones sont calculées."""
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer = BoardRenderer(screen, test_board)

    # BoardRenderer should precompute hex vertices
    assert hasattr(renderer, "_hex_coords")
    assert len(renderer._hex_coords) == test_board.tile_count()

    # Each hex should have 6 vertices
    for tile_id in test_board.tiles:
        assert tile_id in renderer._hex_coords
        assert len(renderer._hex_coords[tile_id]) == 6


def test_board_renderer_has_right_offset(headless_pygame, test_board):
    """Le plateau doit laisser une marge suffisante à gauche pour le HUD."""

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer = BoardRenderer(screen, test_board)

    min_x = min(x for x, _ in renderer._vertex_screen_coords.values())
    assert min_x >= 240


def test_get_tile_at_position_returns_tile(headless_pygame, test_board):
    """Détecter la tuile cliquée doit renvoyer l'identifiant attendu."""

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    renderer = BoardRenderer(screen, test_board)

    # Utiliser le centre du désert (tile_id=0) pour valider la détection
    vertices = renderer._hex_coords[0]
    center_x = sum(v[0] for v in vertices) / len(vertices)
    center_y = sum(v[1] for v in vertices) / len(vertices)

    tile_id = renderer.get_tile_at_position((center_x, center_y))
    assert tile_id == 0

    # Un clic loin du plateau doit retourner None
    assert renderer.get_tile_at_position((0, 0)) is None
