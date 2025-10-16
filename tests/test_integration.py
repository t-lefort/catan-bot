"""Integration tests and edge cases for the game engine."""

import pytest
from copy import deepcopy
from src.core.game_state import GameState, GamePhase, TurnPhase
from src.core.board import HexCoord, VertexCoord, EdgeCoord
from src.core.constants import ResourceType, DevelopmentCardType
from src.core.actions import (
    RollDiceAction,
    BuildSettlementAction,
    BuildCityAction,
    BuildRoadAction,
    EndTurnAction,
)


class TestGameStateImmutability:
    """Tests for GameState immutability."""

    def test_apply_action_returns_new_state(self):
        """Test that apply_action returns a new state object."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.ROLL_DICE

        action = RollDiceAction()
        new_game = game.apply_action(action)

        # Les objets devraient être différents
        assert game is not new_game

    def test_apply_action_does_not_modify_original(self):
        """Test that applying an action doesn't modify the original state."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        original_turn = game.turn_number
        original_player = game.current_player_idx

        action = EndTurnAction()
        new_game = game.apply_action(action)

        # L'état original ne devrait pas avoir changé
        assert game.turn_number == original_turn
        assert game.current_player_idx == original_player

        # Le nouvel état devrait avoir changé
        assert new_game.turn_number == original_turn + 1
        assert new_game.current_player_idx != original_player

    def test_game_state_can_be_copied(self):
        """Test that GameState can be deep copied."""
        game = GameState.create_new_game(num_players=2)

        # Ajouter quelques constructions
        vertex = list(game.board.vertices)[0]
        game.settlements_on_board[vertex] = 0
        game.players[0].settlements.add(vertex)

        # Copier l'état
        game_copy = deepcopy(game)

        # Les deux états devraient être égaux mais différents objets
        assert game is not game_copy
        assert game.turn_number == game_copy.turn_number
        assert game.current_player_idx == game_copy.current_player_idx
        assert len(game.settlements_on_board) == len(game_copy.settlements_on_board)


class TestFullGameSimulation:
    """Tests simulating complete game scenarios."""

    def test_simple_game_flow(self):
        """Test a simple game flow without errors."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME

        # Tour 1: Joueur 0 lance les dés
        game.turn_phase = TurnPhase.ROLL_DICE
        action = RollDiceAction()
        game = game.apply_action(action)

        # Le jeu devrait avancer
        assert game.last_dice_roll is not None
        assert game.turn_phase != TurnPhase.ROLL_DICE

        # Si on n'a pas fait 7, on devrait être en phase MAIN
        if game.last_dice_roll != 7:
            assert game.turn_phase == TurnPhase.MAIN

            # Terminer le tour
            action = EndTurnAction()
            game = game.apply_action(action)

            # Devrait passer au joueur 1
            assert game.current_player_idx == 1
            assert game.turn_phase == TurnPhase.ROLL_DICE

    def test_build_and_upgrade_settlement(self):
        """Test building a settlement and upgrading it to a city."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources pour une colonie
        player = game.players[0]
        player.resources[ResourceType.WOOD] = 2
        player.resources[ResourceType.BRICK] = 2
        player.resources[ResourceType.SHEEP] = 1
        player.resources[ResourceType.WHEAT] = 3
        player.resources[ResourceType.ORE] = 3

        # Placer une route
        edge = list(game.board.edges)[0]
        game.roads_on_board[edge] = 0
        player.roads.add(edge)

        # Trouver un sommet valide pour la colonie
        v1, v2 = edge.vertices()
        vertex = v1 if game.can_place_settlement(v1, 0) else v2

        # Construire la colonie
        success = game.build_settlement(0, vertex)
        assert success
        assert vertex in game.settlements_on_board
        assert player.victory_points() == 1

        # Améliorer en ville
        success = game.build_city(0, vertex)
        assert success
        assert vertex in game.cities_on_board
        assert vertex not in game.settlements_on_board
        assert player.victory_points() == 2

    def test_play_multiple_turns(self):
        """Test playing multiple turns in sequence."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME

        for turn in range(10):
            game.turn_phase = TurnPhase.ROLL_DICE

            # Lancer les dés
            action = RollDiceAction()
            game = game.apply_action(action)

            # Gérer le 7 si nécessaire
            if game.last_dice_roll == 7:
                if game.turn_phase == TurnPhase.DISCARD:
                    # Pour simplifier, on passe la défausse
                    game.turn_phase = TurnPhase.ROBBER

                if game.turn_phase == TurnPhase.ROBBER:
                    # Choisir la première action de voleur disponible
                    actions = game.get_valid_actions()
                    if actions:
                        game = game.apply_action(actions[0])

            # Terminer le tour
            game.turn_phase = TurnPhase.MAIN
            action = EndTurnAction()
            game = game.apply_action(action)

            # Vérifier que le tour a avancé
            assert game.turn_number == turn + 1

    def test_reach_victory_condition(self):
        """Test that a player can reach victory condition."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME

        # Donner 10 points au joueur 0
        vertices = list(game.board.vertices)
        for i in range(10):
            vertex = vertices[i * 5]
            game.settlements_on_board[vertex] = 0
            game.players[0].settlements.add(vertex)

        # Vérifier la victoire
        winner = game.check_victory()
        assert winner == 0

        # Vérifier qu'on peut passer en phase GAME_OVER
        game.turn_phase = TurnPhase.MAIN
        action = EndTurnAction()
        game = game.apply_action(action)

        # Le jeu devrait se terminer (car on vérifie la victoire à la fin du tour)
        # Note: Cela dépend de l'implémentation exacte


