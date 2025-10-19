"""BoardRenderer — rendu pygame du plateau et pièces (GUI-002).

Responsabilités:
- Calculer les coordonnées écran des hexagones depuis Board
- Dessiner les tuiles, numéros de dés, ports
- Dessiner routes, colonies, villes depuis GameState
- Gérer les surbrillances contextuelles (positions légales)

Conventions visuelles (conforme docs/gui-h2h.md):
- Hex pointy-top avec orientation standard
- Ressources: couleurs codées (GRAIN=jaune, ORE=gris, etc.)
- Ports: icônes simples sur arêtes concernées
- Pièces: routes=lignes épaisses, colonies=cercles, villes=carrés
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple, Optional

import pygame

from catan.engine.board import Board, Tile
from catan.engine.state import GameState


# Constantes écran
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800

# Constantes plateau
HEX_SIZE = 50  # rayon de l'hexagone en pixels
BOARD_OFFSET_X = 400  # décalage du plateau pour laisser de la place au HUD
BOARD_OFFSET_Y = 350  # centrage vertical

# Couleurs (palette sobre)
COLOR_BG = (30, 60, 90)
COLOR_SEA = (50, 100, 150)
COLOR_DESERT = (220, 190, 130)
COLOR_ORE = (120, 120, 120)
COLOR_GRAIN = (240, 220, 100)
COLOR_WOOL = (180, 255, 180)
COLOR_BRICK = (200, 80, 50)
COLOR_LUMBER = (80, 150, 60)
COLOR_ROBBER = (50, 50, 50)
COLOR_NUMBER = (255, 255, 255)
COLOR_NUMBER_RED = (255, 100, 100)

# Couleurs joueurs
COLOR_PLAYER_0 = (30, 100, 200)  # Bleu
COLOR_PLAYER_1 = (255, 140, 50)  # Orange

# Couleurs pièces
COLOR_ROAD = (255, 255, 255)
COLOR_SETTLEMENT = (255, 255, 255)
COLOR_CITY = (255, 255, 255)

# Tailles pièces
ROAD_WIDTH = 6
SETTLEMENT_RADIUS = 10
CITY_SIZE = 16


class BoardRenderer:
    """Rendu du plateau et des pièces."""

    # Map ressource -> couleur
    _RESOURCE_COLORS: Dict[str, Tuple[int, int, int]] = {
        "DESERT": COLOR_DESERT,
        "ORE": COLOR_ORE,
        "GRAIN": COLOR_GRAIN,
        "WOOL": COLOR_WOOL,
        "BRICK": COLOR_BRICK,
        "LUMBER": COLOR_LUMBER,
    }

    # Map player_id -> couleur
    _PLAYER_COLORS: List[Tuple[int, int, int]] = [COLOR_PLAYER_0, COLOR_PLAYER_1]

    def __init__(self, screen: pygame.Surface, board: Board) -> None:
        """Initialize renderer with pygame surface and game board.

        Args:
            screen: pygame surface to draw on
            board: game board to render
        """
        self.screen = screen
        self.board = board

        # Precompute hex coordinates for all tiles
        self._hex_coords: Dict[int, List[Tuple[int, int]]] = {}
        self._vertex_screen_coords: Dict[int, Tuple[int, int]] = {}
        self._precompute_coordinates()

        # Font for numbers (lazy init on first render)
        self._font: Optional[pygame.font.Font] = None

    def _precompute_coordinates(self) -> None:
        """Precompute screen coordinates for all hexagons and vertices."""
        # Hex vertices in pointy-top orientation (starting from top)
        hex_angles = [math.radians(30 + 60 * i) for i in range(6)]

        for tile_id, tile in self.board.tiles.items():
            # Convert cube coordinates to pixel position
            # Using axial coordinates derived from cube
            q = tile.cube.x
            r = tile.cube.z

            # Pointy-top hex layout
            x = HEX_SIZE * math.sqrt(3) * (q + r / 2.0)
            y = HEX_SIZE * 1.5 * r

            # Apply screen offset
            center_x = int(BOARD_OFFSET_X + x)
            center_y = int(BOARD_OFFSET_Y + y)

            # Compute 6 vertices
            vertices = []
            for angle in hex_angles:
                vx = int(center_x + HEX_SIZE * math.cos(angle))
                vy = int(center_y + HEX_SIZE * math.sin(angle))
                vertices.append((vx, vy))

            self._hex_coords[tile_id] = vertices

        # Map logical vertices to screen coordinates
        for vertex_id, vertex in self.board.vertices.items():
            # vertex.position contains (x, y) in logical board space
            # Scale to screen coordinates
            x = vertex.position[0] * HEX_SIZE
            y = vertex.position[1] * HEX_SIZE

            screen_x = int(BOARD_OFFSET_X + x * math.sqrt(3) / 2.0)
            screen_y = int(BOARD_OFFSET_Y + y)

            self._vertex_screen_coords[vertex_id] = (screen_x, screen_y)

    def _ensure_font(self) -> pygame.font.Font:
        """Lazy init font."""
        if self._font is None:
            pygame.font.init()
            self._font = pygame.font.SysFont("Arial", 18, bold=True)
        return self._font

    def render_board(self) -> None:
        """Render the board: hexes, numbers, ports."""
        for tile_id, tile in self.board.tiles.items():
            vertices = self._hex_coords[tile_id]

            # Fill hex with resource color
            color = self._RESOURCE_COLORS.get(tile.resource, COLOR_DESERT)
            pygame.draw.polygon(self.screen, color, vertices)

            # Draw border
            pygame.draw.polygon(self.screen, (0, 0, 0), vertices, width=2)

            # Draw number (if not desert)
            if tile.pip is not None:
                center_x = sum(v[0] for v in vertices) // 6
                center_y = sum(v[1] for v in vertices) // 6

                # Red for 6 and 8 (high probability)
                number_color = COLOR_NUMBER_RED if tile.pip in (6, 8) else COLOR_NUMBER
                font = self._ensure_font()
                text = font.render(str(tile.pip), True, number_color)
                text_rect = text.get_rect(center=(center_x, center_y))
                self.screen.blit(text, text_rect)

            # Draw robber if present
            if tile.has_robber:
                center_x = sum(v[0] for v in vertices) // 6
                center_y = sum(v[1] for v in vertices) // 6
                pygame.draw.circle(
                    self.screen, COLOR_ROBBER, (center_x, center_y), 15, width=0
                )
                # Robber outline
                pygame.draw.circle(
                    self.screen, (200, 200, 200), (center_x, center_y), 15, width=2
                )

        # Draw ports (simple markers on edges)
        self._render_ports()

    def _render_ports(self) -> None:
        """Draw port markers on corresponding edges."""
        for port in self.board.ports:
            # Get the two vertices of the port
            v1_id, v2_id = port.vertices
            if v1_id not in self._vertex_screen_coords or v2_id not in self._vertex_screen_coords:
                continue

            v1_pos = self._vertex_screen_coords[v1_id]
            v2_pos = self._vertex_screen_coords[v2_id]

            # Midpoint
            mid_x = (v1_pos[0] + v2_pos[0]) // 2
            mid_y = (v1_pos[1] + v2_pos[1]) // 2

            # Draw small circle for port marker
            port_color = (255, 255, 255)
            pygame.draw.circle(self.screen, port_color, (mid_x, mid_y), 8, width=2)

            # Draw port type (simplified)
            font = self._ensure_font()
            label = "?" if port.kind == "ANY" else port.kind[0]  # First letter
            text = font.render(label, True, (255, 255, 255))
            text_rect = text.get_rect(center=(mid_x, mid_y))
            self.screen.blit(text, text_rect)

    def render_pieces(self, state: GameState) -> None:
        """Render roads, settlements, and cities from game state.

        Args:
            state: current game state
        """
        # Render roads
        for player_id, player in enumerate(state.players):
            color = self._PLAYER_COLORS[player_id]

            for edge_id in player.roads:
                self._draw_road(edge_id, color)

            for vertex_id in player.settlements:
                self._draw_settlement(vertex_id, color)

            for vertex_id in player.cities:
                self._draw_city(vertex_id, color)

    def _draw_road(self, edge_id: int, color: Tuple[int, int, int]) -> None:
        """Draw a road on the specified edge."""
        edge = self.board.edges.get(edge_id)
        if edge is None:
            return

        v1_id, v2_id = edge.vertices
        if v1_id not in self._vertex_screen_coords or v2_id not in self._vertex_screen_coords:
            return

        v1_pos = self._vertex_screen_coords[v1_id]
        v2_pos = self._vertex_screen_coords[v2_id]

        pygame.draw.line(self.screen, color, v1_pos, v2_pos, width=ROAD_WIDTH)

    def _draw_settlement(self, vertex_id: int, color: Tuple[int, int, int]) -> None:
        """Draw a settlement at the specified vertex."""
        if vertex_id not in self._vertex_screen_coords:
            return

        pos = self._vertex_screen_coords[vertex_id]
        pygame.draw.circle(self.screen, color, pos, SETTLEMENT_RADIUS, width=0)
        pygame.draw.circle(self.screen, (0, 0, 0), pos, SETTLEMENT_RADIUS, width=2)

    def _draw_city(self, vertex_id: int, color: Tuple[int, int, int]) -> None:
        """Draw a city at the specified vertex."""
        if vertex_id not in self._vertex_screen_coords:
            return

        pos = self._vertex_screen_coords[vertex_id]

        # Draw as a square
        rect = pygame.Rect(0, 0, CITY_SIZE, CITY_SIZE)
        rect.center = pos
        pygame.draw.rect(self.screen, color, rect, width=0)
        pygame.draw.rect(self.screen, (0, 0, 0), rect, width=2)


__all__ = ["BoardRenderer", "SCREEN_WIDTH", "SCREEN_HEIGHT"]
