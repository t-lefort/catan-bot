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
