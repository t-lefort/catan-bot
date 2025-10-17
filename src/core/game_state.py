"""Main game state representation.

Le GameState contient l'état complet d'une partie de Catan.
Conçu pour être:
- Immutable (copie pour chaque action)
- Hashable (pour MCTS/AlphaZero)
- Sérialisable (pour sauvegarder/charger)
- Rapide à copier (copy-on-write pour les structures volumineuses)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from enum import IntEnum
import random
from copy import deepcopy

from .board import Board, Coordinate, Tile
from .player import PlayerState
from .constants import (
    DevelopmentCardType,
    ResourceType,
    BUILDING_COSTS,
    BuildingType,
    DEV_CARD_COST,
    MIN_ROAD_LENGTH_FOR_BONUS,
    MIN_ARMY_SIZE_FOR_BONUS,
    MAX_HAND_SIZE_BEFORE_DISCARD,
    BANK_TRADE_RATIO,
    PORT_GENERIC_RATIO,
    PORT_SPECIFIC_RATIO,
    DEV_CARD_DISTRIBUTION,
)

if TYPE_CHECKING:
    from .actions import Action
    from .constants import PortType


class GamePhase(IntEnum):
    """Phases du jeu."""
    SETUP = 0           # Phase d'installation (colonies + routes initiales)
    MAIN_GAME = 1       # Jeu principal
    GAME_OVER = 2       # Partie terminée


class TurnPhase(IntEnum):
    """Phases du tour."""
    ROLL_DICE = 0       # Lancer les dés
    ROBBER = 1          # Déplacer le voleur (si 7)
    DISCARD = 2         # Défausser si trop de cartes (si 7)
    MAIN = 3            # Phase principale (construire, commercer, etc.)
    END_TURN = 4        # Fin du tour


@dataclass
class GameState:
    """
    État complet du jeu.

    Contient:
    - Le plateau
    - L'état de chaque joueur
    - La phase du jeu
    - L'historique nécessaire pour les règles
    """

    # Configuration
    board: Board
    num_players: int
    victory_points_to_win: int = 10

    # État des joueurs
    players: list[PlayerState] = field(default_factory=list)
    current_player_idx: int = 0

    # Phase du jeu
    game_phase: GamePhase = GamePhase.SETUP
    turn_phase: TurnPhase = TurnPhase.ROLL_DICE

    # État de la phase de setup
    setup_settlements_placed: int = 0  # Nombre total de colonies placées en setup
    setup_roads_placed: int = 0        # Nombre total de routes placées en setup

    # Cartes développement restantes
    dev_card_deck: list[DevelopmentCardType] = field(default_factory=list)

    # État du plateau (utilise des IDs entiers pour nodes et edges)
    settlements_on_board: dict[int, int] = field(default_factory=dict)  # node_id -> player_id
    cities_on_board: dict[int, int] = field(default_factory=dict)       # node_id -> player_id
    roads_on_board: dict[int, int] = field(default_factory=dict)        # edge_id -> player_id

    # Ports (node -> type de port)
    ports: dict[int, 'PortType'] = field(default_factory=dict)  # node_id -> PortType

    # Robber position (tile_id)
    robber_tile: Optional[int] = None

    # Compteurs de tours
    turn_number: int = 0

    # Dernier jet de dés
    last_dice_roll: Optional[int] = None

    # Gagnant
    winner: Optional[int] = None

    @property
    def current_player(self) -> PlayerState:
        """Retourne le joueur actuel."""
        return self.players[self.current_player_idx]

    def is_game_over(self) -> bool:
        """Vérifie si la partie est terminée."""
        return self.game_phase == GamePhase.GAME_OVER

    def check_victory(self) -> Optional[int]:
        """Vérifie si un joueur a gagné. Retourne l'ID du gagnant ou None."""
        for player in self.players:
            if player.victory_points() >= self.victory_points_to_win:
                return player.player_id
        return None

    def next_player(self) -> None:
        """Passe au joueur suivant."""
        self.current_player_idx = (self.current_player_idx + 1) % self.num_players
        self.turn_number += 1

    def can_place_settlement(self, node_id: int, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une colonie sur un sommet (node).

        Règles:
        - Le node doit être valide (sur le plateau)
        - Le node ne doit pas avoir de construction
        - Les nodes adjacents ne doivent pas avoir de construction (règle de distance)
        - En phase principale: doit être adjacent à une route du joueur
        """
        # Vérifier que le node est valide (sur le plateau)
        if node_id not in self.board.nodes:
            return False

        # Vérifier qu'il n'y a pas déjà une construction sur ce node
        if node_id in self.settlements_on_board or node_id in self.cities_on_board:
            return False

        # Règle de distance: pas de construction sur les nodes adjacents
        for adj_node_id in self.board.get_adjacent_nodes(node_id):
            if adj_node_id in self.settlements_on_board or adj_node_id in self.cities_on_board:
                return False

        # En phase principale, doit être adjacent à une route du joueur
        if self.game_phase == GamePhase.MAIN_GAME:
            # Vérifier qu'au moins une arête adjacente appartient au joueur
            adjacent_edges = self.board.nodes_to_edges.get(node_id, [])
            if not any(self.roads_on_board.get(edge_id) == player_id for edge_id in adjacent_edges):
                return False

        return True

    def can_place_city(self, node_id: int, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une ville sur un node.

        Règles:
        - Doit y avoir une colonie du joueur
        """
        return self.settlements_on_board.get(node_id) == player_id

    def can_place_road(self, edge_id: int, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une route sur une arête (edge).

        Règles:
        - L'arête ne doit pas avoir de route
        - Doit être adjacent à une construction ou route du joueur
        """
        # Vérifier que l'edge est valide
        if edge_id not in self.board.edges:
            return False

        # Vérifier qu'il n'y a pas déjà une route
        if edge_id in self.roads_on_board:
            return False

        # Vérifier qu'une extrémité est connectée à une route ou construction du joueur
        n1, n2 = self.board.edges_to_nodes[edge_id]

        # Vérifier les constructions du joueur
        if self.settlements_on_board.get(n1) == player_id or self.settlements_on_board.get(n2) == player_id:
            return True
        if self.cities_on_board.get(n1) == player_id or self.cities_on_board.get(n2) == player_id:
            return True

        # Vérifier les routes adjacentes (routes connectées aux nodes de cette edge)
        for node_id in [n1, n2]:
            for adjacent_edge_id in self.board.nodes_to_edges.get(node_id, []):
                if self.roads_on_board.get(adjacent_edge_id) == player_id:
                    return True

        return False

    # Méthode obsolète - plus nécessaire avec le nouveau système d'IDs
    # def _edges_between(self, n1: int, n2: int) -> list[int]:
    #     """Retourne les arêtes entre deux nodes adjacents."""
    #     # Avec le nouveau système, on peut trouver l'edge directement
    #     pass

    def get_valid_actions(self) -> list[Action]:
        """
        Retourne toutes les actions valides pour le joueur actuel.

        Cette méthode est critique pour la performance (appelée des millions de fois).
        """
        from .actions import (
            RollDiceAction,
            BuildSettlementAction,
            BuildCityAction,
            BuildRoadAction,
            BuyDevCardAction,
            TradeWithBankAction,
            PlayKnightAction,
            PlayRoadBuildingAction,
            PlayYearOfPlentyAction,
            PlayMonopolyAction,
            MoveRobberAction,
            DiscardResourcesAction,
            EndTurnAction,
        )

        actions: list[Action] = []
        player = self.current_player

        # Phase de SETUP
        if self.game_phase == GamePhase.SETUP:
            # Déterminer si on place une colonie ou une route
            if self.setup_settlements_placed == self.setup_roads_placed:
                # On doit placer une colonie
                for node_id in self.board.nodes:
                    if self.can_place_settlement(node_id, self.current_player_idx):
                        actions.append(BuildSettlementAction(node_id))
            else:
                # On doit placer une route adjacente à la dernière colonie placée
                # Trouver la dernière colonie placée par ce joueur
                last_settlement_id = None
                for node_id in player.settlements:
                    last_settlement_id = node_id
                    break  # La dernière ajoutée (en Python 3.7+, sets gardent l'ordre d'insertion)

                if last_settlement_id:
                    # Générer les routes adjacentes à cette colonie
                    adjacent_edges = self.board.nodes_to_edges.get(last_settlement_id, [])
                    for edge_id in adjacent_edges:
                        if self.can_place_road(edge_id, self.current_player_idx):
                            actions.append(BuildRoadAction(edge_id))
            return actions

        # Phase de lancer de dés
        if self.turn_phase == TurnPhase.ROLL_DICE:
            actions.append(RollDiceAction())
            return actions

        # Phase de déplacement du voleur (après un 7)
        if self.turn_phase == TurnPhase.ROBBER:
            # Générer toutes les actions de déplacement du voleur
            for tile_id, tile in self.board.tiles.items():
                if tile_id != self.robber_tile and tile.is_land:
                    # Trouver les joueurs sur ce tile (exclure le joueur actuel comme victime)
                    players_on_tile = self.get_players_on_tile(tile_id)
                    players_on_tile.discard(self.current_player_idx)

                    if players_on_tile:
                        for victim_id in players_on_tile:
                            actions.append(MoveRobberAction(tile_id, victim_id))
                    else:
                        actions.append(MoveRobberAction(tile_id, None))
            return actions

        # Phase de défausse (après un 7, si trop de cartes)
        if self.turn_phase == TurnPhase.DISCARD:
            # TODO: Générer toutes les combinaisons valides de défausse
            # Pour l'instant, on passe
            return [DiscardResourcesAction({})]

        # Phase principale du tour
        if self.turn_phase == TurnPhase.MAIN:
            # Construire une colonie
            if player.can_build_settlement() and player.can_afford(
                BUILDING_COSTS[BuildingType.SETTLEMENT]
            ):
                for node_id in self.board.nodes:
                    if self.can_place_settlement(node_id, self.current_player_idx):
                        actions.append(BuildSettlementAction(node_id))

            # Construire une ville
            if player.can_build_city() and player.can_afford(
                BUILDING_COSTS[BuildingType.CITY]
            ):
                for node_id in player.settlements:
                    actions.append(BuildCityAction(node_id))

            # Construire une route
            if player.can_build_road() and player.can_afford(
                BUILDING_COSTS[BuildingType.ROAD]
            ):
                for edge_id in self.board.edges:
                    if self.can_place_road(edge_id, self.current_player_idx):
                        actions.append(BuildRoadAction(edge_id))

            # Acheter une carte développement
            if self.dev_card_deck and player.can_afford(DEV_CARD_COST):
                actions.append(BuyDevCardAction())

            # Échanger avec la banque
            for give_resource in ResourceType:
                ratio = self.get_trade_ratio(self.current_player_idx, give_resource)
                if player.resources[give_resource] >= ratio:
                    for receive_resource in ResourceType:
                        if give_resource != receive_resource:
                            actions.append(
                                TradeWithBankAction(give_resource, receive_resource, ratio)
                            )

            # Jouer des cartes développement (max 1 par tour)
            # Knight
            if (
                not player.dev_card_played_this_turn
                and player.dev_cards_in_hand.get(DevelopmentCardType.KNIGHT, 0) > 0
                and DevelopmentCardType.KNIGHT not in player.dev_cards_bought_this_turn
            ):
                for tile_id, tile in self.board.tiles.items():
                    if tile_id != self.robber_tile and tile.is_land:
                        players_on_tile = self.get_players_on_tile(tile_id)
                        players_on_tile.discard(self.current_player_idx)
                        if players_on_tile:
                            for victim_id in players_on_tile:
                                actions.append(PlayKnightAction(tile_id, victim_id))
                        else:
                            actions.append(PlayKnightAction(tile_id, None))

            # Road Building
            if (
                not player.dev_card_played_this_turn
                and player.dev_cards_in_hand.get(DevelopmentCardType.ROAD_BUILDING, 0) > 0
                and DevelopmentCardType.ROAD_BUILDING
                not in player.dev_cards_bought_this_turn
            ):
                # TODO: Générer toutes les paires de routes valides
                # Pour l'instant, on simplifie
                valid_edges = [
                    edge_id
                    for edge_id in self.board.edges
                    if self.can_place_road(edge_id, self.current_player_idx)
                ]
                for edge1_id in valid_edges[:10]:  # Limiter pour la performance
                    actions.append(PlayRoadBuildingAction(edge1_id, None))

            # Year of Plenty
            if (
                not player.dev_card_played_this_turn
                and player.dev_cards_in_hand.get(DevelopmentCardType.YEAR_OF_PLENTY, 0) > 0
                and DevelopmentCardType.YEAR_OF_PLENTY
                not in player.dev_cards_bought_this_turn
            ):
                for r1 in ResourceType:
                    for r2 in ResourceType:
                        actions.append(PlayYearOfPlentyAction(r1, r2))

            # Monopoly
            if (
                not player.dev_card_played_this_turn
                and player.dev_cards_in_hand.get(DevelopmentCardType.MONOPOLY, 0) > 0
                and DevelopmentCardType.MONOPOLY not in player.dev_cards_bought_this_turn
            ):
                for resource in ResourceType:
                    actions.append(PlayMonopolyAction(resource))

            # Toujours possible de terminer son tour
            actions.append(EndTurnAction())

        return actions

    def apply_action(self, action: Action) -> 'GameState':
        """
        Applique une action et retourne le nouvel état.

        Retourne une copie modifiée du GameState (immutabilité).
        """
        from .actions import (
            RollDiceAction,
            BuildSettlementAction,
            BuildCityAction,
            BuildRoadAction,
            BuyDevCardAction,
            TradeWithBankAction,
            PlayKnightAction,
            PlayRoadBuildingAction,
            PlayYearOfPlentyAction,
            PlayMonopolyAction,
            MoveRobberAction,
            DiscardResourcesAction,
            EndTurnAction,
        )

        # Créer une copie du state (pour l'immutabilité)
        new_state = deepcopy(self)

        # Appliquer l'action selon son type
        if isinstance(action, RollDiceAction):
            dice_roll = new_state.roll_dice()
            new_state.last_dice_roll = dice_roll

            if dice_roll == 7:
                # Vérifier si des joueurs doivent défausser
                need_discard = any(
                    p.total_resources() > MAX_HAND_SIZE_BEFORE_DISCARD
                    for p in new_state.players
                )
                if need_discard:
                    new_state.turn_phase = TurnPhase.DISCARD
                else:
                    new_state.turn_phase = TurnPhase.ROBBER
            else:
                # Distribuer les ressources
                new_state.distribute_resources(dice_roll)
                new_state.turn_phase = TurnPhase.MAIN

        elif isinstance(action, BuildSettlementAction):
            success = new_state.build_settlement(new_state.current_player_idx, action.node_id)
            # En phase SETUP, gérer la logique spéciale
            if success and new_state.game_phase == GamePhase.SETUP:
                new_state.setup_settlements_placed += 1
                # Si c'est le 2ème round (après num_players placements), donner les ressources
                if new_state.setup_settlements_placed > new_state.num_players:
                    # Donner les ressources des tuiles terrestres adjacentes
                    land_tiles = new_state.board.get_land_tiles_for_node(action.node_id)
                    for tile in land_tiles:
                        resource = tile.resource
                        if resource is not None:
                            new_state.current_player.resources[resource] += 1

        elif isinstance(action, BuildCityAction):
            new_state.build_city(new_state.current_player_idx, action.node_id)

        elif isinstance(action, BuildRoadAction):
            success = new_state.build_road(new_state.current_player_idx, action.edge_id)
            # En phase SETUP, gérer la transition de joueur
            if success and new_state.game_phase == GamePhase.SETUP:
                new_state.setup_roads_placed += 1

                # Vérifier si on termine la phase de setup
                if new_state.setup_roads_placed >= new_state.num_players * 2:
                    new_state.game_phase = GamePhase.MAIN_GAME
                    new_state.turn_phase = TurnPhase.ROLL_DICE
                else:
                    # Passer au joueur suivant
                    # Premier round (rounds 0 à num_players-1): ordre normal
                    # Deuxième round (rounds num_players à 2*num_players-1): ordre inversé
                    if new_state.setup_roads_placed < new_state.num_players:
                        # Premier round: ordre croissant
                        new_state.next_player()
                    elif new_state.setup_roads_placed == new_state.num_players:
                        # Transition: le dernier joueur du round 1 joue à nouveau
                        pass  # Ne rien faire, même joueur
                    else:
                        # Deuxième round: ordre décroissant
                        new_state.current_player_idx = (new_state.current_player_idx - 1) % new_state.num_players

        elif isinstance(action, BuyDevCardAction):
            new_state.buy_dev_card(new_state.current_player_idx)

        elif isinstance(action, TradeWithBankAction):
            new_state.trade_with_bank(
                new_state.current_player_idx,
                action.give,
                action.receive,
                action.amount,
            )

        elif isinstance(action, PlayKnightAction):
            new_state.play_knight(
                new_state.current_player_idx,
                action.new_robber_tile,
                action.steal_from_player,
            )

        elif isinstance(action, PlayRoadBuildingAction):
            new_state.play_road_building(
                new_state.current_player_idx, action.edge1_id, action.edge2_id
            )

        elif isinstance(action, PlayYearOfPlentyAction):
            new_state.play_year_of_plenty(
                new_state.current_player_idx, action.resource1, action.resource2
            )

        elif isinstance(action, PlayMonopolyAction):
            new_state.play_monopoly(new_state.current_player_idx, action.resource)

        elif isinstance(action, MoveRobberAction):
            moved = new_state.move_robber(action.new_tile_id)
            if moved:
                if action.steal_from_player is not None:
                    new_state.steal_resource_from_player(
                        action.steal_from_player, new_state.current_player_idx
                    )
                new_state.turn_phase = TurnPhase.MAIN

        elif isinstance(action, DiscardResourcesAction):
            # Défausser les ressources
            player = new_state.current_player
            for resource, amount in action.resources.items():
                player.resources[resource] -= amount
            # TODO: Gérer le cas multi-joueurs
            new_state.turn_phase = TurnPhase.ROBBER

        elif isinstance(action, EndTurnAction):
            # Réinitialiser les cartes achetées ce tour
            new_state.current_player.dev_cards_bought_this_turn.clear()
            # Réinitialiser le flag de carte développement jouée ce tour
            new_state.current_player.dev_card_played_this_turn = False

            # Passer au joueur suivant
            new_state.next_player()
            new_state.turn_phase = TurnPhase.ROLL_DICE

            # Vérifier la victoire
            winner = new_state.check_victory()
            if winner is not None:
                new_state.winner = winner
                new_state.game_phase = GamePhase.GAME_OVER

        return new_state

    def roll_dice(self) -> int:
        """Lance deux dés et retourne leur somme."""
        return random.randint(1, 6) + random.randint(1, 6)

    def distribute_resources(self, dice_roll: int) -> None:
        """
        Distribue les ressources basées sur le jet de dés.

        Pour chaque hexagone avec le numéro correspondant:
        - Chaque colonie adjacente reçoit 1 ressource
        - Chaque ville adjacente reçoit 2 ressources
        """
        if dice_roll == 7:
            # Pas de distribution si on fait 7
            return

        # Récupérer tous les tiles qui produisent pour ce jet
        producing_tiles = self.board.get_tiles_for_roll(dice_roll, self.robber_tile)

        for tile in producing_tiles:
            if tile.resource is None:
                continue

            # Trouver tous les nodes (vertices) de ce tile via nodes_to_tiles
            # Pour chaque node du board, vérifier s'il est adjacent à ce tile
            for node_id in self.board.nodes:
                adjacent_tiles = self.board.get_tiles_for_node(node_id)
                if tile not in adjacent_tiles:
                    continue

                # Vérifier s'il y a une colonie
                if node_id in self.settlements_on_board:
                    player_id = self.settlements_on_board[node_id]
                    self.players[player_id].resources[tile.resource] += 1

                # Vérifier s'il y a une ville (2 ressources)
                elif node_id in self.cities_on_board:
                    player_id = self.cities_on_board[node_id]
                    self.players[player_id].resources[tile.resource] += 2

    def can_place_robber(self, new_tile_id: int) -> bool:
        """Vérifie si le voleur peut être placé sur ce tile.

        Règle ajoutée: on ne peut pas placer le voleur sur une case adjacente
        à un joueur qui n'a que 2 colonies.
        """
        # Le tile doit exister
        if new_tile_id not in self.board.tiles:
            return False

        # Le tile doit être une terre (pas de l'eau)
        if not self.board.tiles[new_tile_id].is_land:
            return False

        # Ne pas remettre le voleur au même endroit
        if new_tile_id == self.robber_tile:
            return False

        # Récupérer les joueurs adjacents au tile
        players_on_tile = self.get_players_on_tile(new_tile_id)

        # Interdire si au moins un joueur adjacent n'a que 2 colonies
        for pid in players_on_tile:
            if len(self.players[pid].settlements) == 2:
                return False

        return True

    def move_robber(self, new_tile_id: int) -> bool:
        """Déplace le voleur sur un nouveau tile. Retourne True si réussi."""
        if not self.can_place_robber(new_tile_id):
            return False

        # Mettre à jour la position du voleur
        self.robber_tile = new_tile_id
        return True

    def get_players_on_tile(self, tile_id: int) -> set[int]:
        """Retourne les IDs des joueurs ayant une construction sur un tile donné."""
        players = set()

        # Trouver tous les nodes adjacents à ce tile
        for node_id in self.board.nodes:
            adjacent_tiles = self.board.get_tiles_for_node(node_id)
            tile_ids = [t.id for t in adjacent_tiles]

            if tile_id not in tile_ids:
                continue

            # Vérifier si ce node a une colonie ou ville
            if node_id in self.settlements_on_board:
                players.add(self.settlements_on_board[node_id])
            elif node_id in self.cities_on_board:
                players.add(self.cities_on_board[node_id])

        return players

    def has_valid_placements(self, player_id: int, building_type: str) -> bool:
        """
        Vérifie s'il existe au moins un emplacement valide pour un type de construction.

        Args:
            player_id: ID du joueur
            building_type: "settlement", "road", ou "city"

        Returns:
            True s'il existe au moins un emplacement valide
        """
        player = self.players[player_id]

        if building_type == "settlement":
            # En phase de setup, vérifier tous les nodes
            if self.game_phase == GamePhase.SETUP:
                for node_id in self.board.nodes:
                    if self.can_place_settlement(node_id, player_id):
                        return True
                return False

            # En phase principale, vérifier les nodes près des routes
            for edge_id in player.roads:
                n1, n2 = self.board.edges_to_nodes[edge_id]
                if self.can_place_settlement(n1, player_id):
                    return True
                if self.can_place_settlement(n2, player_id):
                    return True
            return False

        elif building_type == "road":
            # En phase de setup, vérifier seulement les routes adjacentes à la dernière colonie
            if self.game_phase == GamePhase.SETUP:
                last_settlement_id = None
                for node_id in player.settlements:
                    last_settlement_id = node_id
                    break
                if last_settlement_id:
                    # Trouver les edges adjacents à ce node
                    adjacent_edges = self.board.nodes_to_edges.get(last_settlement_id, [])
                    for edge_id in adjacent_edges:
                        if self.can_place_road(edge_id, player_id):
                            return True
                return False

            # En phase principale, vérifier les routes adjacentes aux routes existantes
            for edge_id in player.roads:
                # Obtenir les deux nodes de cette edge
                n1, n2 = self.board.edges_to_nodes[edge_id]
                # Vérifier les edges adjacentes à ces nodes
                for adjacent_edge in self.board.nodes_to_edges.get(n1, []):
                    if self.can_place_road(adjacent_edge, player_id):
                        return True
                for adjacent_edge in self.board.nodes_to_edges.get(n2, []):
                    if self.can_place_road(adjacent_edge, player_id):
                        return True

            # Vérifier les routes adjacentes aux colonies/villes
            for node_id in player.settlements.union(player.cities):
                adjacent_edges = self.board.nodes_to_edges.get(node_id, [])
                for edge_id in adjacent_edges:
                    if self.can_place_road(edge_id, player_id):
                        return True
            return False

        elif building_type == "city":
            # Il suffit d'avoir au moins une colonie
            return len(player.settlements) > 0

        return False

    def steal_resource_from_player(self, victim_id: int, thief_id: int) -> Optional[ResourceType]:
        """
        Vole une ressource aléatoire d'un joueur.
        Retourne la ressource volée ou None si le joueur n'a pas de ressources.
        """
        victim = self.players[victim_id]
        thief = self.players[thief_id]

        if victim.total_resources() == 0:
            return None

        # Construire une liste de toutes les ressources disponibles
        available_resources = []
        for resource in ResourceType:
            count = victim.resources[resource]
            available_resources.extend([resource] * count)

        # Choisir une ressource aléatoire
        stolen_resource = random.choice(available_resources)

        # Transférer la ressource
        victim.resources[stolen_resource] -= 1
        thief.resources[stolen_resource] += 1

        return stolen_resource

    def update_longest_road(self) -> None:
        """Met à jour le bonus de la route la plus longue."""
        max_length = MIN_ROAD_LENGTH_FOR_BONUS - 1
        player_with_longest = None

        for player in self.players:
            length = player.longest_road_length(self.board)
            if length > max_length:
                max_length = length
                player_with_longest = player.player_id

        # Retirer le bonus de tous les joueurs
        for player in self.players:
            player.has_longest_road = False

        # Donner le bonus au joueur avec la plus longue route
        if player_with_longest is not None:
            self.players[player_with_longest].has_longest_road = True

    def update_largest_army(self) -> None:
        """Met à jour le bonus de l'armée la plus grande."""
        max_knights = MIN_ARMY_SIZE_FOR_BONUS - 1
        player_with_largest = None

        for player in self.players:
            if player.knights_played > max_knights:
                max_knights = player.knights_played
                player_with_largest = player.player_id

        # Retirer le bonus de tous les joueurs
        for player in self.players:
            player.has_largest_army = False

        # Donner le bonus au joueur avec la plus grande armée
        if player_with_largest is not None:
            self.players[player_with_largest].has_largest_army = True

    def build_settlement(self, player_id: int, node_id: int) -> bool:
        """
        Construit une colonie pour un joueur.
        Retourne True si la construction a réussi, False sinon.
        """
        player = self.players[player_id]

        # Vérifier que le joueur peut construire
        if not player.can_build_settlement():
            return False

        # Vérifier que le placement est valide
        if not self.can_place_settlement(node_id, player_id):
            return False

        # Vérifier que le joueur peut payer (sauf en phase de setup)
        if self.game_phase == GamePhase.MAIN_GAME:
            if not player.can_afford(BUILDING_COSTS[BuildingType.SETTLEMENT]):
                return False
            player.pay(BUILDING_COSTS[BuildingType.SETTLEMENT])

        # Construire la colonie
        self.settlements_on_board[node_id] = player_id
        player.settlements.add(node_id)

        return True

    def build_city(self, player_id: int, node_id: int) -> bool:
        """
        Améliore une colonie en ville.
        Retourne True si la construction a réussi, False sinon.
        """
        player = self.players[player_id]

        # Vérifier que le joueur peut construire
        if not player.can_build_city():
            return False

        # Vérifier que le placement est valide
        if not self.can_place_city(node_id, player_id):
            return False

        # Vérifier que le joueur peut payer
        if not player.can_afford(BUILDING_COSTS[BuildingType.CITY]):
            return False

        player.pay(BUILDING_COSTS[BuildingType.CITY])

        # Améliorer la colonie en ville
        if node_id in self.settlements_on_board and self.settlements_on_board[node_id] == player_id:
            del self.settlements_on_board[node_id]
            self.cities_on_board[node_id] = player_id

            player.settlements.remove(node_id)
            player.cities.add(node_id)

            return True

        return False

    def build_road(self, player_id: int, edge_id: int) -> bool:
        """
        Construit une route pour un joueur.
        Retourne True si la construction a réussi, False sinon.
        """
        player = self.players[player_id]

        # Vérifier que le joueur peut construire
        if not player.can_build_road():
            return False

        # Vérifier que le placement est valide
        if not self.can_place_road(edge_id, player_id):
            return False

        # Vérifier que le joueur peut payer (sauf en phase de setup)
        if self.game_phase == GamePhase.MAIN_GAME:
            if not player.can_afford(BUILDING_COSTS[BuildingType.ROAD]):
                return False
            player.pay(BUILDING_COSTS[BuildingType.ROAD])

        # Construire la route
        self.roads_on_board[edge_id] = player_id
        player.roads.add(edge_id)

        # Mettre à jour la route la plus longue
        self.update_longest_road()

        return True

    def buy_dev_card(self, player_id: int) -> Optional[DevelopmentCardType]:
        """
        Achète une carte développement.
        Retourne la carte achetée ou None si impossible.
        """
        player = self.players[player_id]

        # Vérifier qu'il reste des cartes
        if not self.dev_card_deck:
            return None

        # Vérifier que le joueur peut payer
        if not player.can_afford(DEV_CARD_COST):
            return None

        player.pay(DEV_CARD_COST)

        # Piocher une carte aléatoire
        card = self.dev_card_deck.pop()
        player.dev_cards_in_hand[card] = player.dev_cards_in_hand.get(card, 0) + 1
        player.dev_cards_bought_this_turn.append(card)

        return card

    def get_player_ports(self, player_id: int) -> set[PortType]:
        """Retourne les types de ports accessibles à un joueur."""
        player = self.players[player_id]
        accessible_ports: set[PortType] = set()

        # Vérifier toutes les colonies et villes du joueur
        for node_id in player.settlements.union(player.cities):
            # Vérifier si ce node a un port
            if node_id in self.ports:
                accessible_ports.add(self.ports[node_id])

        return accessible_ports

    def get_trade_ratio(self, player_id: int, resource: ResourceType) -> int:
        """
        Retourne le meilleur ratio d'échange pour une ressource donnée.

        Retourne 2 si le joueur a un port spécialisé pour cette ressource,
        3 si le joueur a un port générique,
        4 sinon (échange avec la banque).
        """
        from .constants import PortType

        ports = self.get_player_ports(player_id)

        # Vérifier les ports spécialisés
        resource_port_map = {
            ResourceType.WOOD: PortType.WOOD,
            ResourceType.BRICK: PortType.BRICK,
            ResourceType.SHEEP: PortType.SHEEP,
            ResourceType.WHEAT: PortType.WHEAT,
            ResourceType.ORE: PortType.ORE,
        }

        if resource_port_map[resource] in ports:
            return PORT_SPECIFIC_RATIO

        # Vérifier le port générique
        if PortType.GENERIC in ports:
            return PORT_GENERIC_RATIO

        # Échange avec la banque par défaut
        return BANK_TRADE_RATIO

    def trade_with_bank(
        self, player_id: int, give: ResourceType, receive: ResourceType, amount: int
    ) -> bool:
        """
        Effectue un échange avec la banque ou un port.

        Args:
            player_id: ID du joueur
            give: ressource à donner
            receive: ressource à recevoir
            amount: nombre de ressources à donner

        Returns:
            True si l'échange a réussi, False sinon
        """
        player = self.players[player_id]

        # Vérifier que le joueur a assez de ressources
        if player.resources[give] < amount:
            return False

        # Vérifier que le ratio est valide
        required_ratio = self.get_trade_ratio(player_id, give)
        if amount != required_ratio:
            return False

        # Effectuer l'échange
        player.resources[give] -= amount
        player.resources[receive] += 1

        return True

    def play_knight(
        self, player_id: int, new_robber_tile: int, steal_from: Optional[int]
    ) -> bool:
        """
        Joue une carte Chevalier.

        Returns:
            True si la carte a été jouée avec succès, False sinon
        """
        player = self.players[player_id]

        # Vérifier que le joueur a une carte Chevalier
        if player.dev_cards_in_hand.get(DevelopmentCardType.KNIGHT, 0) == 0:
            return False

        # Vérifier que la carte n'a pas été achetée ce tour
        if DevelopmentCardType.KNIGHT in player.dev_cards_bought_this_turn:
            return False

        # Jouer la carte
        player.dev_cards_in_hand[DevelopmentCardType.KNIGHT] -= 1
        player.dev_cards_played[DevelopmentCardType.KNIGHT] = (
            player.dev_cards_played.get(DevelopmentCardType.KNIGHT, 0) + 1
        )
        player.knights_played += 1
        player.dev_card_played_this_turn = True

        # Déplacer le voleur (respecter les règles de placement)
        if not self.can_place_robber(new_robber_tile):
            return False
        self.move_robber(new_robber_tile)

        # Voler une ressource si spécifié
        if steal_from is not None:
            self.steal_resource_from_player(steal_from, player_id)

        # Mettre à jour l'armée la plus grande
        self.update_largest_army()

        return True

    def play_road_building(
        self, player_id: int, edge1_id: int, edge2_id: Optional[int]
    ) -> bool:
        """
        Joue une carte Construction de routes.

        Returns:
            True si la carte a été jouée avec succès, False sinon
        """
        player = self.players[player_id]

        # Vérifier qu'une carte développement n'a pas déjà été jouée ce tour
        if player.dev_card_played_this_turn:
            return False

        # Vérifier que le joueur a la carte
        if player.dev_cards_in_hand.get(DevelopmentCardType.ROAD_BUILDING, 0) == 0:
            return False

        # Vérifier que la carte n'a pas été achetée ce tour
        if DevelopmentCardType.ROAD_BUILDING in player.dev_cards_bought_this_turn:
            return False

        # Jouer la carte
        player.dev_cards_in_hand[DevelopmentCardType.ROAD_BUILDING] -= 1
        player.dev_cards_played[DevelopmentCardType.ROAD_BUILDING] = (
            player.dev_cards_played.get(DevelopmentCardType.ROAD_BUILDING, 0) + 1
        )
        player.dev_card_played_this_turn = True

        # Construire les routes (gratuitement)
        if not self.can_place_road(edge1_id, player_id):
            return False

        self.roads_on_board[edge1_id] = player_id
        player.roads.add(edge1_id)

        if edge2_id is not None:
            if not self.can_place_road(edge2_id, player_id):
                # Annuler la première route
                del self.roads_on_board[edge1_id]
                player.roads.remove(edge1_id)
                return False

            self.roads_on_board[edge2_id] = player_id
            player.roads.add(edge2_id)

        # Mettre à jour la route la plus longue
        self.update_longest_road()

        return True

    def play_year_of_plenty(
        self, player_id: int, resource1: ResourceType, resource2: ResourceType
    ) -> bool:
        """
        Joue une carte Invention (Year of Plenty).

        Returns:
            True si la carte a été jouée avec succès, False sinon
        """
        player = self.players[player_id]

        # Vérifier qu'une carte développement n'a pas déjà été jouée ce tour
        if player.dev_card_played_this_turn:
            return False

        # Vérifier que le joueur a la carte
        if player.dev_cards_in_hand.get(DevelopmentCardType.YEAR_OF_PLENTY, 0) == 0:
            return False

        # Vérifier que la carte n'a pas été achetée ce tour
        if DevelopmentCardType.YEAR_OF_PLENTY in player.dev_cards_bought_this_turn:
            return False

        # Jouer la carte
        player.dev_cards_in_hand[DevelopmentCardType.YEAR_OF_PLENTY] -= 1
        player.dev_cards_played[DevelopmentCardType.YEAR_OF_PLENTY] = (
            player.dev_cards_played.get(DevelopmentCardType.YEAR_OF_PLENTY, 0) + 1
        )
        player.dev_card_played_this_turn = True

        # Recevoir les ressources
        player.resources[resource1] += 1
        player.resources[resource2] += 1

        return True

    def play_monopoly(self, player_id: int, resource: ResourceType) -> int:
        """
        Joue une carte Monopole.

        Returns:
            Le nombre de ressources volées, ou -1 si la carte ne peut pas être jouée
        """
        player = self.players[player_id]

        # Vérifier qu'une carte développement n'a pas déjà été jouée ce tour
        if player.dev_card_played_this_turn:
            return -1

        # Vérifier que le joueur a la carte
        if player.dev_cards_in_hand.get(DevelopmentCardType.MONOPOLY, 0) == 0:
            return -1

        # Vérifier que la carte n'a pas été achetée ce tour
        if DevelopmentCardType.MONOPOLY in player.dev_cards_bought_this_turn:
            return -1

        # Jouer la carte
        player.dev_cards_in_hand[DevelopmentCardType.MONOPOLY] -= 1
        player.dev_cards_played[DevelopmentCardType.MONOPOLY] = (
            player.dev_cards_played.get(DevelopmentCardType.MONOPOLY, 0) + 1
        )
        player.dev_card_played_this_turn = True

        # Voler toutes les ressources de ce type aux autres joueurs
        total_stolen = 0
        for other_player in self.players:
            if other_player.player_id != player_id:
                stolen = other_player.resources[resource]
                other_player.resources[resource] = 0
                player.resources[resource] += stolen
                total_stolen += stolen

        return total_stolen

    @staticmethod
    def create_initial_dev_card_deck() -> list[DevelopmentCardType]:
        """Crée et mélange le paquet initial de cartes développement."""
        deck = []
        for card_type, count in DEV_CARD_DISTRIBUTION.items():
            deck.extend([card_type] * count)
        random.shuffle(deck)
        return deck

    @staticmethod
    def create_default_ports() -> dict[int, 'PortType']:
        """Crée les ports aux positions standard de Catan.

        TODO: Cette méthode doit être refactorisée pour utiliser les node IDs.
        Pour l'instant, elle retourne un dict vide.
        Les ports seront gérés directement dans Board.create_standard_board()
        une fois que le système de water tiles + ports sera implémenté.

        Distribution standard:
        - 4 ports génériques (3:1)
        - 5 ports spécialisés (2:1 pour chaque ressource)
        """
        # TODO: Implémenter la logique de création des ports avec le nouveau système
        # Pour l'instant, retourner un dict vide pour permettre la compilation
        return {}

    @classmethod
    def create_new_game(cls, num_players: int = 4, shuffle_board: bool = True) -> 'GameState':
        """
        Crée un nouveau jeu de Catan.

        Args:
            num_players: Nombre de joueurs (2-4)
            shuffle_board: Si True, mélange le plateau

        Returns:
            Un nouvel état de jeu initialisé
        """
        # Créer le plateau
        board = Board.create_standard_board(shuffle=shuffle_board)

        # Créer les joueurs
        players = [PlayerState(player_id=i) for i in range(num_players)]

        # Créer le paquet de cartes développement
        dev_card_deck = cls.create_initial_dev_card_deck()

        # Créer une disposition par défaut de ports
        default_ports = cls.create_default_ports()

        # Créer l'état du jeu
        game_state = cls(
            board=board,
            num_players=num_players,
            players=players,
            dev_card_deck=dev_card_deck,
            ports=default_ports,
            game_phase=GamePhase.SETUP,
            turn_phase=TurnPhase.ROLL_DICE,
        )

        return game_state

    def __repr__(self) -> str:
        return (
            f"GameState(turn={self.turn_number}, "
            f"phase={self.game_phase.name}, "
            f"current_player={self.current_player_idx}, "
            f"winner={self.winner})"
        )
