"""Tests for the GameState class and game mechanics."""

import pytest
from src.core.game_state import GameState, GamePhase, TurnPhase
from src.core.board import Board, HexCoord, VertexCoord, EdgeCoord
from src.core.player import PlayerState
from src.core.constants import ResourceType, BuildingType, DevelopmentCardType
from src.core.actions import (
    RollDiceAction,
    BuildSettlementAction,
    BuildRoadAction,
    EndTurnAction,
)


class TestGameStateCreation:
    """Tests for creating a new game state."""

    def test_create_new_game(self):
        """Test creating a new game with default settings."""
        game = GameState.create_new_game(num_players=4)

        assert game.num_players == 4
        assert len(game.players) == 4
        assert game.game_phase == GamePhase.SETUP
        assert game.turn_phase == TurnPhase.ROLL_DICE
        assert game.current_player_idx == 0
        assert len(game.dev_card_deck) == 25  # Total dev cards in standard game

    def test_create_new_game_with_different_player_count(self):
        """Test creating games with different numbers of players."""
        for num_players in [2, 3, 4]:
            game = GameState.create_new_game(num_players=num_players)
            assert game.num_players == num_players
            assert len(game.players) == num_players


class TestResourceProduction:
    """Tests for resource production on dice rolls."""

    def test_resource_production_on_roll(self):
        """Test that resources are distributed correctly."""
        game = GameState.create_new_game(num_players=2)

        # Placer une colonie sur le plateau pour un joueur
        # Trouver un hexagone avec un numéro
        hex_coord = None
        hex_number = None
        for coord, hex in game.board.hexes.items():
            if hex.number is not None:
                hex_coord = coord
                hex_number = hex.number
                break

        assert hex_coord is not None

        # Placer une colonie sur ce hexagone
        vertex = VertexCoord(hex_coord, 0)
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        # Sauvegarder les ressources initiales
        initial_resources = game.players[0].resources.copy()

        # Distribuer les ressources pour le numéro de cet hexagone
        game.distribute_resources(hex_number)

        # Vérifier que le joueur a reçu des ressources
        assert game.players[0].total_resources() > sum(initial_resources)

    def test_no_resources_on_seven(self):
        """Test that rolling a 7 doesn't distribute resources."""
        game = GameState.create_new_game(num_players=2)

        # Placer une colonie
        hex_coord = list(game.board.hexes.keys())[0]
        vertex = VertexCoord(hex_coord, 0)
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        initial_resources = game.players[0].total_resources()
        game.distribute_resources(7)

        # Aucune ressource ne devrait être distribuée
        assert game.players[0].total_resources() == initial_resources


