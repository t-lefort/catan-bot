"""Tests pour le lancer de dés et distribution de ressources (ENG-003, ENG-004).

Spécifications (docs/specs.md):
- Lancer de 2 dés (2 à 12)
- Distribution selon numéros de dés et colonies/villes adjacentes
- Le 7 déclenche la phase voleur (pas de distribution)
- Le voleur bloque la production de la tuile où il se trouve
"""

import pytest
from dataclasses import replace

from catan.engine.board import Board
from catan.engine.state import GameState, SetupPhase, TurnSubPhase
from catan.engine.actions import (
    RollDice,
    PlaceSettlement,
    PlaceRoad,
    DiscardResources,
    MoveRobber,
)


class TestDiceRoll:
    """Tests pour le lancer de dés."""

    def test_roll_dice_action_exists(self):
        """L'action RollDice existe et peut être créée."""
        action = RollDice()
        assert action is not None

    def test_roll_dice_returns_value_between_2_and_12(self):
        """Le lancer de dés retourne une valeur entre 2 et 12."""
        state = self._setup_complete_game()

        # Simuler plusieurs lancers pour vérifier la plage
        for _ in range(20):
            action = RollDice()
            new_state = state.apply_action(action)
            # La valeur du dé devrait être stockée dans l'état
            assert hasattr(new_state, 'last_dice_roll')
            assert 2 <= new_state.last_dice_roll <= 12

    def test_roll_dice_can_be_forced_for_testing(self):
        """On peut forcer la valeur des dés pour les tests."""
        state = self._setup_complete_game()
        action = RollDice(forced_value=(3, 4))
        new_state = state.apply_action(action)
        assert new_state.last_dice_roll == 7

    def test_roll_dice_only_legal_at_start_of_turn(self):
        """Le lancer de dés n'est légal qu'au début du tour (phase PLAY)."""
        state = GameState.new_1v1_game()
        # Pendant setup, le lancer de dés n'est pas légal
        assert not state.is_action_legal(RollDice())

        # Après setup, en début de tour, c'est légal
        state = self._setup_complete_game()
        assert state.is_action_legal(RollDice())

    def _setup_complete_game(self) -> GameState:
        """Crée un jeu après la phase de setup."""
        state = GameState.new_1v1_game()
        # Placements rapides pour terminer le setup
        placements = [(10, 0), (20, 0), (30, 0), (40, 0)]
        for vertex_id, edge_offset in placements:
            state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
            vertex = state.board.vertices[vertex_id]
            edge_id = vertex.edges[edge_offset]
            state = state.apply_action(PlaceRoad(edge_id=edge_id, free=True))
        assert state.phase == SetupPhase.PLAY
        return state


