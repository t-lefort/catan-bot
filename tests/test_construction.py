"""Tests pour ENG-005 — Construction (routes, colonies, villes).

Spécifications (docs/specs.md):
- Coûts respectés pour chaque construction.
- Routes doivent étendre le réseau existant (settlement/route connectée).
- Colonies doivent être adjacentes à une route du joueur et respecter la règle de distance.
- Villes requièrent une colonie existante et consomment les ressources adéquates.
"""

from __future__ import annotations

from typing import Dict

from catan.engine.actions import BuildCity, PlaceRoad, PlaceSettlement
from catan.engine.rules import COSTS
from catan.engine.state import GameState, SetupPhase, TurnSubPhase


def _empty_resources() -> Dict[str, int]:
    """Retourne un stock de ressources vide."""

    return {"BRICK": 0, "LUMBER": 0, "WOOL": 0, "GRAIN": 0, "ORE": 0}


def base_play_state() -> GameState:
    """Construit un état post-setup minimal pour les tests de construction."""

    state = GameState.new_1v1_game()

    # Forcer les attributs vers une phase de jeu standard
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 1
    state.current_player_id = 0
    state.dice_rolled_this_turn = True
    state._waiting_for_road = False
    state._setup_roads_placed = 0
    state._setup_settlements_placed = 0

    # Réinitialiser proprement les joueurs
    for player in state.players:
        player.resources = _empty_resources()
        player.roads = []
        player.settlements = []
        player.cities = []
        player.victory_points = 0

    # Positionner un réseau minimal cohérent
    state.players[0].settlements = [10]
    state.players[0].roads = [8]  # Arête (5, 10)
    state.players[0].victory_points = 1

    state.players[1].settlements = [30]
    state.players[1].roads = [35]
    state.players[1].victory_points = 1

    return state


def test_place_road_consumes_resources_and_extends_network():
    """Le joueur peut construire une route connectée en payant le coût."""

    state = base_play_state()
    player = state.players[0]
    player.resources["BRICK"] = 1
    player.resources["LUMBER"] = 1

    action = PlaceRoad(edge_id=15)  # edge (10, 11), connecté à la colonie 10
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert 15 in new_player.roads
    assert new_player.resources["BRICK"] == 0
    assert new_player.resources["LUMBER"] == 0


def test_place_road_requires_connection_to_existing_network():
    """Une route non connectée au réseau du joueur est illégale."""

    state = base_play_state()
    player = state.players[0]
    player.resources["BRICK"] = 1
    player.resources["LUMBER"] = 1

    action = PlaceRoad(edge_id=21)  # arête (14, 20), hors réseau joueur 0
    assert not state.is_action_legal(action)


def test_place_road_requires_dice_roll_first():
    """Le joueur doit avoir lancé les dés avant de construire."""

    state = base_play_state()
    state.dice_rolled_this_turn = False
    player = state.players[0]
    player.resources["BRICK"] = 1
    player.resources["LUMBER"] = 1

    action = PlaceRoad(edge_id=15)
    assert not state.is_action_legal(action)


def test_place_settlement_consumes_resources_and_adds_vp():
    """Une colonie peut être construite sur un sommet libre relié au réseau."""

    state = base_play_state()
    player = state.players[0]
    # Étendons le réseau vers le sommet 22 via routes préexistantes
    player.roads.extend([16, 24])  # (10,16) puis (16,22)
    player.resources.update({"BRICK": 1, "LUMBER": 1, "WOOL": 1, "GRAIN": 1})

    action = PlaceSettlement(vertex_id=22)
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert 22 in new_player.settlements
    assert new_player.victory_points == 2  # +1 VP
    for resource, cost in COSTS["settlement"].items():
        assert new_player.resources[resource] == max(0, player.resources[resource] - cost)


def test_place_settlement_requires_connected_road():
    """Colonies doivent être adjacentes à une route du joueur."""

    state = base_play_state()
    player = state.players[0]
    player.resources.update({"BRICK": 1, "LUMBER": 1, "WOOL": 1, "GRAIN": 1})

    action = PlaceSettlement(vertex_id=22)
    assert not state.is_action_legal(action)


def test_place_settlement_enforces_distance_rule():
    """Impossible de placer une colonie adjacente à une colonie existante."""

    state = base_play_state()
    player = state.players[0]
    player.roads.append(15)  # Connecte au sommet 11
    player.resources.update({"BRICK": 1, "LUMBER": 1, "WOOL": 1, "GRAIN": 1})

    action = PlaceSettlement(vertex_id=11)
    assert not state.is_action_legal(action)


def test_build_city_consumes_resources_and_upgrades_settlement():
    """Une ville nécessite une colonie existante et consomme 2 blé + 3 minerai."""

    state = base_play_state()
    player = state.players[0]
    player.resources.update({"GRAIN": 2, "ORE": 3})

    action = BuildCity(vertex_id=10)
    assert state.is_action_legal(action)

    new_state = state.apply_action(action)
    new_player = new_state.players[0]

    assert 10 in new_player.cities
    assert 10 not in new_player.settlements
    assert new_player.victory_points == 2  # 1 (colonie) + 1 pour l'amélioration
    assert new_player.resources["GRAIN"] == 0
    assert new_player.resources["ORE"] == 0


def test_build_city_requires_existing_settlement():
    """On ne peut pas construire une ville sans colonie sur le sommet visé."""

    state = base_play_state()
    player = state.players[0]
    player.settlements = []  # Retirer la colonie initiale
    player.resources.update({"GRAIN": 2, "ORE": 3})

    action = BuildCity(vertex_id=10)
    assert not state.is_action_legal(action)


def test_build_city_requires_resources():
    """Une ville ne peut être construite sans les ressources nécessaires."""

    state = base_play_state()
    player = state.players[0]
    player.resources.update({"GRAIN": 2, "ORE": 2})  # Manque 1 minerai

    action = BuildCity(vertex_id=10)
    assert not state.is_action_legal(action)


def test_place_settlement_respects_piece_limit():
    """Impossible de dépasser 5 colonies simultanées pour un joueur."""

    state = base_play_state()
    player = state.players[0]
    player.resources.update({"BRICK": 2, "LUMBER": 2, "WOOL": 2, "GRAIN": 2})

    # Pré-remplir les 5 colonies disponibles sur des sommets non adjacents
    player.settlements = [0, 2, 4, 6, 8]
    # Conserver la route connectée au sommet 10 pour rendre le placement autrement légal
    player.roads = [8]

    action = PlaceSettlement(vertex_id=10)
    assert not state.is_action_legal(action)


def test_build_city_respects_piece_limit():
    """Impossible de dépasser 4 villes simultanées pour un joueur."""

    state = base_play_state()
    player = state.players[0]
    player.resources.update({"GRAIN": 3, "ORE": 3})

    # Pré-remplir les 4 villes disponibles
    player.cities = [0, 2, 4, 6]
    player.settlements = [10]  # Ville à améliorer restante

    action = BuildCity(vertex_id=10)
    assert not state.is_action_legal(action)
