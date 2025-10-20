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
from typing import Dict, Tuple, Iterable, Optional

import pygame

from catan.app.game_service import GameService
from catan.gui.app import CatanH2HApp, DiscardPrompt
from catan.gui.hud_controller import PlayerPanel
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

    def format_resource_summary(resources: Dict[str, int]) -> str:
        parts = [f"{res}:{count}" for res, count in resources.items() if count > 0]
        return ", ".join(parts) if parts else "Aucune"

    def format_dev_summary(cards: Dict[str, int]) -> str:
        parts = [f"{card}:{count}" for card, count in cards.items() if count > 0]
        return ", ".join(parts) if parts else "Aucune"

    def build_discard_layout(prompt: DiscardPrompt) -> Dict[str, object]:
        panel_width = 360
        row_height = 42
        padding = 16
        rows_count = len(prompt.resource_order)
        panel_height = padding * 2 + rows_count * row_height + 70

        panel_rect = pygame.Rect(40, SCREEN_HEIGHT - panel_height - 40, panel_width, panel_height)

        rows = []
        for idx, resource in enumerate(prompt.resource_order):
            row_top = panel_rect.top + padding + idx * row_height
            label_pos = (panel_rect.left + 16, row_top + 8)
            minus_rect = pygame.Rect(panel_rect.left + 220, row_top + 4, 32, 32)
            plus_rect = pygame.Rect(panel_rect.left + 260, row_top + 4, 32, 32)
            rows.append(
                {
                    "resource": resource,
                    "label_pos": label_pos,
                    "minus_rect": minus_rect,
                    "plus_rect": plus_rect,
                }
            )

        confirm_rect = pygame.Rect(panel_rect.left + 16, panel_rect.bottom - 56, 140, 36)
        reset_rect = pygame.Rect(confirm_rect.right + 12, confirm_rect.top, 140, 36)

        return {
            "panel_rect": panel_rect,
            "rows": rows,
            "confirm_rect": confirm_rect,
            "reset_rect": reset_rect,
        }

    def render_player_panels(panels: Iterable[PlayerPanel]) -> None:
        panel_width = 360
        panel_height = 120
        base_x = SCREEN_WIDTH - panel_width - 20
        base_y = 80

        for idx, panel in enumerate(panels):
            top = base_y + idx * (panel_height + 20)
            bg_color = (70, 110, 140) if panel.is_current_player else (50, 80, 110)
            rect = pygame.Rect(base_x, top, panel_width, panel_height)
            pygame.draw.rect(screen, bg_color, rect, border_radius=10)
            pygame.draw.rect(screen, (20, 40, 60), rect, width=2, border_radius=10)

            name_prefix = "▶ " if panel.is_current_player else ""
            name_text = font.render(f"{name_prefix}{panel.name}", True, (255, 255, 255))
            screen.blit(name_text, (base_x + 16, top + 12))

            vp_text = f"VP: {panel.victory_points}"
            if panel.hidden_victory_points:
                vp_text += f" (+{panel.hidden_victory_points})"
            vp_text += f" → {panel.total_victory_points}"

            badges = []
            if panel.has_longest_road:
                badges.append("Route")
            if panel.has_largest_army:
                badges.append("Armée")
            badge_text = f" | Titres: {', '.join(badges)}" if badges else ""

            status_line = f"{vp_text} | Cartes main: {panel.hand_size}{badge_text}"
            if panel.pending_discard:
                status_line += f" | Défausser: {panel.pending_discard}"

            status_surf = small_font.render(status_line, True, (230, 230, 230))
            screen.blit(status_surf, (base_x + 16, top + 46))

            res_line = f"Ressources: {format_resource_summary(panel.resources)}"
            res_surf = small_font.render(res_line, True, (210, 210, 210))
            screen.blit(res_surf, (base_x + 16, top + 72))

            dev_line = (
                f"Dev: {format_dev_summary(panel.dev_cards)} | Nouvelles: "
                f"{format_dev_summary(panel.new_dev_cards)}"
            )
            dev_surf = small_font.render(dev_line, True, (200, 200, 200))
            screen.blit(dev_surf, (base_x + 16, top + 96))

    def render_discard_panel(prompt: DiscardPrompt, layout: Dict[str, object]) -> None:
        panel_rect: pygame.Rect = layout["panel_rect"]  # type: ignore[assignment]
        pygame.draw.rect(screen, (45, 75, 105), panel_rect, border_radius=12)
        pygame.draw.rect(screen, (20, 40, 60), panel_rect, width=2, border_radius=12)

        title = font.render(f"Défausse — {prompt.player_name}", True, (255, 255, 255))
        screen.blit(title, (panel_rect.left + 16, panel_rect.top + 8))

        remaining_text = small_font.render(
            f"Cartes à défausser: {prompt.remaining}", True, (230, 230, 230)
        )
        screen.blit(remaining_text, (panel_rect.left + 16, panel_rect.top + 36))

        for row in layout["rows"]:  # type: ignore[assignment]
            resource = row["resource"]
            label_pos = row["label_pos"]
            minus_rect: pygame.Rect = row["minus_rect"]
            plus_rect: pygame.Rect = row["plus_rect"]

            available = prompt.hand.get(resource, 0)
            selected = prompt.selection.get(resource, 0)
            label = f"{resource.title()}: {selected}/{available}"
            label_surf = small_font.render(label, True, (210, 210, 210))
            screen.blit(label_surf, label_pos)

            pygame.draw.rect(screen, (70, 110, 140), minus_rect, border_radius=6)
            pygame.draw.rect(screen, (20, 40, 60), minus_rect, width=2, border_radius=6)
            minus_text = small_font.render("-", True, (255, 255, 255))
            screen.blit(minus_text, minus_text.get_rect(center=minus_rect.center))

            pygame.draw.rect(screen, (70, 110, 140), plus_rect, border_radius=6)
            pygame.draw.rect(screen, (20, 40, 60), plus_rect, width=2, border_radius=6)
            plus_text = small_font.render("+", True, (255, 255, 255))
            screen.blit(plus_text, plus_text.get_rect(center=plus_rect.center))

        confirm_rect: pygame.Rect = layout["confirm_rect"]  # type: ignore[assignment]
        reset_rect: pygame.Rect = layout["reset_rect"]  # type: ignore[assignment]

        confirm_color = (100, 180, 120) if prompt.can_confirm else (90, 90, 90)
        pygame.draw.rect(screen, confirm_color, confirm_rect, border_radius=8)
        pygame.draw.rect(screen, (20, 40, 60), confirm_rect, width=2, border_radius=8)
        confirm_label = small_font.render("Valider", True, (0, 0, 0))
        screen.blit(confirm_label, confirm_label.get_rect(center=confirm_rect.center))

        pygame.draw.rect(screen, (160, 120, 70), reset_rect, border_radius=8)
        pygame.draw.rect(screen, (20, 40, 60), reset_rect, width=2, border_radius=8)
        reset_label = small_font.render("Réinitialiser", True, (0, 0, 0))
        screen.blit(reset_label, reset_label.get_rect(center=reset_rect.center))

    running = True
    ui_state = app.get_ui_state()

    while running:
        ui_state_changed = False
        discard_layout: Optional[Dict[str, object]] = (
            build_discard_layout(ui_state.discard_prompt)
            if ui_state.mode == "discard" and ui_state.discard_prompt
            else None
        )

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

                if ui_state.mode == "discard":
                    if event.key == pygame.K_RETURN:
                        if app.confirm_discard_selection():
                            ui_state_changed = True
                    elif event.key == pygame.K_BACKSPACE:
                        if app.reset_discard_selection():
                            ui_state_changed = True
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

                if discard_layout:
                    handled = False
                    for row in discard_layout["rows"]:  # type: ignore[assignment]
                        minus_rect: pygame.Rect = row["minus_rect"]
                        plus_rect: pygame.Rect = row["plus_rect"]
                        resource = row["resource"]
                        if minus_rect.collidepoint(pos):
                            if app.adjust_discard_selection(resource, -1):
                                ui_state_changed = True
                            handled = True
                            break
                        if plus_rect.collidepoint(pos):
                            if app.adjust_discard_selection(resource, 1):
                                ui_state_changed = True
                            handled = True
                            break
                    if handled:
                        continue

                    confirm_rect: pygame.Rect = discard_layout["confirm_rect"]  # type: ignore[assignment]
                    reset_rect: pygame.Rect = discard_layout["reset_rect"]  # type: ignore[assignment]
                    if confirm_rect.collidepoint(pos):
                        if app.confirm_discard_selection():
                            ui_state_changed = True
                        continue
                    if reset_rect.collidepoint(pos):
                        if app.reset_discard_selection():
                            ui_state_changed = True
                        continue

                if ui_state.highlight_tiles:
                    tile_id = app.renderer.get_tile_at_position(pos)
                    if tile_id is not None and app.handle_board_tile_click(tile_id):
                        ui_state_changed = True
                        continue

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

        if ui_state_changed:
            ui_state = app.get_ui_state()
            discard_layout = (
                build_discard_layout(ui_state.discard_prompt)
                if ui_state.mode == "discard" and ui_state.discard_prompt
                else None
            )

        # Rendu principal
        screen.fill(COLOR_BG)
        renderer = app.renderer
        renderer.render_board()
        renderer.render_pieces(app.state)

        if ui_state.highlight_tiles:
            renderer.render_highlighted_tiles(ui_state.highlight_tiles)
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

        # Dernier lancer de dés
        if ui_state.last_dice_roll is not None:
            dice_text = f"Dernier lancer: {ui_state.last_dice_roll}"
        else:
            dice_text = "Dernier lancer: —"

        if not ui_state.dice_rolled_this_turn:
            dice_text += " (à lancer)"

        dice_surf = small_font.render(dice_text, True, (240, 240, 240))
        screen.blit(dice_surf, (SCREEN_WIDTH - 360, 20))

        render_player_panels(ui_state.player_panels)
        if discard_layout and ui_state.discard_prompt:
            render_discard_panel(ui_state.discard_prompt, discard_layout)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
