"""Tests d'intégration légère pour catan.gui.app (GUI-011).

Ces tests valident le modèle d'orchestration de la GUI (sans boucle
pygame) en s'assurant que:
- l'application démarre en mode setup avec les bons highlights,
- la phase de setup peut être complétée via les clics contrôleurs,
- les actions principales (lancer de dés, construction route) sont
  exposées via le modèle et mettent à jour l'état du jeu.

Le rendu visuel complet n'est pas testé ici — uniquement la logique
de coordination entre GameService et les contrôleurs GUI.
"""

from __future__ import annotations

import os
import pytest

# Forcer le mode headless pour pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from catan.app.game_service import GameService
from catan.engine.state import SetupPhase


@pytest.fixture
def pygame_screen():
    """Initialise pygame en mode headless et retourne une surface écran."""

    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    try:
        yield screen
    finally:
        pygame.quit()


@pytest.fixture
def gui_app(pygame_screen):
    """Construit l'application GUI et démarre une nouvelle partie."""

    from catan.gui.app import CatanH2HApp

    service = GameService()
    app = CatanH2HApp(game_service=service, screen=pygame_screen)
    app.start_new_game(player_names=["Bleu", "Orange"], seed=42)
    return app


def test_app_starts_in_setup_mode(gui_app):
    """L'application démarre en phase setup avec vertices en surbrillance."""

    ui_state = gui_app.get_ui_state()

    assert ui_state.mode == "setup"
    assert ui_state.phase == SetupPhase.SETUP_ROUND_1
    assert ui_state.highlight_vertices  # positions disponibles
    assert not ui_state.highlight_edges  # pas d'arêtes tant que colonie non placée
    assert not ui_state.buttons["roll_dice"].enabled


def _complete_setup(app):
    """Complète la phase de setup en utilisant les contrôleurs."""

    safety = 0
    while app.state.phase != SetupPhase.PLAY:
        safety += 1
        assert safety < 50, "Setup ne devrait pas nécessiter plus de 16 actions"

        ui_state = app.get_ui_state()

        if ui_state.highlight_vertices:
            vertex_id = next(iter(ui_state.highlight_vertices))
            assert app.handle_board_vertex_click(vertex_id)
        elif ui_state.highlight_edges:
            edge_id = next(iter(ui_state.highlight_edges))
            assert app.handle_board_edge_click(edge_id)
        else:
            pytest.fail("Aucune position légale détectée pendant le setup")


def test_complete_setup_then_idle(gui_app):
    """La phase setup s'achève et passe en mode jeu standard."""

    app = gui_app
    _complete_setup(app)

    assert app.state.phase == SetupPhase.PLAY

    ui_state = app.get_ui_state()
    assert ui_state.mode == "idle"
    assert ui_state.buttons["roll_dice"].enabled
    assert not ui_state.highlight_vertices
    assert not ui_state.highlight_edges


def test_roll_dice_action(gui_app):
    """Le bouton lancer les dés appelle le contrôleur et désactive l'action."""

    app = gui_app
    _complete_setup(app)

    assert app.trigger_action("roll_dice", forced_value=8)
    assert app.state.dice_rolled_this_turn
    ui_state = app.get_ui_state()
    assert not ui_state.buttons["roll_dice"].enabled
    assert ui_state.buttons["end_turn"].enabled


def test_build_road_flow(gui_app):
    """Séquence sélection build road + clic arête construit une route."""

    app = gui_app
    _complete_setup(app)

    # Tourne le jeu pour permettre les actions
    assert app.trigger_action("roll_dice", forced_value=5)

    # Donner suffisamment de ressources au joueur courant
    player = app.state.players[app.state.current_player_id]
    player.resources.update({"BRICK": 5, "LUMBER": 5, "WOOL": 2, "GRAIN": 2, "ORE": 3})
    app.refresh_state()

    previous_roads = set(player.roads)

    assert app.trigger_action("select_build_road")
    ui_state = app.get_ui_state()
    assert ui_state.mode == "build_road"
    assert ui_state.highlight_edges

    edge_id = next(iter(ui_state.highlight_edges))
    assert app.handle_board_edge_click(edge_id)

    assert edge_id in app.state.players[player.player_id].roads
    assert app.get_ui_state().mode == "idle"
