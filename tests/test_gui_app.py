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
from catan.engine.rules import DISCARD_THRESHOLD


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


def test_gui_allows_selecting_monopoly_resource(gui_app):
    """Le joueur peut choisir la ressource ciblée avant de jouer Monopole."""

    app = gui_app
    _complete_setup(app)

    assert app.trigger_action("roll_dice", forced_value=6)

    current_id = app.state.current_player_id
    opponent_id = 1 - current_id
    player = app.state.players[current_id]
    opponent = app.state.players[opponent_id]

    for res in player.resources:
        player.resources[res] = 0
    for res in opponent.resources:
        opponent.resources[res] = 0

    player.dev_cards["MONOPOLY"] = 1
    opponent.resources.update({"BRICK": 1, "ORE": 2})
    app.refresh_state()

    assert app.trigger_action("play_monopoly", resource="ORE")

    updated_player = app.state.players[current_id]
    updated_opponent = app.state.players[opponent_id]

    assert updated_opponent.resources["ORE"] == 0
    assert updated_opponent.resources["BRICK"] == 1
    assert updated_player.resources["ORE"] == 2
    assert updated_player.resources["BRICK"] == 0
    assert updated_player.dev_cards["MONOPOLY"] == 0


def test_gui_bank_trade_uses_selected_resources(gui_app):
    """Le commerce banque doit respecter les ressources choisies par l'utilisateur via l'interface."""

    app = gui_app
    _complete_setup(app)

    assert app.trigger_action("roll_dice", forced_value=4)

    current_id = app.state.current_player_id
    player = app.state.players[current_id]
    for res in player.resources:
        player.resources[res] = 0

    trade_rates = app.trade_controller.get_bank_trade_rates()
    wool_rate = trade_rates["WOOL"]
    brick_rate = trade_rates["BRICK"]

    player.resources["BRICK"] = brick_rate
    player.resources["WOOL"] = wool_rate
    app.refresh_state()

    # Ouvrir l'interface d'échange banque
    assert app.trigger_action("bank_trade")
    assert app.mode == "bank_trade"

    # Sélectionner les ressources à donner (WOOL selon le taux)
    for _ in range(wool_rate):
        assert app.adjust_bank_trade_give("WOOL", 1)

    # Sélectionner la ressource à recevoir
    assert app.select_bank_trade_receive("ORE")

    # Confirmer l'échange
    assert app.confirm_bank_trade_selection()

    # Vérifier que l'échange a été effectué
    updated_player = app.state.players[current_id]
    assert updated_player.resources["WOOL"] == 0
    assert updated_player.resources["ORE"] == 1
    assert updated_player.resources["BRICK"] == brick_rate
    assert app.mode == "idle"


def test_discard_flow_selection_and_confirmation(gui_app):
    """La phase de défausse doit exposer une interface sélectionnable et appliquer l'action."""

    app = gui_app
    _complete_setup(app)

    player_id = app.state.current_player_id
    current = app.state.players[player_id]
    for res in current.resources:
        current.resources[res] = 0
    current.resources.update({"BRICK": 4, "LUMBER": 4, "GRAIN": 4})  # Total 12 -> discard 6 (12 // 2)
    app.refresh_state()

    assert app.trigger_action("roll_dice", forced_value=7)

    ui_state = app.get_ui_state()
    assert ui_state.mode == "discard"
    assert isinstance(ui_state.discard_prompt, DiscardPrompt)
    prompt = ui_state.discard_prompt
    assert prompt.required == 6  # 12 cartes -> défausser la moitié
    assert prompt.remaining == 6
    assert prompt.selection == {}
    assert prompt.can_confirm is False

    # Ajuster la sélection
    assert app.adjust_discard_selection("BRICK", 3) is True
    assert app.adjust_discard_selection("LUMBER", 2) is True
    assert app.adjust_discard_selection("GRAIN", 1) is True

    ui_state = app.get_ui_state()
    prompt = ui_state.discard_prompt
    assert prompt.remaining == 0
    assert prompt.selection["BRICK"] == 3
    assert prompt.selection["LUMBER"] == 2
    assert prompt.selection["GRAIN"] == 1
    assert prompt.can_confirm is True

    # Confirmer la défausse
    assert app.confirm_discard_selection() is True
    refreshed_player = app.state.players[player_id]
    # Après avoir défaussé 3 BRICK, 2 LUMBER, 1 GRAIN, il reste:
    # BRICK: 4 - 3 = 1, LUMBER: 4 - 2 = 2, GRAIN: 4 - 1 = 3
    assert refreshed_player.resources["BRICK"] == 1
    assert refreshed_player.resources["LUMBER"] == 2
    assert refreshed_player.resources["GRAIN"] == 3

    # La phase doit passer au déplacement du voleur
    ui_state = app.get_ui_state()
    assert ui_state.mode == "move_robber"