class TestBuilding:
    """Tests for building settlements, cities, and roads."""

    def test_build_settlement(self):
        """Test building a settlement."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME

        # Donner des ressources au joueur
        game.players[0].resources[ResourceType.WOOD] = 1
        game.players[0].resources[ResourceType.BRICK] = 1
        game.players[0].resources[ResourceType.SHEEP] = 1
        game.players[0].resources[ResourceType.WHEAT] = 1

        # Trouver un sommet valide
        vertex = None
        for v in game.board.vertices:
            if game.can_place_settlement(v, 0):
                vertex = v
                break

        # Note: En phase MAIN_GAME, il faut une route adjacente
        # Pour ce test, on place d'abord une route
        if vertex:
            # Trouver une arête adjacente
            for adj_vertex in vertex.adjacent_vertices():
                edges = game._edges_between(vertex, adj_vertex)
                if edges:
                    edge = edges[0]
                    game.roads_on_board[edge] = 0
                    game.players[0].roads.add(edge)
                    break

            success = game.build_settlement(0, vertex)
            assert success
            assert vertex in game.settlements_on_board
            assert game.settlements_on_board[vertex] == 0

    def test_build_city(self):
        """Test upgrading a settlement to a city."""
        game = GameState.create_new_game(num_players=2)

        # Placer une colonie
        vertex = list(game.board.vertices)[0]
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        # Donner des ressources pour une ville
        game.players[0].resources[ResourceType.WHEAT] = 2
        game.players[0].resources[ResourceType.ORE] = 3

        success = game.build_city(0, vertex)
        assert success
        assert vertex in game.cities_on_board
        assert vertex not in game.settlements_on_board


class TestTrading:
    """Tests for trading mechanics."""

    def test_trade_with_bank(self):
        """Test trading with the bank at 4:1 ratio."""
        game = GameState.create_new_game(num_players=2)

        # Donner 4 ressources d'un type
        game.players[0].resources[ResourceType.WOOD] = 4

        success = game.trade_with_bank(
            0, ResourceType.WOOD, ResourceType.BRICK, 4
        )

        assert success
        assert game.players[0].resources[ResourceType.WOOD] == 0
        assert game.players[0].resources[ResourceType.BRICK] == 1

    def test_trade_with_insufficient_resources(self):
        """Test that trading fails with insufficient resources."""
        game = GameState.create_new_game(num_players=2)

        # Donner seulement 3 ressources
        game.players[0].resources[ResourceType.WOOD] = 3

        success = game.trade_with_bank(
            0, ResourceType.WOOD, ResourceType.BRICK, 4
        )

        assert not success


class TestDevelopmentCards:
    """Tests for development card mechanics."""

    def test_buy_dev_card(self):
        """Test buying a development card."""
        game = GameState.create_new_game(num_players=2)

        # Donner des ressources pour acheter une carte
        game.players[0].resources[ResourceType.SHEEP] = 1
        game.players[0].resources[ResourceType.WHEAT] = 1
        game.players[0].resources[ResourceType.ORE] = 1

        initial_deck_size = len(game.dev_card_deck)
        card = game.buy_dev_card(0)

        assert card is not None
        assert len(game.dev_card_deck) == initial_deck_size - 1
        assert game.players[0].dev_cards_in_hand[card] == 1

    def test_play_knight(self):
        """Test playing a knight card."""
        game = GameState.create_new_game(num_players=2)

        # Donner une carte chevalier au joueur
        game.players[0].dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1

        # Trouver un hexagone différent du voleur actuel
        new_hex = None
        for coord, hex in game.board.hexes.items():
            if not hex.has_robber:
                new_hex = coord
                break

        assert new_hex is not None

        success = game.play_knight(0, new_hex, None)
        assert success
        assert game.players[0].knights_played == 1
        assert game.board.hexes[new_hex].has_robber
        assert game.players[0].dev_card_played_this_turn

    def test_cannot_play_multiple_dev_cards_per_turn(self):
        """Test that only one development card can be played per turn."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner plusieurs cartes développement au joueur
        game.players[0].dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1
        game.players[0].dev_cards_in_hand[DevelopmentCardType.YEAR_OF_PLENTY] = 1
        game.players[0].dev_cards_in_hand[DevelopmentCardType.MONOPOLY] = 1

        # Trouver un hexagone différent du voleur actuel
        new_hex = None
        for coord, hex in game.board.hexes.items():
            if not hex.has_robber:
                new_hex = coord
                break

        assert new_hex is not None

        # Jouer la première carte (Knight)
        success = game.play_knight(0, new_hex, None)
        assert success
        assert game.players[0].dev_card_played_this_turn

        # Essayer de jouer une deuxième carte (Year of Plenty) - devrait échouer
        success = game.play_year_of_plenty(0, ResourceType.WOOD, ResourceType.BRICK)
        assert not success
        assert game.players[0].dev_cards_in_hand[DevelopmentCardType.YEAR_OF_PLENTY] == 1  # Carte non utilisée

        # Essayer de jouer une troisième carte (Monopoly) - devrait échouer
        result = game.play_monopoly(0, ResourceType.WHEAT)
        assert result == -1  # Échec
        assert game.players[0].dev_cards_in_hand[DevelopmentCardType.MONOPOLY] == 1  # Carte non utilisée

    def test_can_play_dev_card_after_turn_reset(self):
        """Test that the dev card flag is reset after ending the turn."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des cartes au joueur
        game.players[0].dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1
        game.players[0].dev_cards_in_hand[DevelopmentCardType.YEAR_OF_PLENTY] = 1

        # Trouver un hexagone différent du voleur actuel
        new_hex = None
        for coord, hex in game.board.hexes.items():
            if not hex.has_robber:
                new_hex = coord
                break

        # Jouer une carte
        success = game.play_knight(0, new_hex, None)
        assert success
        assert game.players[0].dev_card_played_this_turn

        # Terminer le tour
        action = EndTurnAction()
        new_game = game.apply_action(action)

        # Vérifier que le flag est réinitialisé pour le joueur précédent
        assert not new_game.players[0].dev_card_played_this_turn

    def test_cannot_play_dev_card_bought_this_turn(self):
        """Test that a dev card bought this turn cannot be played."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner une carte chevalier au joueur et marquer comme achetée ce tour
        game.players[0].dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1
        game.players[0].dev_cards_bought_this_turn.append(DevelopmentCardType.KNIGHT)

        # Trouver un hexagone différent du voleur actuel
        new_hex = None
        for coord, hex in game.board.hexes.items():
            if not hex.has_robber:
                new_hex = coord
                break

        # Essayer de jouer la carte - devrait échouer
        success = game.play_knight(0, new_hex, None)
        assert not success
        assert game.players[0].dev_cards_in_hand[DevelopmentCardType.KNIGHT] == 1  # Carte non utilisée


