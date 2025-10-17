"""Fenêtre principale du jeu - Version simplifiée et fonctionnelle.

Interface graphique pour visualiser et jouer à Catan.
"""

import pygame
import sys
import random
from typing import Optional, Tuple
import math

from ..core.game_state import GameState, GamePhase, TurnPhase
from ..core.board import (
    Board, Coordinate, NodeDirection, EdgeDirection,
    get_node_id, get_edge_id, get_edge_endpoints, get_tiles_touching_node,
)
from ..core.player import PlayerState
from ..core.constants import (
    TerrainType, ResourceType, BuildingType,
    BUILDING_COSTS, DEV_CARD_COST
)
from ..core.actions import (
    BuildSettlementAction,
    BuildRoadAction,
    BuildCityAction,
    BuyDevCardAction,
    MoveRobberAction,
)


# Couleurs
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (200, 200, 200)
RED = (220, 53, 69)
BLUE = (13, 110, 253)
GREEN = (25, 135, 84)
YELLOW = (255, 193, 7)

# Couleurs des terrains
TERRAIN_COLORS = {
    TerrainType.FOREST: (34, 139, 34),
    TerrainType.HILLS: (139, 69, 19),
    TerrainType.PASTURE: (144, 238, 144),
    TerrainType.FIELDS: (255, 215, 0),
    TerrainType.MOUNTAINS: (105, 105, 105),
    TerrainType.DESERT: (244, 164, 96),
}

PLAYER_COLORS = [RED, BLUE, GREEN, YELLOW]


