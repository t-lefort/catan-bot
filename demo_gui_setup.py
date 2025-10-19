#!/usr/bin/env python3
"""Demo GUI Setup - Test interactif de la phase de placement (GUI-003).

Ce script permet de tester la phase de setup avec interaction utilisateur:
- Affichage des positions légales (surbrillance verte)
- Clic sur sommets pour placer colonies
- Clic sur arêtes pour placer routes
- Ordre serpent automatique (J0→J1 puis J1→J0)
- Instructions contextuelles

Usage:
    python3 demo_gui_setup.py
"""

import pygame
import sys

from catan.engine.board import Board
from catan.app.game_service import GameService
from catan.gui.renderer import BoardRenderer, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BG
from catan.gui.setup_controller import SetupController


def main() -> int:
    """Run the interactive setup demo."""
    pygame.init()

    # Create display
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("CatanBot - Demo Setup Interactif (GUI-003)")

    # Create game service and start new game
    game_service = GameService()
    game_service.start_new_game(player_names=["Bleu", "Orange"], seed=42)

    # Create board and renderer
    board = Board.standard()
    renderer = BoardRenderer(screen, board)

    # Create setup controller
    controller = SetupController(game_service, screen)

    # Font for instructions
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 18, bold=True)
    small_font = pygame.font.SysFont("Arial", 14)

    # Main loop
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Get click position
                    click_pos = event.pos

                    # Try vertex click first
                    vertex_id = renderer.get_vertex_at_position(click_pos)
                    if vertex_id is not None:
                        controller.handle_vertex_click(vertex_id)
                        continue

                    # Try edge click
                    edge_id = renderer.get_edge_at_position(click_pos)
                    if edge_id is not None:
                        controller.handle_edge_click(edge_id)

        # Clear screen
        screen.fill(COLOR_BG)

        # Render board and pieces
        renderer.render_board()
        renderer.render_pieces(controller.state)

        # Render highlighted positions (if still in setup)
        if not controller.is_setup_complete():
            legal_vertices = controller.get_legal_settlement_vertices()
            legal_edges = controller.get_legal_road_edges()

            renderer.render_highlighted_vertices(legal_vertices)
            renderer.render_highlighted_edges(legal_edges)

            # Draw instructions
            instructions = controller.get_instructions()
            text = font.render(instructions, True, (255, 255, 255))
            # Draw with black background for readability
            text_rect = text.get_rect(topleft=(10, 10))
            bg_rect = text_rect.inflate(20, 10)
            pygame.draw.rect(screen, (0, 0, 0), bg_rect)
            screen.blit(text, text_rect)

            # Draw help text
            help_lines = [
                "Cliquez sur un sommet vert pour placer une colonie",
                "Cliquez sur une arête verte pour placer une route",
                "ESC ou Q pour quitter",
            ]
            y_offset = 50
            for line in help_lines:
                text = small_font.render(line, True, (200, 200, 200))
                text_rect = text.get_rect(topleft=(10, y_offset))
                bg_rect = text_rect.inflate(10, 5)
                pygame.draw.rect(screen, (0, 0, 0), bg_rect)
                screen.blit(text, text_rect)
                y_offset += 25
        else:
            # Setup complete
            message = "Phase de setup terminée ! Appuyez sur ESC pour quitter."
            text = font.render(message, True, (100, 255, 100))
            text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, 50))
            bg_rect = text_rect.inflate(20, 10)
            pygame.draw.rect(screen, (0, 0, 0), bg_rect)
            screen.blit(text, text_rect)

            # Show player resources (from second placements)
            y_offset = 100
            for player_id, player in enumerate(controller.state.players):
                player_text = f"{player.name}: "
                resources = []
                for res, count in player.resources.items():
                    if count > 0:
                        resources.append(f"{res}={count}")
                if resources:
                    player_text += ", ".join(resources)
                else:
                    player_text += "Aucune ressource"

                color = (30, 100, 200) if player_id == 0 else (255, 140, 50)
                text = small_font.render(player_text, True, color)
                text_rect = text.get_rect(topleft=(10, y_offset))
                bg_rect = text_rect.inflate(10, 5)
                pygame.draw.rect(screen, (0, 0, 0), bg_rect)
                screen.blit(text, text_rect)
                y_offset += 25

        # Update display
        pygame.display.flip()
        clock.tick(60)  # 60 FPS

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