class TestVictoryConditions:
    """Tests for victory condition checking."""

    def test_check_victory_with_sufficient_points(self):
        """Test that victory is detected when a player reaches 10 points."""
        game = GameState.create_new_game(num_players=2)

        # Donner suffisamment de colonies et villes pour 10 points
        # 2 colonies = 2 points, 4 villes = 8 points = 10 points total
        for i in range(2):
            vertex = list(game.board.vertices)[i]
            game.settlements_on_board[vertex] = 0
            game.players[0].settlements.add(vertex)

        for i in range(2, 6):
            vertex = list(game.board.vertices)[i]
            game.cities_on_board[vertex] = 0
            game.players[0].cities.add(vertex)

        winner = game.check_victory()
        assert winner == 0

    def test_no_victory_with_insufficient_points(self):
        """Test that victory is not detected with insufficient points."""
        game = GameState.create_new_game(num_players=2)

        # Donner seulement 2 colonies = 2 points
        for i in range(2):
            vertex = list(game.board.vertices)[i]
            game.settlements_on_board[vertex] = 0
            game.players[0].settlements.add(vertex)

        winner = game.check_victory()
        assert winner is None


class TestPorts:
    """Tests for port mechanics."""

    def test_get_player_ports_no_ports(self):
        """Test that a player with no ports has no accessible ports."""
        game = GameState.create_new_game(num_players=2)
        ports = game.get_player_ports(0)
        assert len(ports) == 0

    def test_get_player_ports_with_settlement(self):
        """Test that a player with a settlement on a port can access it."""
        from src.core.constants import PortType

        game = GameState.create_new_game(num_players=2)

        # Placer un port sur un sommet
        vertex = list(game.board.vertices)[0]
        game.ports[vertex] = PortType.WOOD

        # Placer une colonie du joueur sur ce sommet
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        ports = game.get_player_ports(0)
        assert PortType.WOOD in ports

    def test_get_player_ports_with_city(self):
        """Test that a player with a city on a port can access it."""
        from src.core.constants import PortType

        game = GameState.create_new_game(num_players=2)

        # Placer un port sur un sommet
        vertex = list(game.board.vertices)[0]
        game.ports[vertex] = PortType.GENERIC

        # Placer une ville du joueur sur ce sommet
        game.cities_on_board[vertex] = 0
        game.players[0].cities.add(vertex)

        ports = game.get_player_ports(0)
        assert PortType.GENERIC in ports

    def test_trade_ratio_bank(self):
        """Test trade ratio without ports (4:1 with bank)."""
        game = GameState.create_new_game(num_players=2)

        ratio = game.get_trade_ratio(0, ResourceType.WOOD)
        assert ratio == 4  # BANK_TRADE_RATIO

    def test_trade_ratio_generic_port(self):
        """Test trade ratio with generic port (3:1)."""
        from src.core.constants import PortType

        game = GameState.create_new_game(num_players=2)

        # Donner un port générique au joueur
        vertex = list(game.board.vertices)[0]
        game.ports[vertex] = PortType.GENERIC
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        ratio = game.get_trade_ratio(0, ResourceType.WOOD)
        assert ratio == 3  # PORT_GENERIC_RATIO

    def test_trade_ratio_specific_port(self):
        """Test trade ratio with specific resource port (2:1)."""
        from src.core.constants import PortType

        game = GameState.create_new_game(num_players=2)

        # Donner un port spécifique au joueur
        vertex = list(game.board.vertices)[0]
        game.ports[vertex] = PortType.WOOD
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        # Le ratio pour le bois devrait être 2:1
        ratio = game.get_trade_ratio(0, ResourceType.WOOD)
        assert ratio == 2  # PORT_SPECIFIC_RATIO

        # Le ratio pour les autres ressources devrait être 4:1 (banque)
        ratio = game.get_trade_ratio(0, ResourceType.BRICK)
        assert ratio == 4

    def test_trade_with_port(self):
        """Test trading with a port."""
        from src.core.constants import PortType

        game = GameState.create_new_game(num_players=2)

        # Donner un port 2:1 pour le bois
        vertex = list(game.board.vertices)[0]
        game.ports[vertex] = PortType.WOOD
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        # Donner 2 bois au joueur
        game.players[0].resources[ResourceType.WOOD] = 2

        # Échanger 2 bois contre 1 brique
        success = game.trade_with_bank(0, ResourceType.WOOD, ResourceType.BRICK, 2)

        assert success
        assert game.players[0].resources[ResourceType.WOOD] == 0
        assert game.players[0].resources[ResourceType.BRICK] == 1


