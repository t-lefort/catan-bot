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
from catan.gui.hud_controller import PlayerPanel
from catan.gui.app import DiscardPrompt
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


def test_ui_state_exposes_dice_and_player_panels(gui_app):
    """Le modèle UI doit exposer le lancer de dés et les panneaux joueurs."""

    app = gui_app
    _complete_setup(app)

    # Modifier manuellement l'état pour vérifier la remontée des ressources
    player0 = app.state.players[0]
    player1 = app.state.players[1]
    player0.resources.update({"BRICK": 3, "LUMBER": 2})
    player1.resources.update({"ORE": 1})

    # Lancer les dés avec une valeur forcée
    assert app.trigger_action("roll_dice", forced_value=9)

    ui_state = app.get_ui_state()

    assert ui_state.last_dice_roll == 9
    assert ui_state.dice_rolled_this_turn is True

    # Les panneaux joueurs doivent être exposés et refléter les ressources
    assert ui_state.player_panels
    assert all(isinstance(panel, PlayerPanel) for panel in ui_state.player_panels)

    panel0 = next(panel for panel in ui_state.player_panels if panel.player_id == 0)
    panel1 = next(panel for panel in ui_state.player_panels if panel.player_id == 1)

    assert panel0.resources["BRICK"] == 3
    assert panel0.is_current_player is True
    assert panel1.resources["ORE"] == 1
    assert panel1.is_current_player is False


def test_move_robber_via_ui_state(gui_app):
    """La sélection de tuile (voleur) doit être exposée et fonctionnelle."""

    app = gui_app
    _complete_setup(app)

    # Assurer qu'aucun joueur ne déclenche la défausse
    for player in app.state.players:
        for resource in player.resources:
            player.resources[resource] = 0

    assert app.trigger_action("roll_dice", forced_value=7)

    ui_state = app.get_ui_state()
    assert ui_state.mode == "move_robber"
    assert ui_state.highlight_tiles

    original_tile = app.state.robber_tile_id
    target_tile = next(iter(ui_state.highlight_tiles))

    assert app.handle_board_tile_click(target_tile)

    assert app.state.robber_tile_id == target_tile
    assert app.state.robber_tile_id != original_tile
    assert app.get_ui_state().mode == "idle"
    assert app.renderer.board.tiles[target_tile].has_robber is True
    assert app.renderer.board.tiles[original_tile].has_robber is False


def test_discard_flow_selection_and_confirmation(gui_app):
    """La phase de défausse doit exposer une interface sélectionnable et appliquer l'action."""

    app = gui_app
    _complete_setup(app)

    player_id = app.state.current_player_id
    current = app.state.players[player_id]
    for res in current.resources:
        current.resources[res] = 0
    current.resources.update({"BRICK": 4, "LUMBER": 4, "GRAIN": 4})  # Total 12 -> discard 3
    app.refresh_state()

    assert app.trigger_action("roll_dice", forced_value=7)

    ui_state = app.get_ui_state()
    assert ui_state.mode == "discard"
    assert isinstance(ui_state.discard_prompt, DiscardPrompt)
    prompt = ui_state.discard_prompt
    assert prompt.required == 3
    assert prompt.remaining == 3
    assert prompt.selection == {}
    assert prompt.can_confirm is False

    # Ajuster la sélection
    assert app.adjust_discard_selection("BRICK", 2) is True
    assert app.adjust_discard_selection("GRAIN", 1) is True

    ui_state = app.get_ui_state()
    prompt = ui_state.discard_prompt
    assert prompt.remaining == 0
    assert prompt.selection["BRICK"] == 2
    assert prompt.selection["GRAIN"] == 1
    assert prompt.can_confirm is True

    # Confirmer la défausse
    assert app.confirm_discard_selection() is True
    refreshed_player = app.state.players[player_id]
    assert refreshed_player.resources["BRICK"] == 2
    assert refreshed_player.resources["GRAIN"] == 3

    # La phase doit passer au déplacement du voleur
    ui_state = app.get_ui_state()
    assert ui_state.mode == "move_robber"