class GameWindow:
    """Fenêtre principale du jeu."""

    def __init__(self, width: int = 1400, height: int = 900):
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

        # Paramètres d'affichage
        self.hex_radius = 45
        self.board_offset_x = 700
        self.board_offset_y = 450

        # UI state
        self.action_mode: Optional[str] = None
        self.hover_node: Optional[int] = None
        self.hover_edge: Optional[int] = None

        # Dice
        self.dice_values: Optional[Tuple[int, int]] = None
        self.show_dice = False

        # Messages
        self.message = ""

        # Cache pour les positions
        self._node_cache = {}
        self.action_button_rects: dict[str, pygame.Rect] = {}

    def start_new_game(self, num_players: int = 2) -> None:
        """Démarre une nouvelle partie."""
        board = Board.create_standard_board(shuffle=True)
        players = [PlayerState(player_id=i) for i in range(num_players)]
        dev_deck = GameState.create_initial_dev_card_deck()

        self.game_state = GameState(
            board=board,
            num_players=num_players,
            victory_points_to_win=15,
            players=players,
            dev_card_deck=dev_deck,
        )

        self.game_state.ports = GameState.create_default_ports()
        self.action_mode = None
        self.dice_values = None
        self.show_dice = False
        self._node_cache = {}
        self._update_message()

    def _update_message(self) -> None:
        """Met à jour le message."""
        if not self.game_state:
            return

        pid = self.game_state.current_player_idx + 1
        if self.game_state.game_phase == GamePhase.SETUP:
            if self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed:
                self.message = f"Joueur {pid}: Placez une colonie"
            else:
                self.message = f"Joueur {pid}: Placez une route adjacente"
        elif self.game_state.game_phase == GamePhase.MAIN_GAME:
            if not self.show_dice:
                self.message = f"Joueur {pid}: Lancez les dés"
            else:
                self.message = f"Joueur {pid}: Construisez ou terminez (ESPACE)"
        elif self.game_state.game_phase == GamePhase.GAME_OVER:
            if self.game_state.winner is not None:
                self.message = f"Joueur {self.game_state.winner + 1} a gagné!"

    def run(self) -> None:
        """Boucle principale."""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_motion(event.pos)

            self._render()
            self.clock.tick(self.fps)

        pygame.quit()
        sys.exit()

    def _handle_key(self, key: int) -> None:
        """Gère les touches."""
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        elif key == pygame.K_n:
            self.start_new_game()
        elif key == pygame.K_SPACE:
            if (self.game_state and
                self.game_state.game_phase == GamePhase.MAIN_GAME and
                self.show_dice and self.action_mode != "move_robber"):
                self._end_turn()

    def _handle_click(self, pos: Tuple[int, int]) -> None:
        """Gère les clics."""
        if not self.game_state:
            return

        # Bouton dés
        if (self.game_state.game_phase == GamePhase.MAIN_GAME and
            not self.show_dice and self.action_mode is None):
            dice_rect = pygame.Rect(self.width - 200, 50, 150, 60)
            if dice_rect.collidepoint(pos):
                self._roll_dice()
                return

        # Boutons d'action du panneau
        for action_key, rect in self.action_button_rects.items():
            if rect.collidepoint(pos):
                self._handle_action_button(action_key)
                return

        # Placement
        if self.game_state.game_phase == GamePhase.SETUP:
            self._handle_setup_click(pos)
        elif self.action_mode:
            self._handle_action_click(pos)

    def _handle_setup_click(self, pos: Tuple[int, int]) -> None:
        """Gère les clics en phase setup."""
        if self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed:
            # Placer colonie
            node_id = self._get_node_at_pos(pos)
            if node_id and self.game_state.can_place_settlement(node_id, self.game_state.current_player_idx):
                self.game_state = self.game_state.apply_action(BuildSettlementAction(node_id))
                self._update_message()
        else:
            # Placer route
            edge_id = self._get_edge_at_pos(pos)
            if edge_id and self.game_state.can_place_road(edge_id, self.game_state.current_player_idx):
                self.game_state = self.game_state.apply_action(BuildRoadAction(edge_id))
                self._update_message()

    def _handle_action_click(self, pos: Tuple[int, int]) -> None:
        """Gère les clics en mode action."""
        if self.action_mode == "place_settlement":
            node_id = self._get_node_at_pos(pos)
            if node_id and self.game_state.can_place_settlement(node_id, self.game_state.current_player_idx):
                self.game_state = self.game_state.apply_action(BuildSettlementAction(node_id))
                self.action_mode = None
                self._update_message()
        elif self.action_mode == "place_road":
            edge_id = self._get_edge_at_pos(pos)
            if edge_id and self.game_state.can_place_road(edge_id, self.game_state.current_player_idx):
                self.game_state = self.game_state.apply_action(BuildRoadAction(edge_id))
                self.action_mode = None
                self._update_message()
        elif self.action_mode == "place_city":
            node_id = self._get_node_at_pos(pos)
            if node_id and self.game_state.can_place_city(node_id, self.game_state.current_player_idx):
                self.game_state = self.game_state.apply_action(BuildCityAction(node_id))
                self.action_mode = None
                self._update_message()
        elif self.action_mode == "move_robber":
            coord = self._get_coord_at_pos(pos)
            if coord and coord in self.game_state.board.tile_by_coord:
                tile = self.game_state.board.tile_by_coord[coord]
                # Simplifié : pas de victime pour l'instant
                self.game_state = self.game_state.apply_action(MoveRobberAction(tile.id, None))
                self.action_mode = None
                self.message = "Voleur déplacé"

    def _handle_action_button(self, action_key: str) -> None:
        """Réagit aux clics sur les boutons du panneau d'action."""
        if not self.game_state:
            return

        if action_key == "build_settlement" and self._can_build_settlement():
            if self.action_mode == "place_settlement":
                self.action_mode = None
                self._update_message()
            else:
                self.action_mode = "place_settlement"
                self.message = "Choisissez un emplacement pour votre colonie"
        elif action_key == "build_road" and self._can_build_road():
            if self.action_mode == "place_road":
                self.action_mode = None
                self._update_message()
            else:
                self.action_mode = "place_road"
                self.message = "Choisissez une arête pour votre route"
        elif action_key == "build_city" and self._can_build_city():
            if self.action_mode == "place_city":
                self.action_mode = None
                self._update_message()
            else:
                self.action_mode = "place_city"
                self.message = "Choisissez une colonie à améliorer"
        elif action_key == "buy_dev_card" and self._can_buy_dev_card():
            self.game_state = self.game_state.apply_action(BuyDevCardAction())
            self.action_mode = None
            self._update_message()
            self.message = "Carte développement achetée"
        elif action_key == "end_turn" and self._can_end_turn():
            self._end_turn()

    def _handle_motion(self, pos: Tuple[int, int]) -> None:
        """Gère le mouvement de la souris."""
        if not self.game_state:
            return

        if self.game_state.game_phase == GamePhase.SETUP:
            if self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed:
                self.hover_node = self._get_node_at_pos(pos)
                self.hover_edge = None
            else:
                self.hover_edge = self._get_edge_at_pos(pos)
                self.hover_node = None
        elif self.action_mode in ["place_settlement", "place_city"]:
            self.hover_node = self._get_node_at_pos(pos)
            self.hover_edge = None
        elif self.action_mode == "place_road":
            self.hover_edge = self._get_edge_at_pos(pos)
            self.hover_node = None
        else:
            self.hover_node = None
            self.hover_edge = None

    def _roll_dice(self) -> None:
        """Lance les dés."""
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        self.dice_values = (d1, d2)
        self.show_dice = True
        self.game_state.last_dice_roll = total

        if total == 7:
            self.message = f"Dé: {total} - Le voleur attaque!"
            self.action_mode = "move_robber"
        else:
            self.game_state.distribute_resources(total)
            self.message = f"Dé: {total} - Ressources produites"

    def _end_turn(self) -> None:
        """Termine le tour."""
        self.game_state.next_player()
        self.dice_values = None
        self.show_dice = False
        self.action_mode = None
        self.game_state.current_player.dev_card_played_this_turn = False
        self.game_state.current_player.dev_cards_bought_this_turn = []
        self._update_message()

    def _get_node_at_pos(self, pos: Tuple[int, int]) -> Optional[int]:
        """Trouve le node le plus proche."""
        min_dist = 20.0
        closest = None

        # Itérer directement sur les nodes connus du plateau (IDs déterministes)
        for node_id in self.game_state.board.nodes:
            node_pos = self._get_node_screen_pos(node_id)
            dist = math.hypot(pos[0] - node_pos[0], pos[1] - node_pos[1])
            if dist < min_dist:
                min_dist = dist
                closest = node_id

        return closest

    def _get_edge_at_pos(self, pos: Tuple[int, int]) -> Optional[int]:
        """Trouve l'edge le plus proche."""
        min_dist = 15.0
        closest = None

        for edge_id in self.game_state.board.edges:
            p1, p2 = self._get_edge_screen_endpoints(edge_id)
            dist = self._point_to_segment_dist(pos, p1, p2)
            if dist < min_dist:
                min_dist = dist
                closest = edge_id

        return closest

    def _get_coord_at_pos(self, pos: Tuple[int, int]) -> Optional[Coordinate]:
        """Trouve la coordonnée la plus proche."""
        min_dist = float(self.hex_radius)
        closest = None

        for tile in self.game_state.board.tiles.values():
            hex_pos = self._coord_to_screen(tile.coordinate)
            dist = math.hypot(pos[0] - hex_pos[0], pos[1] - hex_pos[1])
            if dist < min_dist:
                min_dist = dist
                closest = tile.coordinate

        return closest

    def _get_node_screen_pos(self, node_id: int) -> Tuple[int, int]:
        """Position écran d'un node."""
        if node_id in self._node_cache:
            return self._node_cache[node_id]

        # Résoudre par recherche deterministe sur le plateau
        for tile in self.game_state.board.tiles.values():
            for node_dir in NodeDirection:
                if get_node_id(tile.coordinate, node_dir) == node_id:
                    center = self._coord_to_screen(tile.coordinate)

                    # Angles pour vertices (clockwise depuis le haut)
                    angles = {
                        NodeDirection.NORTH: math.radians(90),
                        NodeDirection.NORTHEAST: math.radians(30),
                        NodeDirection.SOUTHEAST: math.radians(330),
                        NodeDirection.SOUTH: math.radians(270),
                        NodeDirection.SOUTHWEST: math.radians(210),
                        NodeDirection.NORTHWEST: math.radians(150),
                    }
                    angle = angles[node_dir]
                    x = int(center[0] + self.hex_radius * math.cos(angle))
                    y = int(center[1] + self.hex_radius * math.sin(angle))
                    pos = (x, y)
                    self._node_cache[node_id] = pos
                    return pos

        return (0, 0)

    def _get_edge_screen_endpoints(self, edge_id: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Positions écran des extrémités d'une edge."""
        # Utiliser le mapping déjà pré-calculé du plateau
        if edge_id in self.game_state.board.edges_to_nodes:
            n1, n2 = self.game_state.board.edges_to_nodes[edge_id]
            return (self._get_node_screen_pos(n1), self._get_node_screen_pos(n2))
        return ((0, 0), (0, 0))

    def _coord_to_screen(self, coord: Coordinate) -> Tuple[int, int]:
        """Convertit coordonnées cubiques en écran."""
        q, r = coord.x, coord.z
        x = self.hex_radius * (1.732 * q + 0.866 * r)
        y = self.hex_radius * (1.5 * r)
        return (int(x + self.board_offset_x), int(y + self.board_offset_y))

    def _point_to_segment_dist(self, p: Tuple[int, int], a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Distance point-segment."""
        px, py = p
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay

        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)

        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def _turn_allows_actions(self) -> bool:
        """Vérifie si le joueur peut effectuer des actions de construction."""
        if not self.game_state:
            return False
        return (
            self.game_state.game_phase == GamePhase.MAIN_GAME
            and self.game_state.turn_phase == TurnPhase.MAIN
            and self.show_dice
            and self.action_mode != "move_robber"
        )

    def _can_build_settlement(self) -> bool:
        """Vérifie si le joueur courant peut construire une colonie maintenant."""
        if not self.game_state or not self._turn_allows_actions():
            return False
        player = self.game_state.current_player
        if not (player.can_build_settlement() and player.can_afford(BUILDING_COSTS[BuildingType.SETTLEMENT])):
            return False
        player_id = self.game_state.current_player_idx
        return any(
            self.game_state.can_place_settlement(node_id, player_id)
            for node_id in self.game_state.board.nodes
        )

    def _can_build_city(self) -> bool:
        """Vérifie si le joueur courant peut construire une ville maintenant."""
        if not self.game_state or not self._turn_allows_actions():
            return False
        player = self.game_state.current_player
        if not (player.can_build_city() and player.can_afford(BUILDING_COSTS[BuildingType.CITY])):
            return False
        player_id = self.game_state.current_player_idx
        return any(
            self.game_state.can_place_city(node_id, player_id)
            for node_id in player.settlements
        )

    def _can_build_road(self) -> bool:
        """Vérifie si le joueur courant peut construire une route maintenant."""
        if not self.game_state or not self._turn_allows_actions():
            return False
        player = self.game_state.current_player
        if not (player.can_build_road() and player.can_afford(BUILDING_COSTS[BuildingType.ROAD])):
            return False
        player_id = self.game_state.current_player_idx
        return any(
            self.game_state.can_place_road(edge_id, player_id)
            for edge_id in self.game_state.board.edges
        )

    def _can_buy_dev_card(self) -> bool:
        """Vérifie si le joueur peut acheter une carte développement."""
        if not self.game_state or not self._turn_allows_actions():
            return False
        player = self.game_state.current_player
        return bool(self.game_state.dev_card_deck) and player.can_afford(DEV_CARD_COST)

    def _can_end_turn(self) -> bool:
        """Vérifie si le joueur peut terminer son tour."""
        if not self.game_state:
            return False
        return (
            self.game_state.game_phase == GamePhase.MAIN_GAME
            and self.game_state.turn_phase == TurnPhase.MAIN
            and self.show_dice
            and self.action_mode not in {"place_settlement", "place_road", "place_city", "move_robber"}
        )

    def _render(self) -> None:
        """Affiche tout."""
        self.screen.fill(WHITE)

        if not self.game_state:
            self._render_menu()
        else:
            self._render_game()

        pygame.display.flip()

    def _render_menu(self) -> None:
        """Menu principal."""
        title = self.font_large.render("CatanBot", True, BLACK)
        self.screen.blit(title, title.get_rect(center=(self.width // 2, 200)))

        instr = self.font_medium.render("Appuyez sur 'N' pour nouvelle partie", True, GRAY)
        self.screen.blit(instr, instr.get_rect(center=(self.width // 2, 300)))

    def _render_game(self) -> None:
        """Affiche le jeu."""
        # Plateau
        for tile in self.game_state.board.tiles.values():
            pos = self._coord_to_screen(tile.coordinate)
            self._draw_hex(pos, TERRAIN_COLORS.get(tile.terrain, GRAY))

            if tile.number and tile.is_land:
                circle_surf = pygame.Surface((30, 30), pygame.SRCALPHA)
                pygame.draw.circle(circle_surf, WHITE, (15, 15), 15)
                self.screen.blit(circle_surf, (pos[0] - 15, pos[1] - 15))

                num_text = self.font_medium.render(str(tile.number), True, BLACK)
                self.screen.blit(num_text, num_text.get_rect(center=pos))

        # Routes
        for edge_id, player_id in self.game_state.roads_on_board.items():
            p1, p2 = self._get_edge_screen_endpoints(edge_id)
            pygame.draw.line(self.screen, PLAYER_COLORS[player_id], p1, p2, 5)

        # Colonies
        for node_id, player_id in self.game_state.settlements_on_board.items():
            pos = self._get_node_screen_pos(node_id)
            pygame.draw.circle(self.screen, PLAYER_COLORS[player_id], pos, 8)
            pygame.draw.circle(self.screen, BLACK, pos, 8, 2)

        # Villes
        for node_id, player_id in self.game_state.cities_on_board.items():
            pos = self._get_node_screen_pos(node_id)
            rect = pygame.Rect(pos[0] - 10, pos[1] - 10, 20, 20)
            pygame.draw.rect(self.screen, PLAYER_COLORS[player_id], rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

        # Preview
        if self.hover_node:
            show_preview = (
                (self.game_state.game_phase == GamePhase.SETUP and
                 self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed) or
                self.action_mode == "place_settlement"
            )
            if show_preview and self.game_state.can_place_settlement(self.hover_node, self.game_state.current_player_idx):
                pos = self._get_node_screen_pos(self.hover_node)
                surf = pygame.Surface((20, 20), pygame.SRCALPHA)
                color = PLAYER_COLORS[self.game_state.current_player_idx]
                pygame.draw.circle(surf, (*color, 128), (10, 10), 10)
                self.screen.blit(surf, (pos[0] - 10, pos[1] - 10))

        if self.hover_edge:
            show_preview = (
                (self.game_state.game_phase == GamePhase.SETUP and
                 self.game_state.setup_settlements_placed != self.game_state.setup_roads_placed) or
                self.action_mode == "place_road"
            )
            if show_preview and self.game_state.can_place_road(self.hover_edge, self.game_state.current_player_idx):
                p1, p2 = self._get_edge_screen_endpoints(self.hover_edge)
                color = PLAYER_COLORS[self.game_state.current_player_idx]
                pygame.draw.line(self.screen, (*color, 128), p1, p2, 7)

        # UI
        self._render_players()
        self._render_dice()
        self._render_message()
        self._render_action_panel()
        self._render_controls()

    def _draw_hex(self, center: Tuple[int, int], color: Tuple[int, int, int]) -> None:
        """Dessine un hexagone."""
        points = []
        for i in range(6):
            angle = math.pi / 3 * i + math.pi / 6
            x = center[0] + self.hex_radius * math.cos(angle)
            y = center[1] + self.hex_radius * math.sin(angle)
            points.append((x, y))
        pygame.draw.polygon(self.screen, color, points)
        pygame.draw.polygon(self.screen, BLACK, points, 2)

    def _render_players(self) -> None:
        """Affiche les infos joueurs."""
        y = 20
        for i, player in enumerate(self.game_state.players):
            color = PLAYER_COLORS[i]
            is_current = (i == self.game_state.current_player_idx)

            rect = pygame.Rect(10, y, 350, 180)
            pygame.draw.rect(self.screen, WHITE, rect)
            pygame.draw.rect(self.screen, color if is_current else GRAY, rect, 3)

            name = f"JOUEUR {i + 1}" + (" (en cours)" if is_current else "")
            text = self.font_medium.render(name, True, color)
            self.screen.blit(text, (20, y + 10))

            vp = self.font_medium.render(f"Points: {player.victory_points()}/15", True, BLACK)
            self.screen.blit(vp, (20, y + 40))

            res_names = ["Bois", "Argile", "Mouton", "Blé", "Minerai"]
            res_y = y + 70
            for j, name in enumerate(res_names):
                count = player.resources[list(ResourceType)[j]]
                text = self.font_small.render(f"{name}: {count}", True, GRAY)
                self.screen.blit(text, (20, res_y + j * 20))

            y += 200

    def _render_dice(self) -> None:
        """Affiche les dés et le bouton."""
        if self.game_state.game_phase == GamePhase.MAIN_GAME and not self.show_dice:
            rect = pygame.Rect(self.width - 200, 50, 150, 60)
            pygame.draw.rect(self.screen, GREEN, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)
            text = self.font_medium.render("Lancer dés", True, WHITE)
            self.screen.blit(text, text.get_rect(center=rect.center))

        if self.show_dice and self.dice_values:
            x, y = self.width - 200, 130
            for i, val in enumerate(self.dice_values):
                rect = pygame.Rect(x + i * 60, y, 50, 50)
                pygame.draw.rect(self.screen, WHITE, rect)
                pygame.draw.rect(self.screen, BLACK, rect, 2)
                text = self.font_large.render(str(val), True, BLACK)
                self.screen.blit(text, text.get_rect(center=rect.center))

            total_text = f"Total: {sum(self.dice_values)}"
            text = self.font_medium.render(total_text, True, BLACK)
            self.screen.blit(text, (x, y + 60))

    def _render_message(self) -> None:
        """Affiche le message."""
        rect = pygame.Rect(370, 10, 800, 50)
        pygame.draw.rect(self.screen, WHITE, rect)
        pygame.draw.rect(self.screen, BLACK, rect, 2)
        text = self.font_medium.render(self.message, True, BLACK)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _render_controls(self) -> None:
        """Affiche les contrôles."""
        controls = ["ESC: Quitter", "N: Nouvelle partie", "SPACE: Tour suivant"]
        y = self.height - 60
        for ctrl in controls:
            text = self.font_small.render(ctrl, True, GRAY)
            self.screen.blit(text, (20, y))
            y += 20

    def _render_action_panel(self) -> None:
        """Affiche les boutons d'action du tour."""
        self.action_button_rects = {}

        if not self.game_state or self.game_state.game_phase != GamePhase.MAIN_GAME:
            return

        panel_width = 220
        panel_height = 260
        panel_x = self.width - panel_width - 30
        panel_y = 160
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)

        pygame.draw.rect(self.screen, WHITE, panel_rect)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 2)

        title = self.font_medium.render("Actions", True, BLACK)
        self.screen.blit(title, (panel_x + 16, panel_y + 12))

        buttons = [
            ("Construire colonie", "build_settlement", self._can_build_settlement()),
            ("Construire route", "build_road", self._can_build_road()),
            ("Construire ville", "build_city", self._can_build_city()),
            ("Acheter carte dev", "buy_dev_card", self._can_buy_dev_card()),
            ("Finir tour", "end_turn", self._can_end_turn()),
        ]

        button_height = 42
        button_margin_top = 50
        button_spacing = 8

        for idx, (label, key, enabled) in enumerate(buttons):
            rect = pygame.Rect(
                panel_x + 15,
                panel_y + button_margin_top + idx * (button_height + button_spacing),
                panel_width - 30,
                button_height,
            )

            highlight = (
                (key == "build_settlement" and self.action_mode == "place_settlement")
                or (key == "build_road" and self.action_mode == "place_road")
                or (key == "build_city" and self.action_mode == "place_city")
            )

            if not enabled:
                color = LIGHT_GRAY
                text_color = GRAY
            elif highlight:
                color = BLUE
                text_color = WHITE
            elif key == "end_turn":
                color = GREEN
                text_color = WHITE
            else:
                color = (100, 149, 237)  # Cornflower blue
                text_color = WHITE

            pygame.draw.rect(self.screen, color, rect, border_radius=6)
            pygame.draw.rect(self.screen, BLACK, rect, 2, border_radius=6)

            text = self.font_small.render(label, True, text_color)
            self.screen.blit(text, text.get_rect(center=rect.center))

            if enabled:
                self.action_button_rects[key] = rect


def main() -> None:
    """Point d'entrée."""
    window = GameWindow()
    window.start_new_game()
    window.run()


if __name__ == "__main__":
    main()
