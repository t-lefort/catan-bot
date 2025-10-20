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
from typing import Dict, List, Tuple, Optional, Set

import pygame

from catan.engine.board import Board, Tile
from catan.engine.state import GameState


# Constantes écran
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800

# Constantes plateau
HEX_SIZE = 50  # rayon de l'hexagone en pixels
BOARD_OFFSET_X = 480  # décalage du plateau pour laisser de la place au HUD
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
ROBBER_OFFSET_Y = 22

# Couleurs joueurs
COLOR_PLAYER_0 = (30, 100, 200)  # Bleu
COLOR_PLAYER_1 = (255, 140, 50)  # Orange

# Couleurs pièces
COLOR_ROAD = (255, 255, 255)
COLOR_SETTLEMENT = (255, 255, 255)
COLOR_CITY = (255, 255, 255)

# Couleurs pour la surbrillance (setup/interactions)
COLOR_HIGHLIGHT_VERTEX = (100, 255, 100, 180)  # Vert semi-transparent
COLOR_HIGHLIGHT_EDGE = (100, 255, 100, 180)    # Vert semi-transparent
COLOR_HIGHLIGHT_TILE = (255, 255, 120, 90)     # Jaune clair semi-transparent

# Tailles pièces
ROAD_WIDTH = 6
SETTLEMENT_RADIUS = 10
CITY_SIZE = 16

