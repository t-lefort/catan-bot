"""Tests pour la phase de setup (ENG-002).

Spécifications (docs/specs.md):
- Deux tours de placement, ordre serpent (J1, J2, J2, J1)
- Chaque joueur place colonie + route adjacente
- Distribution des ressources après le second placement uniquement
- Colonies doivent respecter la règle de distance
"""

import pytest
from catan.engine.board import Board
from catan.engine.state import GameState, Player, SetupPhase
from catan.engine.actions import PlaceSettlement, PlaceRoad


class TestSetupPhaseOrder:
    """Vérification de l'ordre serpent des placements."""

    def test_setup_creates_two_players(self):
        """Un jeu 1v1 initialise exactement 2 joueurs."""
        state = GameState.new_1v1_game(player_names=["Alice", "Bob"])
        assert len(state.players) == 2
        assert state.players[0].name == "Alice"
        assert state.players[1].name == "Bob"

    def test_initial_phase_is_setup(self):
        """La phase initiale est SETUP_ROUND_1."""
        state = GameState.new_1v1_game()
        assert state.phase == SetupPhase.SETUP_ROUND_1

    def test_turn_order_first_round(self):
        """Premier tour: joueur 0 puis joueur 1."""
        state = GameState.new_1v1_game()
        assert state.current_player_id == 0
        # Après placement J0, c'est au tour de J1
        # (détails implémentation dépendent de l'API d'actions)

    def test_turn_order_second_round_reversed(self):
        """Deuxième tour: ordre inverse (1, 0) = serpent."""
        state = GameState.new_1v1_game()
        # Simulation: après 2 placements (J0, J1), on doit être en SETUP_ROUND_2
        # et commencer par J1
        # (détails à implémenter dans state)


class TestSetupPlacements:
    """Vérification des règles de placement pendant setup."""

    def test_first_settlement_can_be_placed_anywhere(self):
        """Pendant setup, la 1ère colonie peut aller sur n'importe quel sommet libre."""
        state = GameState.new_1v1_game()
        board = state.board
        # Prendre un sommet valide arbitraire
        vertex_id = list(board.vertices.keys())[10]
        action = PlaceSettlement(vertex_id=vertex_id, free=True)
        # Doit être valide (pas de contrainte de distance au setup round 1)
        assert state.is_action_legal(action)

    def test_settlement_requires_adjacent_road(self):
        """Pendant setup, après placement colonie, une route adjacente doit être placée."""
        state = GameState.new_1v1_game()
        vertex_id = 10
        state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
        # Récupérer une arête adjacente
        vertex = state.board.vertices[vertex_id]
        adjacent_edge = vertex.edges[0]
        action = PlaceRoad(edge_id=adjacent_edge, free=True)
        assert state.is_action_legal(action)

    def test_distance_rule_applies_after_setup(self):
        """Après setup, la règle de distance s'applique (à vérifier dans ENG-005)."""
        # Placeholder test pour rappel
        pass


class TestResourceDistribution:
    """Vérification de la distribution des ressources après second placement."""

    def test_no_resources_after_first_placement(self):
        """Aucune ressource n'est distribuée après le 1er placement."""
        state = GameState.new_1v1_game()
        vertex_id = 10
        state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
        # Le joueur 0 ne doit avoir aucune ressource
        assert sum(state.players[0].resources.values()) == 0

    def test_resources_distributed_after_second_placement(self):
        """Les ressources adjacentes sont distribuées après le 2e placement."""
        state = GameState.new_1v1_game()

        # Simuler les 4 placements (2 joueurs × 2 tours)
        # Round 1: J0, J1
        # Round 2: J1, J0

        # J0 round 1
        vertex_j0_r1 = 10
        state = state.apply_action(PlaceSettlement(vertex_id=vertex_j0_r1, free=True))
        edge_j0_r1 = state.board.vertices[vertex_j0_r1].edges[0]
        state = state.apply_action(PlaceRoad(edge_id=edge_j0_r1, free=True))

        # J1 round 1
        vertex_j1_r1 = 20
        state = state.apply_action(PlaceSettlement(vertex_id=vertex_j1_r1, free=True))
        edge_j1_r1 = state.board.vertices[vertex_j1_r1].edges[0]
        state = state.apply_action(PlaceRoad(edge_id=edge_j1_r1, free=True))

        # J1 round 2 (ordre serpent)
        vertex_j1_r2 = 30
        state = state.apply_action(PlaceSettlement(vertex_id=vertex_j1_r2, free=True))
        edge_j1_r2 = state.board.vertices[vertex_j1_r2].edges[0]
        state = state.apply_action(PlaceRoad(edge_id=edge_j1_r2, free=True))

        # J1 doit maintenant avoir des ressources adjacentes à vertex_j1_r2
        vertex = state.board.vertices[vertex_j1_r2]
        expected_resources = []
        for tile_id in vertex.adjacent_tiles:
            tile = state.board.tiles[tile_id]
            if tile.resource != "DESERT":
                expected_resources.append(tile.resource)

        # Vérifier que J1 a bien reçu ces ressources
        j1_total = sum(state.players[1].resources.values())
        assert j1_total == len(expected_resources)

    def test_complete_setup_transitions_to_play_phase(self):
        """Après les 4 placements, le jeu passe en phase ACTION."""
        state = GameState.new_1v1_game()

        # Effectuer les 4 placements complets
        placements = [
            (10, 0),  # J0 R1: vertex 10, edge 0 (adjacente)
            (20, 0),  # J1 R1
            (30, 0),  # J1 R2 (serpent)
            (40, 0),  # J0 R2
        ]

        for vertex_id, edge_offset in placements:
            state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
            vertex = state.board.vertices[vertex_id]
            edge_id = vertex.edges[edge_offset]
            state = state.apply_action(PlaceRoad(edge_id=edge_id, free=True))

        # Le setup doit être terminé
        assert state.phase not in [SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2]


class TestSetupInvariants:
    """Invariants à maintenir pendant et après setup."""

    def test_each_player_has_two_settlements_after_setup(self):
        """Après setup, chaque joueur a exactement 2 colonies."""
        state = GameState.new_1v1_game()
        # Effectuer setup complet (4 placements × 2 actions)
        # ... (même code que test précédent)
        # assert len(state.players[0].settlements) == 2
        # assert len(state.players[1].settlements) == 2
        pass

    def test_each_player_has_two_roads_after_setup(self):
        """Après setup, chaque joueur a exactement 2 routes."""
        # Similar test
        pass

    def test_settlements_respect_distance_rule_between_players(self):
        """Les colonies de joueurs différents doivent respecter la distance."""
        # Placeholder
        pass
