"""Tests for get_valid_actions() method."""

import pytest
from src.core.game_state import GameState, GamePhase, TurnPhase
from src.core.board import HexCoord, VertexCoord, EdgeCoord
from src.core.player import PlayerState
from src.core.constants import ResourceType, BuildingType, DevelopmentCardType, BUILDING_COSTS
from src.core.actions import (
    RollDiceAction,
    BuildSettlementAction,
    BuildCityAction,
    BuildRoadAction,
    BuyDevCardAction,
    TradeWithBankAction,
    PlayKnightAction,
    PlayYearOfPlentyAction,
    PlayMonopolyAction,
    MoveRobberAction,
    EndTurnAction,
)


class TestGetValidActionsRollPhase:
    """Tests for valid actions during ROLL_DICE phase."""

    def test_only_roll_dice_action_available(self):
        """Test that only roll dice action is available during roll phase."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.ROLL_DICE

        actions = game.get_valid_actions()

        # Devrait avoir exactement 1 action: lancer les dés
        assert len(actions) == 1
        assert isinstance(actions[0], RollDiceAction)


class TestGetValidActionsRobberPhase:
    """Tests for valid actions during ROBBER phase."""

    def test_robber_actions_after_seven(self):
        """Test that robber actions are available after rolling a 7."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.ROBBER

        actions = game.get_valid_actions()

        # Devrait avoir des actions de déplacement du voleur
        assert len(actions) > 0
        assert all(isinstance(a, MoveRobberAction) for a in actions)

        # Le nombre d'actions dépend du nombre d'hexagones (19 - 1 pour le désert avec voleur)
        # Chaque hexagone peut avoir 0, 1 ou plusieurs victimes possibles
        assert len(actions) >= 18  # Au minimum 18 hexagones disponibles

    def test_robber_actions_with_victims(self):
        """Test robber actions when there are potential victims."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.ROBBER

        # Trouver un hexagone qui n'a PAS le voleur
        hex_coord = None
        for coord, hex_tile in game.board.hexes.items():
            if not hex_tile.has_robber:
                hex_coord = coord
                break

        assert hex_coord is not None, "Should have at least one hex without robber"

        # Placer une colonie du joueur 1 sur cet hexagone
        vertex = VertexCoord(hex_coord, 0)
        game.settlements_on_board[vertex] = 1
        game.players[1].settlements.add(vertex)

        actions = game.get_valid_actions()

        # Vérifier qu'il y a une action pour voler au joueur 1
        steal_actions = [a for a in actions if a.new_hex == hex_coord and a.steal_from_player == 1]
        assert len(steal_actions) > 0


class TestGetValidActionsMainPhase:
    """Tests for valid actions during MAIN phase."""

    def test_no_actions_without_resources(self):
        """Test that only end turn is available without resources."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        actions = game.get_valid_actions()

        # Devrait avoir seulement EndTurnAction
        assert len(actions) == 1
        assert isinstance(actions[0], EndTurnAction)

    def test_build_settlement_action_available(self):
        """Test that build settlement actions are available with resources."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources pour construire une colonie
        player = game.players[0]
        player.resources[ResourceType.WOOD] = 1
        player.resources[ResourceType.BRICK] = 1
        player.resources[ResourceType.SHEEP] = 1
        player.resources[ResourceType.WHEAT] = 1

        # Placer une route pour permettre le placement
        edge = list(game.board.edges)[0]
        game.roads_on_board[edge] = 0
        player.roads.add(edge)

        actions = game.get_valid_actions()

        # Devrait avoir au moins une action de construction de colonie
        settlement_actions = [a for a in actions if isinstance(a, BuildSettlementAction)]
        assert len(settlement_actions) > 0

    def test_build_city_action_available(self):
        """Test that build city actions are available."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources pour construire une ville
        player = game.players[0]
        player.resources[ResourceType.WHEAT] = 2
        player.resources[ResourceType.ORE] = 3

        # Placer une colonie
        vertex = list(game.board.vertices)[0]
        game.settlements_on_board[vertex] = 0
        player.settlements.add(vertex)

        actions = game.get_valid_actions()

        # Devrait avoir une action de construction de ville
        city_actions = [a for a in actions if isinstance(a, BuildCityAction)]
        assert len(city_actions) == 1
        assert city_actions[0].vertex == vertex

    def test_build_road_action_available(self):
        """Test that build road actions are available."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources pour construire une route
        player = game.players[0]
        player.resources[ResourceType.WOOD] = 1
        player.resources[ResourceType.BRICK] = 1

        # Placer une colonie pour permettre le placement de routes
        vertex = list(game.board.vertices)[0]
        game.settlements_on_board[vertex] = 0
        player.settlements.add(vertex)

        actions = game.get_valid_actions()

        # Devrait avoir des actions de construction de route
        road_actions = [a for a in actions if isinstance(a, BuildRoadAction)]
        assert len(road_actions) > 0

    def test_buy_dev_card_action_available(self):
        """Test that buy dev card action is available."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources pour acheter une carte
        player = game.players[0]
        player.resources[ResourceType.SHEEP] = 1
        player.resources[ResourceType.WHEAT] = 1
        player.resources[ResourceType.ORE] = 1

        actions = game.get_valid_actions()

        # Devrait avoir une action d'achat de carte développement
        buy_actions = [a for a in actions if isinstance(a, BuyDevCardAction)]
        assert len(buy_actions) == 1

    def test_no_buy_dev_card_when_deck_empty(self):
        """Test that buy dev card is not available when deck is empty."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Vider le paquet
        game.dev_card_deck = []

        # Donner des ressources
        player = game.players[0]
        player.resources[ResourceType.SHEEP] = 1
        player.resources[ResourceType.WHEAT] = 1
        player.resources[ResourceType.ORE] = 1

        actions = game.get_valid_actions()

        # Ne devrait pas avoir d'action d'achat de carte
        buy_actions = [a for a in actions if isinstance(a, BuyDevCardAction)]
        assert len(buy_actions) == 0

    def test_trade_with_bank_actions_available(self):
        """Test that trade actions are available with enough resources."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner 4 ressources d'un type (pour échange 4:1)
        player = game.players[0]
        player.resources[ResourceType.WOOD] = 4

        actions = game.get_valid_actions()

        # Devrait avoir 4 actions d'échange (bois contre brick/sheep/wheat/ore)
        trade_actions = [a for a in actions if isinstance(a, TradeWithBankAction)]
        assert len(trade_actions) == 4  # 4 autres ressources possibles

        # Vérifier qu'on échange du bois
        assert all(a.give == ResourceType.WOOD for a in trade_actions)
        assert all(a.amount == 4 for a in trade_actions)