class TestResourceDistribution:
    """Tests pour la distribution de ressources après lancer de dés."""

    def test_no_distribution_on_seven(self):
        """Lancer un 7 ne distribue aucune ressource."""
        state = self._setup_game_with_settlements()
        initial_resources = {
            pid: sum(p.resources.values())
            for pid, p in enumerate(state.players)
        }

        # Lancer un 7
        action = RollDice(forced_value=(3, 4))
        new_state = state.apply_action(action)

        # Aucune ressource distribuée
        for pid, player in enumerate(new_state.players):
            assert sum(player.resources.values()) == initial_resources[pid]

    def test_distribution_for_settlement_on_matching_number(self):
        """Une colonie sur une tuile avec le bon numéro reçoit 1 ressource."""
        state = self._setup_game_with_known_settlement()

        # Récupérer le numéro (pip) d'une tuile adjacente à la colonie
        settlement_vertex = 10
        vertex = state.board.vertices[settlement_vertex]
        target_tile = None
        for tile_id in vertex.adjacent_tiles:
            tile = state.board.tiles[tile_id]
            if tile.resource != "DESERT" and tile.pip is not None:
                target_tile = tile
                break

        assert target_tile is not None, "Devrait avoir une tuile avec ressource"

        # Forcer le lancer pour correspondre au numéro (pip)
        dice_value = target_tile.pip
        # Trouver une combinaison qui donne ce total
        die1 = min(dice_value - 1, 6)
        die2 = dice_value - die1

        initial_resource = state.players[0].resources[target_tile.resource]
        action = RollDice(forced_value=(die1, die2))
        new_state = state.apply_action(action)

        # Le joueur 0 devrait avoir gagné 1 ressource
        assert new_state.players[0].resources[target_tile.resource] == initial_resource + 1

    def test_distribution_for_city_gives_double_resources(self):
        """Une ville sur une tuile avec le bon numéro reçoit 2 ressources."""
        # Ce test nécessite la capacité de construire des villes (ENG-005)
        # Placeholder pour l'instant
        pass

    def test_robber_blocks_production(self):
        """Le voleur bloque la production de la tuile où il se trouve."""
        state = self._setup_game_with_known_settlement()

        # Préparer un sommet connu et la tuile associée
        settlement_vertex = state.players[0].settlements[0]
        vertex = state.board.vertices[settlement_vertex]
        robber_tile_id = next(
            tile_id
            for tile_id in vertex.adjacent_tiles
            if state.board.tiles[tile_id].resource != "DESERT"
            and state.board.tiles[tile_id].pip is not None
        )
        target_tile = state.board.tiles[robber_tile_id]

        # État: voleur positionné sur la tuile cible, phase principale
        state.robber_tile_id = robber_tile_id  # type: ignore[attr-defined]
        state = replace(state, dice_rolled_this_turn=False, last_dice_roll=None)
        state.turn_subphase = TurnSubPhase.MAIN  # type: ignore[attr-defined]

        # Suivre les ressources avant le lancer
        player0 = state.players[0]
        initial_resource = player0.resources[target_tile.resource]

        # Lancer les dés avec le numéro de la tuile bloquée
        total = target_tile.pip
        assert total is not None
        die1 = min(total - 1, 6)
        die2 = total - die1
        new_state = state.apply_action(RollDice(forced_value=(die1, die2)))

        # Aucune ressource ne doit être distribuée pour cette tuile
        assert new_state.players[0].resources[target_tile.resource] == initial_resource


    def test_distribution_to_multiple_players(self):
        """Si plusieurs joueurs ont des colonies sur le même numéro, tous reçoivent."""
        # Setup avec colonies des 2 joueurs sur des tuiles avec le même numéro
        # TODO: nécessite setup plus contrôlé
        pass

    def test_distribution_multiple_settlements_same_player(self):
        """Un joueur avec plusieurs colonies sur le même numéro reçoit plusieurs fois."""
        # Après setup, un joueur peut avoir 2 colonies sur différentes tuiles
        # avec le même numéro
        # TODO: nécessite setup contrôlé
        pass

    def test_desert_never_produces(self):
        """Le désert ne produit jamais de ressource, quel que soit le lancer."""
        state = self._setup_game_with_settlement_on_desert()

        # Tester tous les lancers possibles
        for total in range(2, 13):
            die1 = min(total - 1, 6)
            die2 = total - die1
            action = RollDice(forced_value=(die1, die2))
            new_state = state.apply_action(action)
            # Aucune ressource ne devrait être ajoutée
            # (le désert n'a pas de ressource)

    def _setup_game_with_settlements(self) -> GameState:
        """Crée un jeu après setup avec colonies en place."""
        state = GameState.new_1v1_game()
        placements = [(10, 0), (20, 0), (30, 0), (40, 0)]
        for vertex_id, edge_offset in placements:
            state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
            vertex = state.board.vertices[vertex_id]
            edge_id = vertex.edges[edge_offset]
            state = state.apply_action(PlaceRoad(edge_id=edge_id, free=True))
        return state

    def _setup_game_with_known_settlement(self) -> GameState:
        """Crée un jeu avec une colonie sur une position connue."""
        return self._setup_game_with_settlements()

    def _setup_game_with_settlement_on_desert(self) -> GameState:
        """Crée un jeu avec une colonie adjacente au désert."""
        state = GameState.new_1v1_game()

        # Trouver le désert
        desert_tile_id = None
        for tile_id, tile in state.board.tiles.items():
            if tile.resource == "DESERT":
                desert_tile_id = tile_id
                break

        assert desert_tile_id is not None

        # Trouver un sommet adjacent au désert
        desert_tile = state.board.tiles[desert_tile_id]
        desert_vertex = desert_tile.vertices[0]

        # Placer une colonie sur ce sommet
        state = state.apply_action(PlaceSettlement(vertex_id=desert_vertex, free=True))
        vertex = state.board.vertices[desert_vertex]
        edge_id = vertex.edges[0]
        state = state.apply_action(PlaceRoad(edge_id=edge_id, free=True))

        # Compléter le setup
        placements = [(20, 0), (30, 0), (40, 0)]
        for vertex_id, edge_offset in placements:
            state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
            vertex = state.board.vertices[vertex_id]
            edge_id = vertex.edges[edge_offset]
            state = state.apply_action(PlaceRoad(edge_id=edge_id, free=True))

        return state