class TestRobber:
    """Tests for robber mechanics."""

    def test_move_robber(self):
        """Test moving the robber to a new hex."""
        game = GameState.create_new_game(num_players=2)

        # Trouver le désert (où le voleur commence)
        desert_hex = None
        for hex_coord, hex in game.board.hexes.items():
            if hex.has_robber:
                desert_hex = hex_coord
                break

        assert desert_hex is not None

        # Trouver un autre hexagone
        new_hex = None
        for hex_coord in game.board.hexes.keys():
            if hex_coord != desert_hex:
                new_hex = hex_coord
                break

        assert new_hex is not None

        # Déplacer le voleur
        game.move_robber(new_hex)

        # Vérifier que le voleur a été déplacé
        assert game.board.hexes[new_hex].has_robber
        assert not game.board.hexes[desert_hex].has_robber

    def test_steal_resource_from_player(self):
        """Test stealing a resource from another player."""
        game = GameState.create_new_game(num_players=2)

        # Donner des ressources au joueur 1
        game.players[1].resources[ResourceType.WOOD] = 3
        game.players[1].resources[ResourceType.BRICK] = 2

        # Joueur 0 vole au joueur 1
        stolen = game.steal_resource_from_player(1, 0)

        assert stolen is not None
        assert stolen in [ResourceType.WOOD, ResourceType.BRICK]

        # Vérifier que le total de ressources est correct
        assert game.players[1].total_resources() == 4  # A perdu 1 ressource
        assert game.players[0].total_resources() == 1  # A gagné 1 ressource

    def test_steal_from_player_with_no_resources(self):
        """Test stealing from a player with no resources."""
        game = GameState.create_new_game(num_players=2)

        # Joueur 1 n'a pas de ressources
        assert game.players[1].total_resources() == 0

        # Essayer de voler
        stolen = game.steal_resource_from_player(1, 0)

        assert stolen is None
        assert game.players[0].total_resources() == 0

    def test_get_players_on_hex(self):
        """Test getting players with buildings on a hex."""
        game = GameState.create_new_game(num_players=2)

        hex_coord = list(game.board.hexes.keys())[0]

        # Placer des colonies de différents joueurs sur ce hexagone
        vertex1 = VertexCoord(hex_coord, 0)
        vertex2 = VertexCoord(hex_coord, 2)

        game.settlements_on_board[vertex1] = 0
        game.players[0].settlements.add(vertex1)

        game.settlements_on_board[vertex2] = 1
        game.players[1].settlements.add(vertex2)

        players = game.get_players_on_hex(hex_coord)

        assert 0 in players
        assert 1 in players

    def test_robber_blocks_production(self):
        """Test that the robber blocks resource production."""
        game = GameState.create_new_game(num_players=2)

        # Trouver un hexagone avec un numéro
        hex_coord = None
        hex_number = None
        for coord, hex in game.board.hexes.items():
            if hex.number is not None:
                hex_coord = coord
                hex_number = hex.number
                break

        assert hex_coord is not None

        # Placer une colonie sur ce hexagone
        vertex = VertexCoord(hex_coord, 0)
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        # Placer le voleur sur cet hexagone
        game.move_robber(hex_coord)

        initial_resources = game.players[0].total_resources()

        # Distribuer les ressources pour ce numéro
        game.distribute_resources(hex_number)

        # Le joueur ne devrait pas avoir reçu de ressources
        assert game.players[0].total_resources() == initial_resources