class TestGetValidActionsDevCards:
    """Tests for valid actions with development cards."""

    def test_play_knight_action_available(self):
        """Test that knight actions are available."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner une carte chevalier au joueur
        player = game.players[0]
        player.dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1

        actions = game.get_valid_actions()

        # Devrait avoir des actions de chevalier (une par hexagone possible)
        knight_actions = [a for a in actions if isinstance(a, PlayKnightAction)]
        assert len(knight_actions) >= 18  # Au moins 18 hexagones disponibles

    def test_cannot_play_dev_card_bought_this_turn(self):
        """Test that dev cards bought this turn cannot be played."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner une carte et la marquer comme achetée ce tour
        player = game.players[0]
        player.dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1
        player.dev_cards_bought_this_turn.append(DevelopmentCardType.KNIGHT)

        actions = game.get_valid_actions()

        # Ne devrait pas avoir d'actions de chevalier
        knight_actions = [a for a in actions if isinstance(a, PlayKnightAction)]
        assert len(knight_actions) == 0

    def test_cannot_play_second_dev_card(self):
        """Test that only one dev card can be played per turn."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner plusieurs cartes
        player = game.players[0]
        player.dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1
        player.dev_cards_in_hand[DevelopmentCardType.YEAR_OF_PLENTY] = 1

        # Marquer qu'une carte a déjà été jouée
        player.dev_card_played_this_turn = True

        actions = game.get_valid_actions()

        # Ne devrait avoir aucune action de carte développement
        knight_actions = [a for a in actions if isinstance(a, PlayKnightAction)]
        plenty_actions = [a for a in actions if isinstance(a, PlayYearOfPlentyAction)]

        assert len(knight_actions) == 0
        assert len(plenty_actions) == 0

    def test_play_year_of_plenty_actions(self):
        """Test that year of plenty actions are generated correctly."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner une carte Invention
        player = game.players[0]
        player.dev_cards_in_hand[DevelopmentCardType.YEAR_OF_PLENTY] = 1

        actions = game.get_valid_actions()

        # Devrait avoir 25 actions (5x5 combinaisons de ressources)
        plenty_actions = [a for a in actions if isinstance(a, PlayYearOfPlentyAction)]
        assert len(plenty_actions) == 25  # 5 ressources * 5 ressources

    def test_play_monopoly_actions(self):
        """Test that monopoly actions are generated correctly."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner une carte Monopole
        player = game.players[0]
        player.dev_cards_in_hand[DevelopmentCardType.MONOPOLY] = 1

        actions = game.get_valid_actions()

        # Devrait avoir 5 actions (une par type de ressource)
        monopoly_actions = [a for a in actions if isinstance(a, PlayMonopolyAction)]
        assert len(monopoly_actions) == 5


class TestGetValidActionsLimits:
    """Tests for action limits."""

    def test_no_settlement_action_at_limit(self):
        """Test that settlement actions are not available at limit."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources
        player = game.players[0]
        player.resources[ResourceType.WOOD] = 10
        player.resources[ResourceType.BRICK] = 10
        player.resources[ResourceType.SHEEP] = 10
        player.resources[ResourceType.WHEAT] = 10

        # Placer le maximum de colonies (5)
        vertices = list(game.board.vertices)
        for i in range(5):
            vertex = vertices[i * 10]
            game.settlements_on_board[vertex] = 0
            player.settlements.add(vertex)

        # Placer une route pour permettre le placement théorique
        edge = list(game.board.edges)[0]
        game.roads_on_board[edge] = 0
        player.roads.add(edge)

        actions = game.get_valid_actions()

        # Ne devrait pas avoir d'actions de construction de colonie
        settlement_actions = [a for a in actions if isinstance(a, BuildSettlementAction)]
        assert len(settlement_actions) == 0

    def test_no_city_action_at_limit(self):
        """Test that city actions are not available at limit."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources
        player = game.players[0]
        player.resources[ResourceType.WHEAT] = 10
        player.resources[ResourceType.ORE] = 10

        # Placer le maximum de villes (4)
        vertices = list(game.board.vertices)
        for i in range(4):
            vertex = vertices[i * 10]
            game.cities_on_board[vertex] = 0
            player.cities.add(vertex)

        actions = game.get_valid_actions()

        # Ne devrait pas avoir d'actions de construction de ville
        city_actions = [a for a in actions if isinstance(a, BuildCityAction)]
        assert len(city_actions) == 0

    def test_no_road_action_at_limit(self):
        """Test that road actions are not available at limit."""
        game = GameState.create_new_game(num_players=2)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner des ressources
        player = game.players[0]
        player.resources[ResourceType.WOOD] = 10
        player.resources[ResourceType.BRICK] = 10

        # Placer le maximum de routes (15)
        edges = list(game.board.edges)
        for i in range(15):
            edge = edges[i]
            game.roads_on_board[edge] = 0
            player.roads.add(edge)

        actions = game.get_valid_actions()

        # Ne devrait pas avoir d'actions de construction de route
        road_actions = [a for a in actions if isinstance(a, BuildRoadAction)]
        assert len(road_actions) == 0


class TestGetValidActionsPerformance:
    """Tests for performance of get_valid_actions()."""

    def test_get_valid_actions_completes_quickly(self):
        """Test that get_valid_actions() completes in reasonable time."""
        import time

        game = GameState.create_new_game(num_players=4)
        game.game_phase = GamePhase.MAIN_GAME
        game.turn_phase = TurnPhase.MAIN

        # Donner beaucoup de ressources et de cartes pour maximiser les actions
        player = game.players[0]
        for resource in ResourceType:
            player.resources[resource] = 10

        player.dev_cards_in_hand[DevelopmentCardType.KNIGHT] = 1
        player.dev_cards_in_hand[DevelopmentCardType.YEAR_OF_PLENTY] = 1

        # Placer quelques constructions
        vertices = list(game.board.vertices)[:3]
        for vertex in vertices:
            player.settlements.add(vertex)

        edges = list(game.board.edges)[:5]
        for edge in edges:
            player.roads.add(edge)

        # Mesurer le temps
        start_time = time.time()
        actions = game.get_valid_actions()
        elapsed_time = time.time() - start_time

        # Devrait compléter en moins de 100ms
        assert elapsed_time < 0.1

        # Devrait avoir plusieurs actions
        assert len(actions) > 10