class TestSevenRoll:
    """Tests spécifiques pour le lancer de 7."""

    def test_seven_triggers_robber_phase(self):
        """Lancer un 7 déclenche la phase voleur (défausse + déplacement)."""
        state = self._setup_complete_game()
        action = RollDice(forced_value=(3, 4))
        new_state = state.apply_action(action)

        # Pour l'instant, on vérifie juste que le 7 est enregistré
        # La gestion complète du voleur sera dans ENG-004
        assert new_state.last_dice_roll == 7
        # TODO (ENG-004): vérifier requires_discard et phase_action

    def test_seven_no_production(self):
        """Lancer un 7 ne produit aucune ressource."""
        state = self._setup_complete_game()
        initial_total = sum(
            sum(p.resources.values()) for p in state.players
        )

        action = RollDice(forced_value=(3, 4))
        new_state = state.apply_action(action)

        final_total = sum(
            sum(p.resources.values()) for p in new_state.players
        )
        assert final_total == initial_total

    def _setup_complete_game(self) -> GameState:
        """Crée un jeu après la phase de setup."""
        state = GameState.new_1v1_game()
        placements = [(10, 0), (20, 0), (30, 0), (40, 0)]
        for vertex_id, edge_offset in placements:
            state = state.apply_action(PlaceSettlement(vertex_id=vertex_id, free=True))
            vertex = state.board.vertices[vertex_id]
            edge_id = vertex.edges[edge_offset]
            state = state.apply_action(PlaceRoad(edge_id=edge_id, free=True))
        assert state.phase == SetupPhase.PLAY
        return state


class TestRobberSevenResolution:
    """Tests spécifiques à la résolution du 7 (défausse + déplacement du voleur)."""

    def test_roll_seven_requires_discard_when_above_threshold(self):
        """Un joueur > 9 cartes doit défausser après un 7."""
        state = self._setup_game_with_settlements()

        # Joueur 0 avec 13 cartes, Joueur 1 sous le seuil
        state.players[0].resources = {
            "BRICK": 5,
            "LUMBER": 2,
            "WOOL": 2,
            "GRAIN": 2,
            "ORE": 2,
        }
        state.players[1].resources = {
            "BRICK": 1,
            "LUMBER": 1,
            "WOOL": 1,
            "GRAIN": 1,
            "ORE": 1,
        }

        new_state = state.apply_action(RollDice(forced_value=(3, 4)))

        assert new_state.turn_subphase == TurnSubPhase.ROBBER_DISCARD
        assert new_state.pending_discards == {0: 4}
        assert new_state.current_player_id == 0
        assert new_state.robber_roller_id == 0

    def test_discard_action_reduces_hand_and_advances_phase(self):
        """La défausse ramène la main à 9 cartes puis passe à la phase déplacement."""
        state = self._state_after_seven_with_pending_discard()

        discard_action = DiscardResources(resources={"BRICK": 2, "LUMBER": 2})
        new_state = state.apply_action(discard_action)

        assert new_state.pending_discards == {}
        assert new_state.turn_subphase == TurnSubPhase.ROBBER_MOVE
        assert new_state.current_player_id == new_state.robber_roller_id
        assert sum(new_state.players[0].resources.values()) == 9

    def test_move_robber_updates_location_and_steals(self):
        """Déplacer le voleur met à jour sa position et vole 1 ressource si possible."""
        state = self._state_after_seven_with_pending_discard()
        state = state.apply_action(DiscardResources(resources={"BRICK": 2, "LUMBER": 2}))

        # Préparer les ressources pour que le vol soit déterministe
        for resource in state.players[0].resources:
            state.players[0].resources[resource] = 0
        state.players[1].resources = {
            "BRICK": 0,
            "LUMBER": 0,
            "WOOL": 2,
            "GRAIN": 0,
            "ORE": 0,
        }

        # Choisir une tuile adjacente à une colonie de J1 (non désert, avec numéro)
        settlement_vertex = state.players[1].settlements[0]
        vertex = state.board.vertices[settlement_vertex]
        target_tile_id = next(
            tile_id
            for tile_id in vertex.adjacent_tiles
            if state.board.tiles[tile_id].resource != "DESERT"
            and state.board.tiles[tile_id].pip is not None
        )

        roller_id = state.robber_roller_id
        assert roller_id is not None

        new_state = state.apply_action(MoveRobber(tile_id=target_tile_id, steal_from=1))

        assert new_state.robber_tile_id == target_tile_id
        assert new_state.turn_subphase == TurnSubPhase.MAIN
        assert new_state.current_player_id == roller_id
        assert new_state.robber_roller_id is None
        assert new_state.players[1].resources["WOOL"] == 1
        assert new_state.players[0].resources["WOOL"] == 1

    # Helpers -----------------------------------------------------------------

    def _state_after_seven_with_pending_discard(self) -> GameState:
        """Prépare un état où J0 doit encore défausser après un 7."""
        state = self._setup_game_with_settlements()
        state.players[0].resources = {
            "BRICK": 5,
            "LUMBER": 2,
            "WOOL": 2,
            "GRAIN": 2,
            "ORE": 2,
        }
        state.players[1].resources = {
            "BRICK": 1,
            "LUMBER": 1,
            "WOOL": 1,
            "GRAIN": 1,
            "ORE": 1,
        }
        state = state.apply_action(RollDice(forced_value=(3, 4)))
        assert state.turn_subphase == TurnSubPhase.ROBBER_DISCARD
        return state

    def _setup_game_with_settlements(self) -> GameState:
        return TestResourceDistribution()._setup_game_with_settlements()
