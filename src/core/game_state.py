"""Main game state representation.

Le GameState contient l'état complet d'une partie de Catan.
Conçu pour être:
- Immutable (copie pour chaque action)
- Hashable (pour MCTS/AlphaZero)
- Sérialisable (pour sauvegarder/charger)
- Rapide à copier (copy-on-write pour les structures volumineuses)
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import IntEnum, auto
import numpy as np
import random
from copy import deepcopy

from .board import Board, VertexCoord, EdgeCoord, HexCoord
from .player import PlayerState
from .constants import (
    DevelopmentCardType,
    ResourceType,
    BUILDING_COSTS,
    BuildingType,
    DEV_CARD_COST,
    LONGEST_ROAD_VP,
    LARGEST_ARMY_VP,
    MIN_ROAD_LENGTH_FOR_BONUS,
    MIN_ARMY_SIZE_FOR_BONUS,
    MAX_HAND_SIZE_BEFORE_DISCARD,
    BANK_TRADE_RATIO,
    PORT_GENERIC_RATIO,
    PORT_SPECIFIC_RATIO,
    DEV_CARD_DISTRIBUTION,
)


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

    # Cartes développement restantes
    dev_card_deck: list[DevelopmentCardType] = field(default_factory=list)

    # État du plateau
    settlements_on_board: dict[VertexCoord, int] = field(default_factory=dict)
    cities_on_board: dict[VertexCoord, int] = field(default_factory=dict)
    roads_on_board: dict[EdgeCoord, int] = field(default_factory=dict)

    # Ports (vertex -> type de port)
    ports: dict[VertexCoord, 'PortType'] = field(default_factory=dict)

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

    def can_place_settlement(self, vertex: VertexCoord, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une colonie sur un sommet.

        Règles:
        - Le sommet ne doit pas avoir de construction
        - Les sommets adjacents ne doivent pas avoir de construction (règle de distance)
        - En phase principale: doit être adjacent à une route du joueur
        """
        # Vérifier qu'il n'y a pas déjà une construction
        if vertex in self.settlements_on_board or vertex in self.cities_on_board:
            return False

        # Règle de distance: pas de construction sur les sommets adjacents
        for adj_vertex in vertex.adjacent_vertices():
            if adj_vertex in self.settlements_on_board or adj_vertex in self.cities_on_board:
                return False

        # En phase principale, doit être adjacent à une route du joueur
        if self.game_phase == GamePhase.MAIN_GAME:
            player = self.players[player_id]
            # Vérifier qu'au moins une route adjacente appartient au joueur
            adjacent_edges = [
                edge for v1 in vertex.adjacent_vertices()
                for edge in self._edges_between(vertex, v1)
            ]
            if not any(edge in player.roads for edge in adjacent_edges):
                return False

        return True

    def can_place_city(self, vertex: VertexCoord, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une ville sur un sommet.

        Règles:
        - Doit y avoir une colonie du joueur
        """
        return (
            vertex in self.settlements_on_board
            and self.settlements_on_board[vertex] == player_id
        )

    def can_place_road(self, edge: EdgeCoord, player_id: int) -> bool:
        """
        Vérifie si un joueur peut placer une route sur une arête.

        Règles:
        - L'arête ne doit pas avoir de route
        - Doit être adjacent à une construction ou route du joueur
        """
        # Vérifier qu'il n'y a pas déjà une route
        if edge in self.roads_on_board:
            return False

        player = self.players[player_id]

        # Vérifier qu'une extrémité est connectée à une route ou construction du joueur
        v1, v2 = edge.vertices()

        # Vérifier les constructions du joueur
        if v1 in player.settlements or v1 in player.cities:
            return True
        if v2 in player.settlements or v2 in player.cities:
            return True

        # Vérifier les routes adjacentes
        for adj_edge in edge.adjacent_edges():
            if adj_edge in player.roads:
                return True

        return False

    def _edges_between(self, v1: VertexCoord, v2: VertexCoord) -> list[EdgeCoord]:
        """Retourne les arêtes entre deux sommets adjacents."""
        # Obtenir toutes les arêtes possibles des hexagones communs
        edges = []

        # Pour chaque hexagone du premier sommet
        for hex1 in v1.adjacent_hexes():
            # Vérifier chaque direction
            for direction in range(6):
                edge = EdgeCoord(hex1, direction)
                # Vérifier si cette arête connecte les deux sommets
                edge_v1, edge_v2 = edge.vertices()
                if (edge_v1 == v1 and edge_v2 == v2) or (edge_v1 == v2 and edge_v2 == v1):
                    edges.append(edge)

        return edges

    def get_valid_actions(self) -> list['Action']:
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

        actions = []
        player = self.current_player

        # Phase de lancer de dés
        if self.turn_phase == TurnPhase.ROLL_DICE:
            actions.append(RollDiceAction())
            return actions

        # Phase de déplacement du voleur (après un 7)
        if self.turn_phase == TurnPhase.ROBBER:
            # Générer toutes les actions de déplacement du voleur
            for hex_coord in self.board.hexes:
                hex = self.board.hexes[hex_coord]
                if not hex.has_robber:  # Ne pas remettre le voleur au même endroit
                    # Trouver les joueurs sur cet hexagone
                    players_on_hex = self.get_players_on_hex(hex_coord)
                    players_on_hex.discard(self.current_player_idx)

                    if players_on_hex:
                        for victim_id in players_on_hex:
                            actions.append(MoveRobberAction(hex_coord, victim_id))
                    else:
                        actions.append(MoveRobberAction(hex_coord, None))
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
                for vertex in self.board.vertices:
                    if self.can_place_settlement(vertex, self.current_player_idx):
                        actions.append(BuildSettlementAction(vertex))

            # Construire une ville
            if player.can_build_city() and player.can_afford(
                BUILDING_COSTS[BuildingType.CITY]
            ):
                for vertex in player.settlements:
                    actions.append(BuildCityAction(vertex))

            # Construire une route
            if player.can_build_road() and player.can_afford(
                BUILDING_COSTS[BuildingType.ROAD]
            ):
                for edge in self.board.edges:
                    if self.can_place_road(edge, self.current_player_idx):
                        actions.append(BuildRoadAction(edge))

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
                for hex_coord in self.board.hexes:
                    hex = self.board.hexes[hex_coord]
                    if not hex.has_robber:
                        players_on_hex = self.get_players_on_hex(hex_coord)
                        players_on_hex.discard(self.current_player_idx)
                        if players_on_hex:
                            for victim_id in players_on_hex:
                                actions.append(PlayKnightAction(hex_coord, victim_id))
                        else:
                            actions.append(PlayKnightAction(hex_coord, None))

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
                    edge
                    for edge in self.board.edges
                    if self.can_place_road(edge, self.current_player_idx)
                ]
                for edge1 in valid_edges[:10]:  # Limiter pour la performance
                    actions.append(PlayRoadBuildingAction(edge1, None))

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

    def apply_action(self, action: 'Action') -> 'GameState':
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
            new_state.build_settlement(new_state.current_player_idx, action.vertex)

        elif isinstance(action, BuildCityAction):
            new_state.build_city(new_state.current_player_idx, action.vertex)

        elif isinstance(action, BuildRoadAction):
            new_state.build_road(new_state.current_player_idx, action.edge)

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
                action.new_robber_hex,
                action.steal_from_player,
            )

        elif isinstance(action, PlayRoadBuildingAction):
            new_state.play_road_building(
                new_state.current_player_idx, action.edge1, action.edge2
            )

        elif isinstance(action, PlayYearOfPlentyAction):
            new_state.play_year_of_plenty(
                new_state.current_player_idx, action.resource1, action.resource2
            )

        elif isinstance(action, PlayMonopolyAction):
            new_state.play_monopoly(new_state.current_player_idx, action.resource)

        elif isinstance(action, MoveRobberAction):
            new_state.move_robber(action.new_hex)
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

        # Récupérer tous les hexagones qui produisent pour ce jet
        producing_hexes = self.board.get_hexes_for_roll(dice_roll)

        for hex in producing_hexes:
            resource = hex.produces_resource()
            if resource is None:
                continue

            # Trouver tous les sommets de cet hexagone
            for direction in range(6):
                vertex = VertexCoord(hex.coord, direction)

                # Vérifier s'il y a une colonie
                if vertex in self.settlements_on_board:
                    player_id = self.settlements_on_board[vertex]
                    self.players[player_id].resources[resource] += 1

                # Vérifier s'il y a une ville (2 ressources)
                elif vertex in self.cities_on_board:
                    player_id = self.cities_on_board[vertex]
                    self.players[player_id].resources[resource] += 2

    def move_robber(self, new_hex: HexCoord) -> None:
        """Déplace le voleur sur un nouveau hexagone."""
        # Retirer le voleur de son hexagone actuel
        for hex in self.board.hexes.values():
            hex.has_robber = False

        # Placer le voleur sur le nouveau hexagone
        if new_hex in self.board.hexes:
            self.board.hexes[new_hex].has_robber = True

    def get_players_on_hex(self, hex_coord: HexCoord) -> set[int]:
        """Retourne les IDs des joueurs ayant une construction sur un hexagone donné."""
        players = set()

        for direction in range(6):
            vertex = VertexCoord(hex_coord, direction)

            if vertex in self.settlements_on_board:
                players.add(self.settlements_on_board[vertex])
            elif vertex in self.cities_on_board:
                players.add(self.cities_on_board[vertex])

        return players

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
            length = player.longest_road_length()
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

    def build_settlement(self, player_id: int, vertex: VertexCoord) -> bool:
        """
        Construit une colonie pour un joueur.
        Retourne True si la construction a réussi, False sinon.
        """
        player = self.players[player_id]

        # Vérifier que le joueur peut construire
        if not player.can_build_settlement():
            return False

        # Vérifier que le placement est valide
        if not self.can_place_settlement(vertex, player_id):
            return False

        # Vérifier que le joueur peut payer (sauf en phase de setup)
        if self.game_phase == GamePhase.MAIN_GAME:
            if not player.can_afford(BUILDING_COSTS[BuildingType.SETTLEMENT]):
                return False
            player.pay(BUILDING_COSTS[BuildingType.SETTLEMENT])

        # Construire la colonie
        self.settlements_on_board[vertex] = player_id
        player.settlements.add(vertex)

        return True

    def build_city(self, player_id: int, vertex: VertexCoord) -> bool:
        """
        Améliore une colonie en ville.
        Retourne True si la construction a réussi, False sinon.
        """
        player = self.players[player_id]

        # Vérifier que le joueur peut construire
        if not player.can_build_city():
            return False

        # Vérifier que le placement est valide
        if not self.can_place_city(vertex, player_id):
            return False

        # Vérifier que le joueur peut payer
        if not player.can_afford(BUILDING_COSTS[BuildingType.CITY]):
            return False

        player.pay(BUILDING_COSTS[BuildingType.CITY])

        # Améliorer la colonie en ville
        del self.settlements_on_board[vertex]
        self.cities_on_board[vertex] = player_id

        player.settlements.remove(vertex)
        player.cities.add(vertex)

        return True

    def build_road(self, player_id: int, edge: EdgeCoord) -> bool:
        """
        Construit une route pour un joueur.
        Retourne True si la construction a réussi, False sinon.
        """
        player = self.players[player_id]

        # Vérifier que le joueur peut construire
        if not player.can_build_road():
            return False

        # Vérifier que le placement est valide
        if not self.can_place_road(edge, player_id):
            return False

        # Vérifier que le joueur peut payer (sauf en phase de setup)
        if self.game_phase == GamePhase.MAIN_GAME:
            if not player.can_afford(BUILDING_COSTS[BuildingType.ROAD]):
                return False
            player.pay(BUILDING_COSTS[BuildingType.ROAD])

        # Construire la route
        self.roads_on_board[edge] = player_id
        player.roads.add(edge)

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

    def get_player_ports(self, player_id: int) -> set['PortType']:
        """Retourne les types de ports accessibles à un joueur."""
        from .constants import PortType

        player = self.players[player_id]
        accessible_ports = set()

        # Vérifier toutes les colonies et villes du joueur
        for vertex in player.settlements.union(player.cities):
            if vertex in self.ports:
                accessible_ports.add(self.ports[vertex])

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
        self, player_id: int, new_robber_hex: HexCoord, steal_from: Optional[int]
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

        # Déplacer le voleur
        self.move_robber(new_robber_hex)

        # Voler une ressource si spécifié
        if steal_from is not None:
            self.steal_resource_from_player(steal_from, player_id)

        # Mettre à jour l'armée la plus grande
        self.update_largest_army()

        return True

    def play_road_building(
        self, player_id: int, edge1: EdgeCoord, edge2: Optional[EdgeCoord]
    ) -> bool:
        """
        Joue une carte Construction de routes.

        Returns:
            True si la carte a été jouée avec succès, False sinon
        """
        player = self.players[player_id]

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
        if not self.can_place_road(edge1, player_id):
            return False

        self.roads_on_board[edge1] = player_id
        player.roads.add(edge1)

        if edge2 is not None:
            if not self.can_place_road(edge2, player_id):
                # Annuler la première route
                del self.roads_on_board[edge1]
                player.roads.remove(edge1)
                return False

            self.roads_on_board[edge2] = player_id
            player.roads.add(edge2)

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

        # Créer l'état du jeu
        game_state = cls(
            board=board,
            num_players=num_players,
            players=players,
            dev_card_deck=dev_card_deck,
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
