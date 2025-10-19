#!/usr/bin/env python3
"""Demo GUI - Test visuel du rendu pygame (GUI-002).

Ce script démontre le rendu du plateau et des pièces.
Lance une fenêtre pygame affichant le plateau standard avec quelques
pièces de test pour validation visuelle.

Usage:
    python3 demo_gui.py
"""

import pygame
import sys

from catan.engine.board import Board
from catan.engine.state import GameState
from catan.engine.actions import PlaceSettlement, PlaceRoad, RollDice, BuildCity
from catan.gui.renderer import BoardRenderer, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BG


def setup_demo_state() -> GameState:
    """Create a game state with some pieces for visual testing.

    Plays through the setup phase using legal actions, then rolls dice
    to enter PLAY phase. This demonstrates the board rendering with
    settlements and roads placed.
    """
    state = GameState.new_1v1_game(
        player_names=["Bleu", "Orange"], seed=42
    )

    # Complete setup phase using legal actions
    # This will place 2 settlements + 2 roads per player
    setup_moves = [
        # Round 1: P0, P1
        # Round 2: P1, P0 (reverse order)
        0, 1, 2, 3, 4, 5, 6, 7
    ]

    for _ in setup_moves:
        legal = state.legal_actions()
        if legal:
            # Take first legal action (settlement or road)
            state = state.apply_action(legal[0])

    # Should now be in PLAY phase - roll dice
    if state.turn_subphase.value == "MAIN":
        legal = state.legal_actions()
        roll_actions = [a for a in legal if isinstance(a, RollDice)]
        if roll_actions:
            state = state.apply_action(roll_actions[0])

        # Try to build additional pieces if resources allow
        legal = state.legal_actions()
        build_actions = [
            a for a in legal
            if isinstance(a, (PlaceRoad, PlaceSettlement, BuildCity))
        ]

        # Apply a few legal build actions if available
        for action in build_actions[:3]:
            if state.is_action_legal(action):
                state = state.apply_action(action)

    return state


def main() -> int:
    """Run the GUI demo."""
    pygame.init()

    # Create display
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("CatanBot - Demo GUI (GUI-002)")

    # Create board and renderer
    board = Board.standard()
    renderer = BoardRenderer(screen, board)

    # Setup demo state with some pieces
    state = setup_demo_state()

    # Font for instructions
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 16)

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

        # Clear screen
        screen.fill(COLOR_BG)

        # Render board and pieces
        renderer.render_board()
        renderer.render_pieces(state)

        # Draw instructions
        instructions = [
            "Demo GUI - CatanBot (GUI-002)",
            "Plateau standard avec pièces de test",
            "",
            "Appuyez sur ESC ou Q pour quitter",
        ]

        y_offset = 10
        for line in instructions:
            text = font.render(line, True, (255, 255, 255))
            screen.blit(text, (10, y_offset))
            y_offset += 20

        # Update display
        pygame.display.flip()
        clock.tick(60)  # 60 FPS

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