class TestLongestRoadAndLargestArmy:
    """Tests for longest road and largest army bonuses."""

    def test_update_longest_road_no_one_qualifies(self):
        """Test that no one gets the bonus if roads are too short."""
        game = GameState.create_new_game(num_players=2)

        # Ajouter 3 routes au joueur 0 (pas assez pour le bonus)
        for i in range(3):
            edge = EdgeCoord(HexCoord(0, 0), i)
            game.roads_on_board[edge] = 0
            game.players[0].roads.add(edge)

        game.update_longest_road()

        # Personne ne devrait avoir le bonus
        assert not game.players[0].has_longest_road
        assert not game.players[1].has_longest_road

    def test_update_longest_road_one_player_qualifies(self):
        """Test that the player with 5+ roads gets the bonus."""
        game = GameState.create_new_game(num_players=2)

        # Ajouter 5 routes au joueur 0
        for i in range(5):
            edge = EdgeCoord(HexCoord(0, 0), i)
            game.roads_on_board[edge] = 0
            game.players[0].roads.add(edge)

        game.update_longest_road()

        # Le joueur 0 devrait avoir le bonus
        assert game.players[0].has_longest_road
        assert not game.players[1].has_longest_road

    def test_update_longest_road_changes_hands(self):
        """Test that the longest road bonus changes hands."""
        game = GameState.create_new_game(num_players=2)

        # Joueur 0 a 5 routes
        for i in range(5):
            edge = EdgeCoord(HexCoord(0, 0), i)
            game.roads_on_board[edge] = 0
            game.players[0].roads.add(edge)

        game.update_longest_road()
        assert game.players[0].has_longest_road

        # Joueur 1 construit 6 routes (plus longue)
        for i in range(6):
            edge = EdgeCoord(HexCoord(1, 0), i % 6)
            game.roads_on_board[edge] = 1
            game.players[1].roads.add(edge)

        game.update_longest_road()

        # Le bonus devrait passer au joueur 1
        assert not game.players[0].has_longest_road
        assert game.players[1].has_longest_road

    def test_update_largest_army_no_one_qualifies(self):
        """Test that no one gets the bonus with fewer than 3 knights."""
        game = GameState.create_new_game(num_players=2)

        game.players[0].knights_played = 2
        game.update_largest_army()

        assert not game.players[0].has_largest_army
        assert not game.players[1].has_largest_army

    def test_update_largest_army_one_player_qualifies(self):
        """Test that the player with 3+ knights gets the bonus."""
        game = GameState.create_new_game(num_players=2)

        game.players[0].knights_played = 3
        game.update_largest_army()

        assert game.players[0].has_largest_army
        assert not game.players[1].has_largest_army

    def test_update_largest_army_changes_hands(self):
        """Test that the largest army bonus changes hands."""
        game = GameState.create_new_game(num_players=2)

        # Joueur 0 a 3 chevaliers
        game.players[0].knights_played = 3
        game.update_largest_army()
        assert game.players[0].has_largest_army

        # Joueur 1 joue 4 chevaliers
        game.players[1].knights_played = 4
        game.update_largest_army()

        # Le bonus devrait passer au joueur 1
        assert not game.players[0].has_largest_army
        assert game.players[1].has_largest_army