# Tailles pour détection de clics
VERTEX_CLICK_RADIUS = 15  # Rayon de détection pour les clics sur sommets
EDGE_CLICK_DISTANCE = 10  # Distance max pour détecter un clic sur une arête


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

    def update_board(self, board: Board) -> None:
        """Met à jour le plateau rendu (utile pour déplacement du voleur)."""
        self.board = board

    def _precompute_coordinates(self) -> None:
        """Precompute screen coordinates for all hexagons and vertices.

        The Board provides logical coordinates for vertices. We need to:
        1. Scale them to screen space
        2. Apply the screen offset

        The Board uses:
        - axial_to_pixel: x = sqrt(3) * (q + r/2), y = 1.5 * r
        - vertex offsets: (cos(30°+60°k), sin(30°+60°k)) for k in [0..5]
        """
        # First, map all logical vertex coordinates to screen coordinates
        # The Board already computed vertex.position in logical space
        for vertex_id, vertex in self.board.vertices.items():
            # vertex.position is (x, y) in logical hex coordinate space
            # where each hex has unit size
            logical_x, logical_y = vertex.position

            # Scale by HEX_SIZE and apply offset
            screen_x = int(BOARD_OFFSET_X + logical_x * HEX_SIZE)
            screen_y = int(BOARD_OFFSET_Y + logical_y * HEX_SIZE)

            self._vertex_screen_coords[vertex_id] = (screen_x, screen_y)

        # Now compute hex polygon coordinates using the actual vertex positions
        # This ensures hexagons align perfectly with vertices
        for tile_id, tile in self.board.tiles.items():
            # Get the 6 vertices of this tile (in order)
            vertex_ids = tile.vertices

            # Get screen coordinates for these vertices
            vertices = []
            for vid in vertex_ids:
                if vid in self._vertex_screen_coords:
                    vertices.append(self._vertex_screen_coords[vid])

            self._hex_coords[tile_id] = vertices

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
            center_x = sum(v[0] for v in vertices) // 6
            center_y = sum(v[1] for v in vertices) // 6

            # Fill hex with resource color
            color = self._RESOURCE_COLORS.get(tile.resource, COLOR_DESERT)
            pygame.draw.polygon(self.screen, color, vertices)

            # Draw border
            pygame.draw.polygon(self.screen, (0, 0, 0), vertices, width=2)

            # Draw number (if not desert)
            if tile.pip is not None:
                # Draw white circle background for better readability
                pygame.draw.circle(self.screen, (255, 255, 255), (center_x, center_y), 16, width=0)
                pygame.draw.circle(self.screen, (0, 0, 0), (center_x, center_y), 16, width=2)

                # All numbers in black for better contrast
                font = self._ensure_font()
                text = font.render(str(tile.pip), True, (0, 0, 0))
                text_rect = text.get_rect(center=(center_x, center_y))
                self.screen.blit(text, text_rect)

            # Draw robber if present
            if tile.has_robber:
                robber_center = (center_x, center_y + ROBBER_OFFSET_Y)
                pygame.draw.circle(
                    self.screen, COLOR_ROBBER, robber_center, 15, width=0
                )
                # Robber outline
                pygame.draw.circle(
                    self.screen, (200, 200, 200), robber_center, 15, width=2
                )

        # Draw ports (simple markers on edges)
        self._render_ports()

    def _render_ports(self) -> None:
        """Draw port markers on corresponding edges.

        Ports are displayed as larger circles with resource type indicators,
        positioned slightly outside the edge to be more visible.
        """
        PORT_RADIUS = 18  # Larger radius for better visibility
        PORT_OFFSET_FACTOR = 1.3  # Push port markers outward from center

        # Map port types to colors for better recognition
        PORT_COLORS = {
            "ANY": (200, 200, 200),      # Gray for 3:1
            "BRICK": (200, 80, 50),      # Brick red
            "LUMBER": (80, 150, 60),     # Green
            "WOOL": (180, 255, 180),     # Light green
            "GRAIN": (240, 220, 100),    # Yellow
            "ORE": (120, 120, 120),      # Dark gray
        }

        for port in self.board.ports:
            # Get the two vertices of the port
            v1_id, v2_id = port.vertices
            if v1_id not in self._vertex_screen_coords or v2_id not in self._vertex_screen_coords:
                continue

            v1_pos = self._vertex_screen_coords[v1_id]
            v2_pos = self._vertex_screen_coords[v2_id]

            # Calculate midpoint of the edge
            edge_mid_x = (v1_pos[0] + v2_pos[0]) / 2
            edge_mid_y = (v1_pos[1] + v2_pos[1]) / 2

            # Find the center of the board (approximate)
            board_center_x = BOARD_OFFSET_X
            board_center_y = BOARD_OFFSET_Y

            # Vector from board center to edge midpoint
            dx = edge_mid_x - board_center_x
            dy = edge_mid_y - board_center_y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 0:
                # Normalize and push outward
                dx /= dist
                dy /= dist

                # Position port marker further out
                port_x = int(edge_mid_x + dx * HEX_SIZE * 0.4)
                port_y = int(edge_mid_y + dy * HEX_SIZE * 0.4)
            else:
                # Fallback to edge midpoint
                port_x = int(edge_mid_x)
                port_y = int(edge_mid_y)

            # Draw port circle with resource-specific color
            port_color = PORT_COLORS.get(port.kind, (255, 255, 255))
            pygame.draw.circle(self.screen, port_color, (port_x, port_y), PORT_RADIUS, width=0)
            pygame.draw.circle(self.screen, (0, 0, 0), (port_x, port_y), PORT_RADIUS, width=3)

            # Draw port ratio text
            font = self._ensure_font()
            if port.kind == "ANY":
                label = "3:1"
            else:
                label = f"2:1"

            text = font.render(label, True, (0, 0, 0))
            text_rect = text.get_rect(center=(port_x, port_y - 2))
            self.screen.blit(text, text_rect)

            # Draw small resource indicator for specific ports
            if port.kind != "ANY":
                small_font = pygame.font.SysFont("Arial", 10, bold=True)
                res_text = small_font.render(port.kind[0], True, (0, 0, 0))
                res_rect = res_text.get_rect(center=(port_x, port_y + 6))
                self.screen.blit(res_text, res_rect)

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

    def render_highlighted_vertices(self, vertex_ids: Set[int]) -> None:
        """Render highlighted vertices (for legal settlement placements).

        Args:
            vertex_ids: Set of vertex IDs to highlight
        """
        for vertex_id in vertex_ids:
            if vertex_id not in self._vertex_screen_coords:
                continue

            pos = self._vertex_screen_coords[vertex_id]

            # Draw semi-transparent circle
            # Create a temporary surface with alpha
            size = SETTLEMENT_RADIUS * 3
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(
                surf,
                COLOR_HIGHLIGHT_VERTEX,
                (size // 2, size // 2),
                SETTLEMENT_RADIUS + 5
            )
            self.screen.blit(surf, (pos[0] - size // 2, pos[1] - size // 2))

    def render_highlighted_edges(self, edge_ids: Set[int]) -> None:
        """Render highlighted edges (for legal road placements).

        Args:
            edge_ids: Set of edge IDs to highlight
        """
        for edge_id in edge_ids:
            edge = self.board.edges.get(edge_id)
            if edge is None:
                continue

            v1_id, v2_id = edge.vertices
            if v1_id not in self._vertex_screen_coords or v2_id not in self._vertex_screen_coords:
                continue

            v1_pos = self._vertex_screen_coords[v1_id]
            v2_pos = self._vertex_screen_coords[v2_id]

            # Draw thicker semi-transparent line
            pygame.draw.line(
                self.screen,
                (100, 255, 100),  # Bright green
                v1_pos,
                v2_pos,
                width=ROAD_WIDTH + 4
            )

    def get_vertex_at_position(self, pos: Tuple[int, int]) -> Optional[int]:
        """Find vertex ID at given screen position.

        Args:
            pos: (x, y) screen coordinates

        Returns:
            Vertex ID if click is near a vertex, None otherwise
        """
        click_x, click_y = pos

        for vertex_id, vertex_pos in self._vertex_screen_coords.items():
            vx, vy = vertex_pos
            distance = math.sqrt((click_x - vx) ** 2 + (click_y - vy) ** 2)

            if distance <= VERTEX_CLICK_RADIUS:
                return vertex_id

        return None

    def get_tile_at_position(self, pos: Tuple[float, float]) -> Optional[int]:
        """Return the tile ID containing the given position, if any."""

        x, y = pos

        for tile_id, vertices in self._hex_coords.items():
            if self._point_in_polygon(x, y, vertices):
                return tile_id

        return None

    def render_highlighted_tiles(self, tile_ids: Set[int]) -> None:
        """Render highlighted tiles (e.g. for robber selection)."""

        if not tile_ids:
            return

        for tile_id in tile_ids:
            vertices = self._hex_coords.get(tile_id)
            if not vertices:
                continue

            min_x = min(v[0] for v in vertices)
            min_y = min(v[1] for v in vertices)
            max_x = max(v[0] for v in vertices)
            max_y = max(v[1] for v in vertices)

            width = int(max_x - min_x) + 1
            height = int(max_y - min_y) + 1
            if width <= 0 or height <= 0:
                continue

            surf = pygame.Surface((width, height), pygame.SRCALPHA)
            local_vertices = [(vx - min_x, vy - min_y) for vx, vy in vertices]
            pygame.draw.polygon(surf, COLOR_HIGHLIGHT_TILE, local_vertices)
            self.screen.blit(surf, (min_x, min_y))

    @staticmethod
    def _point_in_polygon(x: float, y: float, vertices: List[Tuple[int, int]]) -> bool:
        """Return True if point is inside polygon defined by vertices."""

        inside = False
        n = len(vertices)
        if n < 3:
            return False

        j = n - 1
        for i in range(n):
            xi, yi = vertices[i]
            xj, yj = vertices[j]

            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i

        return inside

    def get_edge_at_position(self, pos: Tuple[int, int]) -> Optional[int]:
        """Find edge ID at given screen position.

        Args:
            pos: (x, y) screen coordinates

        Returns:
            Edge ID if click is near an edge, None otherwise
        """
        click_x, click_y = pos

        for edge_id, edge in self.board.edges.items():
            v1_id, v2_id = edge.vertices
            if v1_id not in self._vertex_screen_coords or v2_id not in self._vertex_screen_coords:
                continue

            v1_pos = self._vertex_screen_coords[v1_id]
            v2_pos = self._vertex_screen_coords[v2_id]

            # Calculate distance from point to line segment
            distance = self._point_to_segment_distance(
                (click_x, click_y), v1_pos, v2_pos
            )

            if distance <= EDGE_CLICK_DISTANCE:
                return edge_id

        return None

    def _point_to_segment_distance(
        self,
        point: Tuple[int, int],
        seg_a: Tuple[int, int],
        seg_b: Tuple[int, int]
    ) -> float:
        """Calculate distance from point to line segment.

        Args:
            point: (x, y) coordinates of point
            seg_a: (x, y) coordinates of segment start
            seg_b: (x, y) coordinates of segment end

        Returns:
            Distance from point to segment
        """
        px, py = point
        ax, ay = seg_a
        bx, by = seg_b

        # Vector from A to B
        abx = bx - ax
        aby = by - ay

        # Vector from A to P
        apx = px - ax
        apy = py - ay

        # Squared length of AB
        ab_squared = abx * abx + aby * aby

        if ab_squared == 0:
            # A and B are the same point
            return math.sqrt(apx * apx + apy * apy)

        # Project AP onto AB, computing parameterized position t
        t = max(0, min(1, (apx * abx + apy * aby) / ab_squared))

        # Compute projection point
        proj_x = ax + t * abx
        proj_y = ay + t * aby

        # Distance from P to projection
        dx = px - proj_x
        dy = py - proj_y

        return math.sqrt(dx * dx + dy * dy)


__all__ = ["BoardRenderer", "SCREEN_WIDTH", "SCREEN_HEIGHT"]