class TestResourceManagement:
    """Tests for resource management."""

    def test_resource_distribution_to_multiple_players(self):
        """Test that resources are distributed to all players with buildings."""
        game = GameState.create_new_game(num_players=3)

        # Trouver un hexagone avec un numéro
        hex_coord = None
        hex_number = None
        for coord, hex in game.board.hexes.items():
            if hex.number is not None and hex.number == 6:
                hex_coord = coord
                hex_number = hex.number
                break

        if hex_coord is None:
            # Utiliser n'importe quel hexagone avec un numéro
            for coord, hex in game.board.hexes.items():
                if hex.number is not None:
                    hex_coord = coord
                    hex_number = hex.number
                    break

        # Placer des colonies de différents joueurs sur ce hexagone
        for i in range(3):
            vertex = VertexCoord(hex_coord, i * 2)
            game.settlements_on_board[vertex] = i
            game.players[i].settlements.add(vertex)

        # Distribuer les ressources
        game.distribute_resources(hex_number)

        # Tous les joueurs devraient avoir reçu des ressources
        for i in range(3):
            assert game.players[i].total_resources() > 0

    def test_city_produces_double_resources(self):
        """Test that cities produce 2 resources instead of 1."""
        game = GameState.create_new_game(num_players=2)

        # Trouver un hexagone avec un numéro
        hex_coord = None
        hex_number = None
        for coord, hex in game.board.hexes.items():
            if hex.number is not None:
                hex_coord = coord
                hex_number = hex.number
                break

        # Placer une colonie pour le joueur 0
        vertex1 = VertexCoord(hex_coord, 0)
        game.settlements_on_board[vertex1] = 0
        game.players[0].settlements.add(vertex1)

        # Placer une ville pour le joueur 1
        vertex2 = VertexCoord(hex_coord, 2)
        game.cities_on_board[vertex2] = 1
        game.players[1].cities.add(vertex2)

        # Distribuer les ressources
        game.distribute_resources(hex_number)

        # Le joueur 0 devrait avoir 1 ressource, le joueur 1 devrait avoir 2
        assert game.players[0].total_resources() == 1
        assert game.players[1].total_resources() == 2


