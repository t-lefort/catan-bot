"""Simple Pygame GUI for testing the bot.

Interface graphique minimaliste pour:
- Visualiser le plateau
- Jouer contre le bot
- Vérifier que les règles fonctionnent correctement
"""

import pygame
import sys
from typing import Optional, Tuple
import numpy as np

from ..core.game_state import GameState
from ..core.board import Board, HexCoord
from ..core.constants import TerrainType


# Couleurs
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
RED = (220, 53, 69)
BLUE = (13, 110, 253)
GREEN = (25, 135, 84)
YELLOW = (255, 193, 7)

# Couleurs des terrains
TERRAIN_COLORS = {
    TerrainType.FOREST: (34, 139, 34),      # Vert foncé
    TerrainType.HILLS: (139, 69, 19),       # Marron
    TerrainType.PASTURE: (144, 238, 144),   # Vert clair
    TerrainType.FIELDS: (255, 215, 0),      # Jaune doré
    TerrainType.MOUNTAINS: (105, 105, 105), # Gris
    TerrainType.DESERT: (244, 164, 96),     # Sable
}

# Couleurs des joueurs
PLAYER_COLORS = [RED, BLUE, GREEN, YELLOW]


class GameWindow:
    """Fenêtre principale du jeu."""

    def __init__(self, width: int = 1200, height: int = 800):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("CatanBot")

        self.clock = pygame.time.Clock()
        self.fps = 60

        # Fonts
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)

        # Game state
        self.game_state: Optional[GameState] = None

        # Paramètres d'affichage du plateau
        self.hex_radius = 50
        self.board_offset_x = 400
        self.board_offset_y = 400

    def start_new_game(self, num_players: int = 4) -> None:
        """Démarre une nouvelle partie."""
        board = Board.create_standard_board(shuffle=True)
        self.game_state = GameState(
            board=board,
            num_players=num_players,
            victory_points_to_win=10,
        )

    def run(self) -> None:
        """Boucle principale du jeu."""
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    self._handle_keypress(event.key)

            self._render()
            self.clock.tick(self.fps)

        pygame.quit()
        sys.exit()

    def _handle_click(self, pos: Tuple[int, int]) -> None:
        """Gère les clics de souris."""
        # TODO: Déterminer quelle action effectuer selon la position
        pass

    def _handle_keypress(self, key: int) -> None:
        """Gère les touches du clavier."""
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        elif key == pygame.K_n:
            # Nouvelle partie
            self.start_new_game()
        elif key == pygame.K_SPACE:
            # Passer le tour / effectuer l'action du bot
            pass

    def _render(self) -> None:
        """Affiche l'état actuel."""
        self.screen.fill(WHITE)

        if self.game_state is None:
            self._render_menu()
        else:
            self._render_game()

        pygame.display.flip()

    def _render_menu(self) -> None:
        """Affiche le menu principal."""
        title = self.font_large.render("CatanBot", True, BLACK)
        title_rect = title.get_rect(center=(self.width // 2, 200))
        self.screen.blit(title, title_rect)

        instruction = self.font_medium.render("Appuyez sur 'N' pour nouvelle partie", True, GRAY)
        instruction_rect = instruction.get_rect(center=(self.width // 2, 300))
        self.screen.blit(instruction, instruction_rect)

    def _render_game(self) -> None:
        """Affiche le jeu en cours."""
        assert self.game_state is not None

        # Afficher le plateau
        self._render_board()

        # Afficher les informations des joueurs
        self._render_player_info()

        # Afficher les contrôles
        self._render_controls()

    def _render_board(self) -> None:
        """Affiche le plateau hexagonal."""
        if self.game_state is None:
            return

        board = self.game_state.board

        for hex_coord, hex_tile in board.hexes.items():
            # Calculer la position à l'écran
            screen_pos = self._hex_to_screen(hex_coord)

            # Dessiner l'hexagone
            color = TERRAIN_COLORS.get(hex_tile.terrain, GRAY)
            self._draw_hexagon(screen_pos, self.hex_radius, color)

            # Dessiner le numéro
            if hex_tile.number is not None:
                number_text = self.font_medium.render(str(hex_tile.number), True, BLACK)
                number_rect = number_text.get_rect(center=screen_pos)

                # Fond blanc pour le numéro
                pygame.draw.circle(self.screen, WHITE, screen_pos, 15)
                self.screen.blit(number_text, number_rect)

            # Dessiner le voleur si présent
            if hex_tile.has_robber:
                pygame.draw.circle(self.screen, BLACK, screen_pos, 10)

    def _render_player_info(self) -> None:
        """Affiche les informations des joueurs."""
        if self.game_state is None:
            return

        y_offset = 50
        for i, player in enumerate(self.game_state.players):
            color = PLAYER_COLORS[i]

            # Nom et score
            player_text = f"Joueur {i + 1}: {player.victory_points()} PV"
            text = self.font_medium.render(player_text, True, color)
            self.screen.blit(text, (20, y_offset))

            # Ressources
            resources_text = f"Ressources: {player.total_resources()}"
            text = self.font_small.render(resources_text, True, GRAY)
            self.screen.blit(text, (20, y_offset + 25))

            # Constructions
            buildings_text = (
                f"Colonies: {len(player.settlements)}, "
                f"Villes: {len(player.cities)}, "
                f"Routes: {len(player.roads)}"
            )
            text = self.font_small.render(buildings_text, True, GRAY)
            self.screen.blit(text, (20, y_offset + 45))

            y_offset += 90

    def _render_controls(self) -> None:
        """Affiche les contrôles."""
        controls = [
            "ESC: Quitter",
            "N: Nouvelle partie",
            "SPACE: Tour suivant",
        ]

        y_offset = self.height - 100
        for control in controls:
            text = self.font_small.render(control, True, GRAY)
            self.screen.blit(text, (20, y_offset))
            y_offset += 20

    def _hex_to_screen(self, hex_coord: HexCoord) -> Tuple[int, int]:
        """Convertit des coordonnées hexagonales en coordonnées écran."""
        x = self.hex_radius * (3/2 * hex_coord.q)
        y = self.hex_radius * (np.sqrt(3)/2 * hex_coord.q + np.sqrt(3) * hex_coord.r)

        screen_x = int(x + self.board_offset_x)
        screen_y = int(y + self.board_offset_y)

        return (screen_x, screen_y)

    def _draw_hexagon(
        self, center: Tuple[int, int], radius: int, color: Tuple[int, int, int]
    ) -> None:
        """Dessine un hexagone."""
        points = []
        for i in range(6):
            angle = np.pi / 3 * i
            x = center[0] + radius * np.cos(angle)
            y = center[1] + radius * np.sin(angle)
            points.append((x, y))

        pygame.draw.polygon(self.screen, color, points)
        pygame.draw.polygon(self.screen, BLACK, points, 2)  # Bordure


def main() -> None:
    """Point d'entrée pour lancer la GUI."""
    window = GameWindow()
    window.start_new_game()
    window.run()


if __name__ == "__main__":
    main()