class TestActionApplication:
    """Tests for applying actions to the game state."""

    def test_apply_roll_dice_action(self):
        """Test applying a roll dice action."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.ROLL_DICE

        action = RollDiceAction()
        new_game = game.apply_action(action)

        assert new_game.last_dice_roll is not None
        assert 2 <= new_game.last_dice_roll <= 12
        assert new_game.turn_phase != TurnPhase.ROLL_DICE

    def test_apply_end_turn_action(self):
        """Test applying an end turn action."""
        game = GameState.create_new_game(num_players=2)
        game.turn_phase = TurnPhase.MAIN

        action = EndTurnAction()
        new_game = game.apply_action(action)

        assert new_game.current_player_idx == 1
        assert new_game.turn_phase == TurnPhase.ROLL_DICE
        assert new_game.turn_number == 1


class TestEdgeCases:
    """Tests for edge cases and limits."""

    def test_build_settlement_at_limit(self):
        """Test that a player cannot build more than 5 settlements."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME

        # Placer 5 colonies
        for i in range(5):
            vertex = list(game.board.vertices)[i * 10]  # Espacer les colonies
            game.settlements_on_board[vertex] = 0
            game.players[0].settlements.add(vertex)

        # Essayer de construire une 6ème colonie
        assert not game.players[0].can_build_settlement()

    def test_build_city_at_limit(self):
        """Test that a player cannot build more than 4 cities."""
        game = GameState.create_new_game(num_players=2)

        # Placer 4 villes
        for i in range(4):
            vertex = list(game.board.vertices)[i * 10]
            game.cities_on_board[vertex] = 0
            game.players[0].cities.add(vertex)

        # Essayer de construire une 5ème ville
        assert not game.players[0].can_build_city()

    def test_buy_dev_card_when_deck_empty(self):
        """Test that buying a dev card fails when deck is empty."""
        game = GameState.create_new_game(num_players=2)

        # Vider le paquet
        game.dev_card_deck = []

        # Donner des ressources
        game.players[0].resources[ResourceType.SHEEP] = 1
        game.players[0].resources[ResourceType.WHEAT] = 1
        game.players[0].resources[ResourceType.ORE] = 1

        # Essayer d'acheter une carte
        card = game.buy_dev_card(0)
        assert card is None

    def test_distance_rule_for_settlements(self):
        """Test that settlements cannot be placed adjacent to each other."""
        game = GameState.create_new_game(num_players=2)

        # Placer une colonie
        vertex1 = list(game.board.vertices)[0]
        game.settlements_on_board[vertex1] = 0
        game.players[0].settlements.add(vertex1)

        # Essayer de placer une colonie sur un sommet adjacent
        adjacent_vertices = vertex1.adjacent_vertices()
        for vertex2 in adjacent_vertices:
            if game.board.contains_vertex(vertex2):
                # Ne devrait pas pouvoir placer ici
                assert not game.can_place_settlement(vertex2, 1)

    def test_road_connectivity_requirement(self):
        """Test that roads must be connected to player's network."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME

        # Placer une colonie
        vertex = list(game.board.vertices)[0]
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        # Une route adjacente à la colonie devrait être valide
        # Trouver une arête adjacente
        edges = game.board.edges
        valid_edge = None
        for edge in edges:
            v1, v2 = edge.vertices()
            if v1 == vertex or v2 == vertex:
                valid_edge = edge
                break

        if valid_edge:
            assert game.can_place_road(valid_edge, 0)

        # Une route non connectée ne devrait pas être valide
        # Trouver une arête éloignée
        for edge in edges:
            v1, v2 = edge.vertices()
            if v1 not in [vertex] + vertex.adjacent_vertices() and \
               v2 not in [vertex] + vertex.adjacent_vertices():
                # Cette arête n'est pas connectée
                assert not game.can_place_road(edge, 0)
                break