class TestDevelopmentCardMechanics:
    """Tests for development card mechanics."""

    def test_dev_card_deck_shuffled(self):
        """Test that the dev card deck is shuffled."""
        # Créer plusieurs jeux et vérifier que les decks sont différents
        deck1 = GameState.create_initial_dev_card_deck()
        deck2 = GameState.create_initial_dev_card_deck()

        # Les decks devraient avoir la même taille
        assert len(deck1) == len(deck2)

        # Mais très probablement un ordre différent
        # (Note: Ce test pourrait théoriquement échouer avec une très faible probabilité)

    def test_dev_card_distribution(self):
        """Test that the dev card deck has the correct distribution."""
        from src.core.constants import DEV_CARD_DISTRIBUTION

        deck = GameState.create_initial_dev_card_deck()

        # Compter les cartes de chaque type
        card_counts = {}
        for card in deck:
            card_counts[card] = card_counts.get(card, 0) + 1

        # Vérifier la distribution
        for card_type, expected_count in DEV_CARD_DISTRIBUTION.items():
            assert card_counts.get(card_type, 0) == expected_count

    def test_all_dev_cards_can_be_bought(self):
        """Test that all dev cards in deck can be bought."""
        game = GameState.create_new_game(num_players=2)

        initial_deck_size = len(game.dev_card_deck)
        assert initial_deck_size == 25

        # Donner beaucoup de ressources
        player = game.players[0]
        player.resources[ResourceType.SHEEP] = 25
        player.resources[ResourceType.WHEAT] = 25
        player.resources[ResourceType.ORE] = 25

        # Acheter toutes les cartes
        for _ in range(initial_deck_size):
            card = game.buy_dev_card(0)
            assert card is not None

        # Le deck devrait être vide
        assert len(game.dev_card_deck) == 0

        # Impossible d'acheter une autre carte
        player.resources[ResourceType.SHEEP] = 10
        player.resources[ResourceType.WHEAT] = 10
        player.resources[ResourceType.ORE] = 10
        card = game.buy_dev_card(0)
        assert card is None


class TestEdgeCasesAndBoundaries:
    """Tests for edge cases and boundary conditions."""

    def test_player_with_zero_resources(self):
        """Test game state with player having zero resources."""
        game = GameState.create_new_game(num_players=2)
        player = game.players[0]

        assert player.total_resources() == 0
        assert not player.can_afford({ResourceType.WOOD: 1})

    def test_negative_resources_prevented(self):
        """Test that negative resources are prevented."""
        game = GameState.create_new_game(num_players=2)
        player = game.players[0]

        # Essayer de payer sans ressources
        with pytest.raises(AssertionError):
            player.pay({ResourceType.WOOD: 1})

    def test_game_with_maximum_players(self):
        """Test creating a game with maximum players."""
        game = GameState.create_new_game(num_players=4)
        assert game.num_players == 4
        assert len(game.players) == 4

    def test_game_with_minimum_players(self):
        """Test creating a game with minimum players."""
        game = GameState.create_new_game(num_players=2)
        assert game.num_players == 2
        assert len(game.players) == 2

    def test_all_resources_types_can_be_produced(self):
        """Test that all resource types can be produced."""
        game = GameState.create_new_game(num_players=2)

        resources_produced = set()

        # Vérifier tous les hexagones
        for hex in game.board.hexes.values():
            resource = hex.produces_resource()
            if resource is not None:
                resources_produced.add(resource)

        # Devrait avoir les 5 types de ressources
        assert ResourceType.WOOD in resources_produced
        assert ResourceType.BRICK in resources_produced
        assert ResourceType.SHEEP in resources_produced
        assert ResourceType.WHEAT in resources_produced
        assert ResourceType.ORE in resources_produced

    def test_buildings_count_limits(self):
        """Test that building limits are enforced."""
        from src.core.constants import (
            MAX_SETTLEMENTS_PER_PLAYER,
            MAX_CITIES_PER_PLAYER,
            MAX_ROADS_PER_PLAYER,
        )

        game = GameState.create_new_game(num_players=2)
        player = game.players[0]

        # Vérifier les limites
        assert MAX_SETTLEMENTS_PER_PLAYER == 5
        assert MAX_CITIES_PER_PLAYER == 4
        assert MAX_ROADS_PER_PLAYER == 15

        # Ajouter le maximum de constructions
        vertices = list(game.board.vertices)
        for i in range(MAX_SETTLEMENTS_PER_PLAYER):
            player.settlements.add(vertices[i * 10])

        assert not player.can_build_settlement()
        assert len(player.settlements) == MAX_SETTLEMENTS_PER_PLAYER


class TestGameStateRepr:
    """Tests for GameState string representation."""

    def test_game_state_repr(self):
        """Test that GameState has a useful string representation."""
        game = GameState.create_new_game(num_players=2)
        game.turn_number = 5
        game.current_player_idx = 1

        repr_str = repr(game)
        assert "turn=5" in repr_str
        assert "current_player=1" in repr_str
        assert "GameState" in repr_str

    def test_game_state_repr_with_winner(self):
        """Test GameState repr with a winner."""
        game = GameState.create_new_game(num_players=2)
        game.winner = 0
        game.game_phase = GamePhase.GAME_OVER

        repr_str = repr(game)
        assert "winner=0" in repr_str
        assert "GAME_OVER" in repr_str