def test_buy_development_action_button(gui_app):
    """Le bouton acheter carte développement doit être listé et fonctionner."""

    app = gui_app
    _complete_setup(app)

    player = app.state.players[app.state.current_player_id]
    for resource in player.resources:
        player.resources[resource] = 0
    player.resources.update({"WOOL": 1, "GRAIN": 1, "ORE": 1})

    app.refresh_state()
    assert app.trigger_action("roll_dice", forced_value=6)

    ui_state = app.get_ui_state()
    assert "buy_development" in ui_state.buttons
    assert ui_state.buttons["buy_development"].enabled is True

    total_new_cards_before = sum(player.new_dev_cards.values())
    assert app.trigger_action("buy_development") is True

    ui_state_after = app.get_ui_state()
    assert ui_state_after.buttons["buy_development"].enabled is False
    total_new_cards_after = sum(app.state.players[player.player_id].new_dev_cards.values())
    assert total_new_cards_after == total_new_cards_before + 1


def test_discard_requirements_both_players(gui_app):
    """Les exigences de défausse doivent être correctes pour chaque joueur successivement."""

    app = gui_app
    _complete_setup(app)

    player0 = app.state.players[0]
    player1 = app.state.players[1]

    for resource in player0.resources:
        player0.resources[resource] = 0
    for resource in player1.resources:
        player1.resources[resource] = 0

    player0.resources.update({"BRICK": 5, "LUMBER": 5, "WOOL": 1})  # 11 -> discard 5 (11 // 2)
    player1.resources.update({"BRICK": 4, "LUMBER": 4, "GRAIN": 4, "ORE": 1})  # 13 -> discard 6 (13 // 2)

    app.refresh_state()
    assert app.trigger_action("roll_dice", forced_value=7)

    ui_state = app.get_ui_state()
    assert ui_state.mode == "discard"
    prompt = ui_state.discard_prompt
    assert prompt is not None
    # Joueur 0 a 11 cartes -> doit défausser 11 // 2 = 5 cartes
    expected_p0 = sum(app.state.players[0].resources.values()) // 2
    assert prompt.required == expected_p0
    assert prompt.remaining == expected_p0

    assert app.adjust_discard_selection("BRICK", 3)
    assert app.adjust_discard_selection("LUMBER", expected_p0 - 3)
    assert app.confirm_discard_selection()

    ui_state = app.get_ui_state()
    assert ui_state.mode == "discard"
    prompt = ui_state.discard_prompt
    assert prompt is not None
    # Joueur 1 a 13 cartes -> doit défausser 13 // 2 = 6 cartes
    expected_p1 = sum(app.state.players[1].resources.values()) // 2
    assert prompt.required == expected_p1
    assert prompt.remaining == expected_p1


def test_road_building_interactive_selection(gui_app):
    """La carte Road Building doit permettre au joueur de choisir où placer les routes."""

    app = gui_app
    _complete_setup(app)

    assert app.trigger_action("roll_dice", forced_value=4)

    current_id = app.state.current_player_id
    player = app.state.players[current_id]

    # Donner une carte Road Building au joueur
    player.dev_cards["ROAD_BUILDING"] = 1
    player.new_dev_cards["ROAD_BUILDING"] = 0
    app.refresh_state()

    # Déclencher l'action Road Building
    assert app.trigger_action("play_road_building")
    assert app.mode == "select_road_building"

    # Obtenir les cibles légales
    targets = app.development_controller.get_legal_road_building_targets()
    assert len(targets) > 0

    # Sélectionner la première cible
    edge1, edge2 = targets[0]

    # Cliquer sur la première arête
    assert app.handle_board_edge_click(edge1)
    assert len(app._road_building_edges) == 1

    # Cliquer sur la deuxième arête
    assert app.handle_board_edge_click(edge2)

    # Vérifier que les routes ont été placées et que le mode est revenu à idle
    assert app.mode == "idle"
    updated_player = app.state.players[current_id]
    assert updated_player.dev_cards["ROAD_BUILDING"] == 0
