#!/usr/bin/env python3
"""Lance la GUI Catane 1v1 (prototype H2H basé sur pygame).

Ce script fournit une boucle d'évènements minimale permettant de jouer
manuellement en s'appuyant sur `catan.gui.app.CatanH2HApp`. Il relie les
contrôleurs GUI au rendu pygame existant.

Raccourcis clavier principaux:
- ESPACE : lancer les dés
- R      : sélectionner la construction de route
- S      : sélectionner la construction de colonie
- C      : sélectionner la construction de ville
- E      : terminer le tour
- RETOUR : annuler l'action en cours
- ESC    : annuler l'action en cours ou quitter si aucune action
"""

from __future__ import annotations

import sys
from typing import Dict, Tuple

import pygame

from catan.app.game_service import GameService
from catan.gui.app import CatanH2HApp
from catan.gui.renderer import (
    COLOR_BG,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


KEY_BINDINGS: Tuple[Tuple[str, int, str], ...] = (
    ("SPACE", pygame.K_SPACE, "roll_dice"),
    ("E", pygame.K_e, "end_turn"),
    ("R", pygame.K_r, "select_build_road"),
    ("S", pygame.K_s, "select_build_settlement"),
    ("C", pygame.K_c, "select_build_city"),
    ("BACKSPACE", pygame.K_BACKSPACE, "cancel"),
)


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("CatanBot — GUI H2H (prototype)")

    app = CatanH2HApp(game_service=GameService(), screen=screen)
    app.start_new_game(player_names=["Bleu", "Orange"], seed=None)

    clock = pygame.time.Clock()
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 20, bold=True)
    small_font = pygame.font.SysFont("Arial", 16)

    running = True
    ui_state = app.get_ui_state()

    while running:
        ui_state_changed = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if app.mode in {"build_road", "build_settlement", "build_city", "move_robber"}:
                        app.trigger_action("cancel")
                        ui_state_changed = True
                    else:
                        running = False
                    continue

                for label, key, action in KEY_BINDINGS:
                    if event.key != key:
                        continue

                    button_state = ui_state.buttons.get(action)
                    if action == "cancel" or (button_state and button_state.enabled):
                        if app.trigger_action(action):
                            ui_state_changed = True
                    break

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos

                # Tentative sur les sommets en priorité
                if ui_state.highlight_vertices:
                    vertex_id = app.renderer.get_vertex_at_position(pos)
                    if vertex_id is not None and app.handle_board_vertex_click(vertex_id):
                        ui_state_changed = True
                        continue

                if ui_state.highlight_edges:
                    edge_id = app.renderer.get_edge_at_position(pos)
                    if edge_id is not None and app.handle_board_edge_click(edge_id):
                        ui_state_changed = True
                        continue

                # TODO(GUI-012): gestion clic tuile pour le voleur

        if ui_state_changed:
            ui_state = app.get_ui_state()

        # Rendu principal
        screen.fill(COLOR_BG)
        renderer = app.renderer
        renderer.render_board()
        renderer.render_pieces(app.state)

        if ui_state.highlight_vertices:
            renderer.render_highlighted_vertices(ui_state.highlight_vertices)
        if ui_state.highlight_edges:
            renderer.render_highlighted_edges(ui_state.highlight_edges)

        # Instructions
        instructions = font.render(ui_state.instructions, True, (255, 255, 255))
        screen.blit(instructions, (20, 20))

        # Tableau des actions disponibles
        y_offset = 60
        for label, key, action in KEY_BINDINGS:
            button_state = ui_state.buttons.get(action)
            enabled = button_state.enabled if button_state else False
            text = f"[{label}] {button_state.label if button_state else action}"
            color = (200, 255, 200) if enabled else (120, 120, 120)
            surf = small_font.render(text, True, color)
            screen.blit(surf, (20, y_offset))
            y_offset += 24

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())

