"""Simple Pygame GUI for testing the bot.

Interface graphique minimaliste pour:
- Visualiser le plateau
- Jouer contre le bot
- Vérifier que les règles fonctionnent correctement
"""

import pygame
import sys
from typing import Optional, Tuple
import math
import numpy as np

from ..core.game_state import GameState, GamePhase
from ..core.board import Board, HexCoord, VertexCoord, EdgeCoord
from ..core.constants import TerrainType, ResourceType, DevelopmentCardType, BUILDING_COSTS, BuildingType, DEV_CARD_COST
from ..core.actions import BuildSettlementAction, BuildRoadAction, BuildCityAction


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

    def __init__(self, width: int = 1400, height: int = 900):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("CatanBot - Partie à 2 joueurs")

        self.clock = pygame.time.Clock()
        self.fps = 60

        # Fonts
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)

        # Game state
        self.game_state: Optional[GameState] = None

        # Paramètres d'affichage du plateau
        self.hex_radius = 45
        self.board_offset_x = 700
        self.board_offset_y = 450

        # Discard mode
        self.discard_mode: bool = False
        self.discard_player_id: Optional[int] = None
        self.discard_target: int = 0
        self.discard_selection: dict[ResourceType, int] = {}

        # Game mode tracking
        self.action_mode: Optional[str] = None  # None, "place_settlement", "place_road", "place_city", "move_robber"

        # UI state
        self.selected_vertex: Optional[VertexCoord] = None
        self.selected_edge: Optional[EdgeCoord] = None
        self.hover_vertex: Optional[VertexCoord] = None
        self.hover_edge: Optional[EdgeCoord] = None

        # Dice state
        self.dice_values: Optional[Tuple[int, int]] = None
        self.show_dice: bool = False

        # Messages
        self.message: str = ""
        self.message_time: int = 0

    def start_new_game(self, num_players: int = 2) -> None:
        """Démarre une nouvelle partie à 2 joueurs."""
        board = Board.create_standard_board(shuffle=True)

        # Créer les joueurs
        from ..core.player import PlayerState
        players = [PlayerState(player_id=i) for i in range(num_players)]

        self.game_state = GameState(
            board=board,
            num_players=num_players,
            victory_points_to_win=15,
            players=players,
        )
        self.discard_mode = False
        self.discard_player_id = None
        self.discard_selection = {}
        self.action_mode = None
        self.dice_values = None
        self.show_dice = False
        self._update_message_for_current_state()

    def set_message(self, msg: str) -> None:
        """Affiche un message à l'utilisateur."""
        self.message = msg
        self.message_time = pygame.time.get_ticks()

    def _update_message_for_current_state(self) -> None:
        """Met à jour le message en fonction de l'état actuel du jeu."""
        if self.game_state is None:
            return

        player_id = self.game_state.current_player_idx

        if self.game_state.game_phase == GamePhase.SETUP:
            # Déterminer si on doit placer une colonie ou une route
            if self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed:
                self.set_message(f"Joueur {player_id + 1}: Placez une colonie")
            else:
                self.set_message(f"Joueur {player_id + 1}: Placez une route adjacente")
        elif self.game_state.game_phase == GamePhase.MAIN_GAME:
            if self.dice_values is None:
                self.set_message(f"Joueur {player_id + 1}: Lancez les dés")
            else:
                self.set_message(f"Joueur {player_id + 1}: Construisez ou terminez votre tour (ESPACE)")
        elif self.game_state.game_phase == GamePhase.GAME_OVER:
            winner_id = self.game_state.winner
            if winner_id is not None:
                self.set_message(f"Joueur {winner_id + 1} a gagné!")

    def run(self) -> None:
        """Boucle principale du jeu."""
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event.pos)
                elif event.type == pygame.KEYDOWN:
                    self._handle_keypress(event.key)

            self._render()
            self.clock.tick(self.fps)

        pygame.quit()
        sys.exit()

    def _handle_click(self, pos: Tuple[int, int]) -> None:
        """Gère les clics de souris."""
        if self.game_state is None:
            return

        if self.discard_mode:
            self._handle_discard_click(pos)
            return

        # Vérifier si c'est un clic sur le bouton de dés
        if self.action_mode is None and self.game_state.game_phase == GamePhase.MAIN_GAME:
            dice_button_rect = pygame.Rect(self.width - 200, 50, 150, 60)
            if dice_button_rect.collidepoint(pos):
                self._roll_dice()
                return

        # Clic sur le plateau pour placer une construction
        # En phase SETUP ou quand un mode d'action est actif
        if self.game_state.game_phase == GamePhase.SETUP:
            # Déterminer si on doit placer une colonie ou une route
            if self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed:
                vertex = self._get_vertex_at_pos(pos)
                if vertex and self.game_state.can_place_settlement(vertex, self.game_state.current_player_idx):
                    self._apply_action_and_update(BuildSettlementAction(vertex))
            else:
                edge = self._get_edge_at_pos(pos)
                if edge and self.game_state.can_place_road(edge, self.game_state.current_player_idx):
                    self._apply_action_and_update(BuildRoadAction(edge))
        elif self.action_mode == "place_settlement":
            vertex = self._get_vertex_at_pos(pos)
            if vertex and self.game_state.can_place_settlement(vertex, self.game_state.current_player_idx):
                self._apply_action_and_update(BuildSettlementAction(vertex))
                self.action_mode = None
        elif self.action_mode == "place_road":
            edge = self._get_edge_at_pos(pos)
            if edge and self.game_state.can_place_road(edge, self.game_state.current_player_idx):
                self._apply_action_and_update(BuildRoadAction(edge))
                self.action_mode = None
        elif self.action_mode == "place_city":
            vertex = self._get_vertex_at_pos(pos)
            if vertex and self.game_state.can_place_city(vertex, self.game_state.current_player_idx):
                self._apply_action_and_update(BuildCityAction(vertex))
                self.action_mode = None
        elif self.action_mode == "move_robber":
            hex_coord = self._get_hex_at_pos(pos)
            if hex_coord and hex_coord in self.game_state.board.hexes:
                # Vérifier que le voleur n'est pas déjà sur cet hexagone
                hex_tile = self.game_state.board.hexes[hex_coord]
                if not hex_tile.has_robber:
                    # Déplacer le voleur (sans vol pour l'instant)
                    from ..core.actions import MoveRobberAction
                    self._apply_action_and_update(MoveRobberAction(hex_coord, None))
                    self.action_mode = None
                    self.set_message("Voleur déplacé. Construisez ou appuyez ESPACE pour terminer le tour")

    def _handle_mouse_motion(self, pos: Tuple[int, int]) -> None:
        """Gère le mouvement de la souris pour afficher les preview."""
        if self.game_state is None or self.discard_mode:
            return

        # Mettre à jour le hover
        # En phase SETUP, déterminer automatiquement ce qu'on doit placer
        if self.game_state.game_phase == GamePhase.SETUP:
            if self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed:
                # On doit placer une colonie
                self.hover_vertex = self._get_vertex_at_pos(pos)
                self.hover_edge = None
            else:
                # On doit placer une route
                self.hover_edge = self._get_edge_at_pos(pos)
                self.hover_vertex = None
        elif self.action_mode in ["place_settlement", "place_city"]:
            self.hover_vertex = self._get_vertex_at_pos(pos)
            self.hover_edge = None
        elif self.action_mode == "place_road":
            self.hover_edge = self._get_edge_at_pos(pos)
            self.hover_vertex = None
        else:
            self.hover_vertex = None
            self.hover_edge = None

    def _handle_discard_click(self, pos: Tuple[int, int]) -> None:
        """Gère les clics dans l'interface de discard."""
        if self.discard_player_id is None or self.game_state is None:
            return

        player = self.game_state.players[self.discard_player_id]
        selected_total = sum(self.discard_selection.values())

        # Calculer les positions des boutons
        panel_width = 600
        panel_height = 400
        panel_x = (self.width - panel_width) // 2
        panel_y = (self.height - panel_height) // 2

        text_x = panel_x + 20
        text_y = panel_y + 100  # Après le titre et les instructions

        for i, resource_type in enumerate(ResourceType):
            count = player.resources[resource_type]
            selected = self.discard_selection.get(resource_type, 0)

            button_y = text_y + i * 40

            # Bouton -
            minus_rect = pygame.Rect(text_x + 350, button_y, 40, 30)
            if minus_rect.collidepoint(pos) and selected > 0:
                self.discard_selection[resource_type] = selected - 1
                if self.discard_selection[resource_type] == 0:
                    del self.discard_selection[resource_type]
                return

            # Bouton +
            plus_rect = pygame.Rect(text_x + 400, button_y, 40, 30)
            if plus_rect.collidepoint(pos) and selected < count and selected_total < self.discard_target:
                self.discard_selection[resource_type] = selected + 1
                return

    def _handle_keypress(self, key: int) -> None:
        """Gère les touches du clavier."""
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        elif key == pygame.K_n:
            # Nouvelle partie
            self.start_new_game()
        elif key == pygame.K_RETURN and self.discard_mode:
            # Valider la défausse
            self._validate_discard()
        elif key == pygame.K_SPACE:
            # Terminer le tour (phase principale seulement)
            if self.game_state and self.game_state.game_phase == GamePhase.MAIN_GAME and self.dice_values:
                self._end_turn()

    def _validate_discard(self) -> None:
        """Valide et applique la défausse des cartes."""
        if self.discard_player_id is None or self.game_state is None:
            return

        selected_total = sum(self.discard_selection.values())
        if selected_total != self.discard_target:
            return  # Pas encore assez de cartes sélectionnées

        # Défausser les cartes
        player = self.game_state.players[self.discard_player_id]
        for resource_type, count in self.discard_selection.items():
            player.resources[resource_type] -= count

        # Réinitialiser le mode discard
        self.discard_mode = False
        self.discard_player_id = None
        self.discard_selection = {}
        self.discard_target = 0

    def check_discard_needed(self) -> None:
        """Vérifie si des joueurs doivent défausser des cartes (après un 7)."""
        if self.game_state is None:
            return

        for i, player in enumerate(self.game_state.players):
            if player.total_resources() > 9:
                # Ce joueur doit défausser
                self.discard_mode = True
                self.discard_player_id = i
                self.discard_target = player.total_resources() // 2
                self.discard_selection = {}
                break  # Un seul joueur à la fois

    def _apply_action_and_update(self, action) -> None:
        """Applique une action et met à jour l'interface."""
        if self.game_state is None:
            return

        # Appliquer l'action via GameState (qui retourne un nouveau state)
        self.game_state = self.game_state.apply_action(action)

        # Mettre à jour le message
        self._update_message_for_current_state()

        # Vérifier la victoire
        if self.game_state.game_phase == GamePhase.GAME_OVER:
            winner_id = self.game_state.winner
            if winner_id is not None:
                self.set_message(f"Joueur {winner_id + 1} a gagné avec {self.game_state.players[winner_id].victory_points()} points!")

    def _roll_dice(self) -> None:
        """Lance les dés et produit les ressources."""
        if self.game_state is None:
            return

        import random
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        total = dice1 + dice2

        self.dice_values = (dice1, dice2)
        self.show_dice = True
        self.game_state.last_dice_roll = total

        if total == 7:
            self.set_message(f"Dé: {total} - Le voleur attaque!")
            self.check_discard_needed()
            if not self.discard_mode:
                self.action_mode = "move_robber"
                self.set_message("Déplacez le voleur sur une tuile")
        else:
            # Production de ressources
            self.game_state.distribute_resources(total)
            self.action_mode = None
            self.set_message(f"Dé: {total} - Ressources produites. Construisez ou appuyez ESPACE pour terminer le tour")


    def _end_turn(self) -> None:
        """Termine le tour et passe au joueur suivant."""
        if self.game_state is None:
            return

        # Passer au joueur suivant
        self.game_state.next_player()

        # Réinitialiser l'état du tour
        self.dice_values = None
        self.show_dice = False
        self.action_mode = None

        # Réinitialiser les cartes dev jouées
        player = self.game_state.current_player
        player.dev_card_played_this_turn = False
        player.dev_cards_bought_this_turn = []

        self.set_message(f"Joueur {self.game_state.current_player_idx + 1}: Lancez les dés!")

    def _check_victory(self) -> None:
        """Vérifie si un joueur a gagné."""
        if self.game_state is None:
            return

        winner_id = self.game_state.check_victory()
        if winner_id is not None:
            self.game_state.game_phase = GamePhase.GAME_OVER
            self.game_state.winner = winner_id
            self.set_message(f"Joueur {winner_id + 1} a gagné avec {self.game_state.players[winner_id].victory_points()} points!")

    def _has_any_valid_placements(self, placement_type: str) -> bool:
        """
        Vérifie s'il existe au moins un emplacement valide pour le type de construction donné.

        Args:
            placement_type: "settlement", "road", ou "city"

        Returns:
            True s'il existe au moins un emplacement valide
        """
        if self.game_state is None:
            return False

        return self.game_state.has_valid_placements(
            self.game_state.current_player_idx,
            placement_type
        )

    def _get_vertex_at_pos(self, pos: Tuple[int, int]) -> Optional[VertexCoord]:
        """Trouve le sommet le plus proche de la position de la souris."""
        if self.game_state is None:
            return None

        min_dist: float = 20.0  # Distance max en pixels
        closest_vertex = None

        for hex_coord in self.game_state.board.hexes:
            # Créer les 6 vertices de cet hexagone
            for direction in range(6):
                vertex = VertexCoord(hex_coord, direction)
                vertex_screen_pos = self._vertex_to_screen(vertex)
                dx = float(pos[0] - vertex_screen_pos[0])
                dy = float(pos[1] - vertex_screen_pos[1])
                dist = math.hypot(dx, dy)
                if dist < min_dist:
                    min_dist = dist
                    closest_vertex = vertex

        return closest_vertex

    def _get_edge_at_pos(self, pos: Tuple[int, int]) -> Optional[EdgeCoord]:
        """Trouve l'arête la plus proche de la position de la souris."""
        if self.game_state is None:
            return None

        min_dist: float = 15.0  # Distance max en pixels
        closest_edge = None

        # Utiliser uniquement les arêtes valides du plateau
        for edge in self.game_state.board.edges:
            v1, v2 = edge.vertices()
            v1_screen = self._vertex_to_screen(v1)
            v2_screen = self._vertex_to_screen(v2)

            # Distance point-segment
            dist = self._point_to_segment_distance(pos, v1_screen, v2_screen)
            if dist < min_dist:
                min_dist = dist
                closest_edge = edge

        return closest_edge

    def _point_to_segment_distance(self, point: Tuple[int, int], seg_a: Tuple[int, int], seg_b: Tuple[int, int]) -> float:
        """Calcule la distance entre un point et un segment."""
        px, py = point
        ax, ay = seg_a
        bx, by = seg_b

        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)

        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / float(dx**2 + dy**2)))
        proj_x, proj_y = ax + t * dx, ay + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def _vertex_to_screen(self, vertex: VertexCoord) -> Tuple[int, int]:
        """Convertit un sommet en coordonnées écran en moyennant les positions des hexagones adjacents."""
        hexes = vertex.adjacent_hexes()
        if not hexes:
            return (0, 0)

        # Moyenne des positions des hexagones adjacents
        x_sum, y_sum = 0, 0
        count = 0
        for hex_coord in hexes:
            if self.game_state is not None and hex_coord in self.game_state.board.hexes:
                hx, hy = self._hex_to_screen(hex_coord)
                x_sum += hx
                y_sum += hy
                count += 1

        if count == 0:
            return (0, 0)

        # Le vertex est à la moyenne des centres + un petit offset
        # C'est une approximation, mais ça fonctionne visuellement
        return (int(x_sum / count), int(y_sum / count))

    def _get_hex_at_pos(self, pos: Tuple[int, int]) -> Optional[HexCoord]:
        """Trouve l'hexagone le plus proche de la position de la souris."""
        if self.game_state is None:
            return None

        min_dist: float = self.hex_radius  # Distance max en pixels
        closest_hex = None

        for hex_coord in self.game_state.board.hexes:
            hex_screen_pos = self._hex_to_screen(hex_coord)
            dx = float(pos[0] - hex_screen_pos[0])
            dy = float(pos[1] - hex_screen_pos[1])
            dist = math.hypot(dx, dy)
            if dist < min_dist:
                min_dist = dist
                closest_hex = hex_coord

        return closest_hex

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

        # Afficher les constructions (routes, colonies, villes)
        self._render_buildings()

        # Afficher les informations des joueurs
        self._render_player_info()

        # Afficher les boutons et contrôles de jeu
        self._render_game_controls()

        # Afficher le message en haut
        self._render_message()

        # Afficher l'interface de discard si nécessaire
        if self.discard_mode:
            self._render_discard_interface()

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

    def _render_buildings(self) -> None:
        """Affiche les routes, colonies et villes sur le plateau."""
        if self.game_state is None:
            return

        # Dessiner les routes
        for edge, player_id in self.game_state.roads_on_board.items():
            v1, v2 = edge.vertices()
            v1_screen = self._vertex_to_screen(v1)
            v2_screen = self._vertex_to_screen(v2)
            color = PLAYER_COLORS[player_id]
            pygame.draw.line(self.screen, color, v1_screen, v2_screen, 5)

        # Dessiner les colonies
        for vertex, player_id in self.game_state.settlements_on_board.items():
            pos = self._vertex_to_screen(vertex)
            color = PLAYER_COLORS[player_id]
            pygame.draw.circle(self.screen, color, pos, 8)
            pygame.draw.circle(self.screen, BLACK, pos, 8, 2)

        # Dessiner les villes
        for vertex, player_id in self.game_state.cities_on_board.items():
            pos = self._vertex_to_screen(vertex)
            color = PLAYER_COLORS[player_id]
            pygame.draw.rect(self.screen, color, (pos[0]-10, pos[1]-10, 20, 20))
            pygame.draw.rect(self.screen, BLACK, (pos[0]-10, pos[1]-10, 20, 20), 2)

        # Afficher les emplacements valides en mode placement
        # Preview pour les colonies (SETUP ou action_mode)
        show_settlement_preview = (
            (self.game_state.game_phase == GamePhase.SETUP and
             self.game_state.setup_settlements_placed == self.game_state.setup_roads_placed) or
            self.action_mode == "place_settlement"
        )
        if show_settlement_preview and self.hover_vertex:
            if self.game_state.can_place_settlement(self.hover_vertex, self.game_state.current_player_idx):
                pos = self._vertex_to_screen(self.hover_vertex)
                color = PLAYER_COLORS[self.game_state.current_player_idx]
                pygame.draw.circle(self.screen, (*color, 128), pos, 10)

        # Preview pour les routes (SETUP ou action_mode)
        show_road_preview = (
            (self.game_state.game_phase == GamePhase.SETUP and
             self.game_state.setup_settlements_placed != self.game_state.setup_roads_placed) or
            self.action_mode == "place_road"
        )
        if show_road_preview and self.hover_edge:
            if self.game_state.can_place_road(self.hover_edge, self.game_state.current_player_idx):
                v1, v2 = self.hover_edge.vertices()
                v1_screen = self._vertex_to_screen(v1)
                v2_screen = self._vertex_to_screen(v2)
                color = PLAYER_COLORS[self.game_state.current_player_idx]
                pygame.draw.line(self.screen, (*color, 128), v1_screen, v2_screen, 7)

    def _render_message(self) -> None:
        """Affiche le message en haut de l'écran."""
        if self.message:
            # Fond du message
            msg_rect = pygame.Rect(370, 10, 800, 50)
            pygame.draw.rect(self.screen, WHITE, msg_rect)
            pygame.draw.rect(self.screen, BLACK, msg_rect, 2)

            # Texte
            text = self.font_medium.render(self.message, True, BLACK)
            text_rect = text.get_rect(center=msg_rect.center)
            self.screen.blit(text, text_rect)

    def _render_game_controls(self) -> None:
        """Affiche les boutons de jeu (dés, constructions, etc)."""
        if self.game_state is None:
            return

        # Bouton de dés (seulement en phase principale et sans action en cours)
        if self.game_state.game_phase == GamePhase.MAIN_GAME and self.action_mode is None:
            dice_button_rect = pygame.Rect(self.width - 200, 50, 150, 60)
            pygame.draw.rect(self.screen, GREEN, dice_button_rect)
            pygame.draw.rect(self.screen, BLACK, dice_button_rect, 2)

            dice_text = self.font_medium.render("Lancer dés", True, WHITE)
            dice_text_rect = dice_text.get_rect(center=dice_button_rect.center)
            self.screen.blit(dice_text, dice_text_rect)

        # Afficher les dés si lancés
        if self.show_dice and self.dice_values:
            dice_x = self.width - 200
            dice_y = 130

            # Dé 1
            pygame.draw.rect(self.screen, WHITE, (dice_x, dice_y, 50, 50))
            pygame.draw.rect(self.screen, BLACK, (dice_x, dice_y, 50, 50), 2)
            d1_text = self.font_large.render(str(self.dice_values[0]), True, BLACK)
            d1_rect = d1_text.get_rect(center=(dice_x + 25, dice_y + 25))
            self.screen.blit(d1_text, d1_rect)

            # Dé 2
            pygame.draw.rect(self.screen, WHITE, (dice_x + 60, dice_y, 50, 50))
            pygame.draw.rect(self.screen, BLACK, (dice_x + 60, dice_y, 50, 50), 2)
            d2_text = self.font_large.render(str(self.dice_values[1]), True, BLACK)
            d2_rect = d2_text.get_rect(center=(dice_x + 85, dice_y + 25))
            self.screen.blit(d2_text, d2_rect)

            # Total
            total_text = f"Total: {self.dice_values[0] + self.dice_values[1]}"
            text = self.font_medium.render(total_text, True, BLACK)
            self.screen.blit(text, (dice_x, dice_y + 60))

        # Boutons de construction (phase principale, après avoir lancé les dés)
        if self.game_state.game_phase == GamePhase.MAIN_GAME and self.action_mode is None and self.dice_values:
            button_y = 250
            button_width = 150
            button_height = 40
            button_spacing = 10
            button_x = self.width - 200

            # Bouton Colonie
            player = self.game_state.current_player
            if (player.can_afford(BUILDING_COSTS[BuildingType.SETTLEMENT]) and
                player.can_build_settlement() and
                self._has_any_valid_placements("settlement")):
                settlement_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                pygame.draw.rect(self.screen, GREEN, settlement_rect)
                pygame.draw.rect(self.screen, BLACK, settlement_rect, 2)
                text = self.font_small.render("Colonie (B,M,B,B)", True, WHITE)
                text_rect = text.get_rect(center=settlement_rect.center)
                self.screen.blit(text, text_rect)

                # Détecter le clic
                mouse_pos = pygame.mouse.get_pos()
                if settlement_rect.collidepoint(mouse_pos) and pygame.mouse.get_pressed()[0]:
                    self.action_mode = "place_settlement"
                    self.set_message("Cliquez sur un sommet pour placer votre colonie")

            button_y += button_height + button_spacing

            # Bouton Route
            if (player.can_afford(BUILDING_COSTS[BuildingType.ROAD]) and
                player.can_build_road() and
                self._has_any_valid_placements("road")):
                road_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                pygame.draw.rect(self.screen, GREEN, road_rect)
                pygame.draw.rect(self.screen, BLACK, road_rect, 2)
                text = self.font_small.render("Route (B,A)", True, WHITE)
                text_rect = text.get_rect(center=road_rect.center)
                self.screen.blit(text, text_rect)

                # Détecter le clic
                mouse_pos = pygame.mouse.get_pos()
                if road_rect.collidepoint(mouse_pos) and pygame.mouse.get_pressed()[0]:
                    self.action_mode = "place_road"
                    self.set_message("Cliquez sur une arête pour placer votre route")

            button_y += button_height + button_spacing

            # Bouton Ville
            if (player.can_afford(BUILDING_COSTS[BuildingType.CITY]) and
                player.can_build_city() and
                self._has_any_valid_placements("city")):
                city_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                pygame.draw.rect(self.screen, GREEN, city_rect)
                pygame.draw.rect(self.screen, BLACK, city_rect, 2)
                text = self.font_small.render("Ville (BLÉx3,Mx2)", True, WHITE)
                text_rect = text.get_rect(center=city_rect.center)
                self.screen.blit(text, text_rect)

                # Détecter le clic
                mouse_pos = pygame.mouse.get_pos()
                if city_rect.collidepoint(mouse_pos) and pygame.mouse.get_pressed()[0]:
                    self.action_mode = "place_city"
                    self.set_message("Cliquez sur une de vos colonies pour la transformer en ville")

            button_y += button_height + button_spacing

            # Bouton Carte Développement
            if player.can_afford(DEV_CARD_COST) and len(self.game_state.dev_card_deck) > 0:
                dev_card_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                pygame.draw.rect(self.screen, GREEN, dev_card_rect)
                pygame.draw.rect(self.screen, BLACK, dev_card_rect, 2)
                text = self.font_small.render("Carte Dev (Mt,Blé,Mr)", True, WHITE)
                text_rect = text.get_rect(center=dev_card_rect.center)
                self.screen.blit(text, text_rect)

                # Détecter le clic
                mouse_pos = pygame.mouse.get_pos()
                if dev_card_rect.collidepoint(mouse_pos) and pygame.mouse.get_pressed()[0]:
                    # Acheter une carte développement
                    card = self.game_state.buy_dev_card(self.game_state.current_player_idx)
                    if card:
                        self.set_message(f"Carte développement achetée: {card.name}")
                    else:
                        self.set_message("Impossible d'acheter une carte développement")

    def _render_player_info(self) -> None:
        """Affiche les informations détaillées des joueurs."""
        if self.game_state is None:
            return

        # Panel de gauche pour les joueurs
        panel_width = 350
        y_offset = 20

        for i, player in enumerate(self.game_state.players):
            color = PLAYER_COLORS[i]
            is_current = (i == self.game_state.current_player)

            # Fond du panneau
            panel_rect = pygame.Rect(10, y_offset, panel_width, 280)
            border_color = color if is_current else GRAY
            pygame.draw.rect(self.screen, WHITE, panel_rect)
            pygame.draw.rect(self.screen, border_color, panel_rect, 3)

            text_x = 20
            text_y = y_offset + 10

            # Nom du joueur et points
            player_text = f"JOUEUR {i + 1}"
            if is_current:
                player_text += " (en cours)"
            text = self.font_medium.render(player_text, True, color)
            self.screen.blit(text, (text_x, text_y))
            text_y += 30

            # Points de victoire
            vp_text = f"Points de victoire: {player.victory_points()}/15"
            text = self.font_medium.render(vp_text, True, BLACK)
            self.screen.blit(text, (text_x, text_y))
            text_y += 30

            # Ressources détaillées
            resources_title = self.font_small.render("Ressources:", True, BLACK)
            self.screen.blit(resources_title, (text_x, text_y))
            text_y += 20

            resource_names = {
                ResourceType.WOOD: "Bois",
                ResourceType.BRICK: "Argile",
                ResourceType.SHEEP: "Mouton",
                ResourceType.WHEAT: "Blé",
                ResourceType.ORE: "Minerai"
            }

            for resource_type in ResourceType:
                count = player.resources[resource_type]
                name = resource_names.get(resource_type, str(resource_type))
                res_text = f"  {name}: {count}"
                text = self.font_small.render(res_text, True, GRAY)
                self.screen.blit(text, (text_x, text_y))
                text_y += 18

            text_y += 5

            # Cartes développement
            total_dev_cards = sum(player.dev_cards_in_hand.values())
            dev_text = f"Cartes développement: {total_dev_cards}"
            text = self.font_small.render(dev_text, True, BLACK)
            self.screen.blit(text, (text_x, text_y))
            text_y += 20

            # Détail des cartes développement
            if total_dev_cards > 0:
                for card_type, count in player.dev_cards_in_hand.items():
                    if count > 0:
                        card_name = card_type.name.replace("_", " ").title()
                        card_text = f"  {card_name}: {count}"
                        text = self.font_small.render(card_text, True, GRAY)
                        self.screen.blit(text, (text_x, text_y))
                        text_y += 18

            # Constructions
            text_y = y_offset + 220
            buildings_text = (
                f"Colonies: {len(player.settlements)}  "
                f"Villes: {len(player.cities)}  "
                f"Routes: {len(player.roads)}"
            )
            text = self.font_small.render(buildings_text, True, BLACK)
            self.screen.blit(text, (text_x, text_y))
            text_y += 18

            # Bonus
            bonus_parts = []
            if player.has_longest_road:
                bonus_parts.append("Route la + longue")
            if player.has_largest_army:
                bonus_parts.append("Armée la + grande")
            if bonus_parts:
                bonus_text = f"Bonus: {', '.join(bonus_parts)}"
                text = self.font_small.render(bonus_text, True, color)
                self.screen.blit(text, (text_x, text_y))

            y_offset += 300

    def _render_discard_interface(self) -> None:
        """Affiche l'interface de défausse des cartes."""
        if self.discard_player_id is None or self.game_state is None:
            return

        player = self.game_state.players[self.discard_player_id]

        # Fond semi-transparent
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Panneau central
        panel_width = 600
        panel_height = 400
        panel_x = (self.width - panel_width) // 2
        panel_y = (self.height - panel_height) // 2

        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(self.screen, WHITE, panel_rect)
        pygame.draw.rect(self.screen, RED, panel_rect, 3)

        text_x = panel_x + 20
        text_y = panel_y + 20

        # Titre
        title = f"Joueur {self.discard_player_id + 1} - Défausser des cartes"
        text = self.font_large.render(title, True, RED)
        self.screen.blit(text, (text_x, text_y))
        text_y += 40

        # Instructions
        current_total = player.total_resources()
        selected_total = sum(self.discard_selection.values())
        remaining = current_total - selected_total
        to_discard = self.discard_target

        instruction = f"Vous avez {current_total} cartes. Défaussez-en {to_discard}."
        text = self.font_medium.render(instruction, True, BLACK)
        self.screen.blit(text, (text_x, text_y))
        text_y += 30

        status = f"Sélectionnées: {selected_total}/{to_discard}"
        text = self.font_medium.render(status, True, BLACK)
        self.screen.blit(text, (text_x, text_y))
        text_y += 40

        # Afficher les ressources avec boutons +/-
        resource_names = {
            ResourceType.WOOD: "Bois",
            ResourceType.BRICK: "Argile",
            ResourceType.SHEEP: "Mouton",
            ResourceType.WHEAT: "Blé",
            ResourceType.ORE: "Minerai"
        }

        for resource_type in ResourceType:
            count = player.resources[resource_type]
            selected = self.discard_selection.get(resource_type, 0)
            name = resource_names.get(resource_type, str(resource_type))

            # Nom de la ressource
            res_text = f"{name}: {count} (défausser: {selected})"
            text = self.font_medium.render(res_text, True, BLACK)
            self.screen.blit(text, (text_x, text_y))

            # Bouton -
            if selected > 0:
                minus_rect = pygame.Rect(text_x + 350, text_y, 40, 30)
                pygame.draw.rect(self.screen, RED, minus_rect)
                minus_text = self.font_medium.render("-", True, WHITE)
                minus_text_rect = minus_text.get_rect(center=minus_rect.center)
                self.screen.blit(minus_text, minus_text_rect)

            # Bouton +
            if selected < count and selected_total < to_discard:
                plus_rect = pygame.Rect(text_x + 400, text_y, 40, 30)
                pygame.draw.rect(self.screen, GREEN, plus_rect)
                plus_text = self.font_medium.render("+", True, WHITE)
                plus_text_rect = plus_text.get_rect(center=plus_rect.center)
                self.screen.blit(plus_text, plus_text_rect)

            text_y += 40

        # Bouton de validation
        if selected_total == to_discard:
            text_y += 10
            validate_text = "Appuyez sur ENTRÉE pour valider"
            text = self.font_medium.render(validate_text, True, GREEN)
            self.screen.blit(text, (text_x, text_y))

    def _render_controls(self) -> None:
        """Affiche les contrôles."""
        if self.discard_mode:
            controls = [
                "Cliquez sur +/- pour sélectionner les cartes",
                "ENTRÉE: Valider la défausse",
            ]
        else:
            controls = [
                "ESC: Quitter",
                "N: Nouvelle partie",
                "SPACE: Tour suivant",
            ]

        y_offset = self.height - 60
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
