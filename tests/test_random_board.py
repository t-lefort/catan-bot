"""Tests pour la génération aléatoire du plateau (ENG-014)."""

from catan.engine.board import Board


def test_random_board_generates_different_layouts():
    """Deux plateaux aléatoires avec des seeds différentes doivent être différents."""
    board1 = Board.random(seed=42)
    board2 = Board.random(seed=123)

    # Les ressources doivent être différentes
    resources1 = [tile.resource for tile in board1.tiles.values()]
    resources2 = [tile.resource for tile in board2.tiles.values()]

    # Au moins une ressource doit être à une position différente
    assert resources1 != resources2


def test_random_board_reproductibility():
    """Deux plateaux avec la même seed doivent être identiques."""
    board1 = Board.random(seed=42)
    board2 = Board.random(seed=42)

    # Vérifier que les ressources sont identiques
    for tile_id in board1.tiles:
        assert board1.tiles[tile_id].resource == board2.tiles[tile_id].resource
        assert board1.tiles[tile_id].pip == board2.tiles[tile_id].pip

    # Vérifier que les ports sont identiques
    for port_id in range(len(board1.ports)):
        assert board1.ports[port_id].kind == board2.ports[port_id].kind


def test_random_board_preserves_game_structure():
    """Le plateau aléatoire doit conserver la structure du jeu."""
    board = Board.random(seed=42)

    # Nombre de tuiles correct
    assert board.tile_count() == 19

    # Nombre de sommets correct
    assert board.vertex_count() == 54

    # Nombre d'arêtes correct
    assert board.edge_count() == 72

    # Nombre de ports correct
    assert len(board.ports) == 9

    # Le désert doit être présent
    resources = [tile.resource for tile in board.tiles.values()]
    assert "DESERT" in resources

    # Le désert ne doit pas avoir de pip
    desert_tiles = [tile for tile in board.tiles.values() if tile.resource == "DESERT"]
    assert len(desert_tiles) == 1
    assert desert_tiles[0].pip is None

    # Le voleur doit être sur le désert (tile_id 0)
    assert board.tiles[0].has_robber
    assert board.tiles[0].resource == "DESERT"


def test_random_board_has_correct_resource_distribution():
    """Le plateau aléatoire doit avoir la distribution correcte de ressources."""
    board = Board.random(seed=42)
    resources = [tile.resource for tile in board.tiles.values()]

    # Compter chaque type de ressource
    from collections import Counter
    resource_counts = Counter(resources)

    # Vérifier les quantités (basées sur le plateau standard)
    assert resource_counts["DESERT"] == 1
    assert resource_counts["LUMBER"] == 4
    assert resource_counts["BRICK"] == 3
    assert resource_counts["WOOL"] == 4
    assert resource_counts["GRAIN"] == 4
    assert resource_counts["ORE"] == 3


def test_random_board_has_all_pip_numbers():
    """Le plateau aléatoire doit avoir tous les numéros de dés."""
    board = Board.random(seed=42)
    pips = [tile.pip for tile in board.tiles.values() if tile.pip is not None]

    # Il doit y avoir 18 pips (19 tuiles - 1 désert)
    assert len(pips) == 18

    # Vérifier que tous les pips sont valides (2-12, sauf 7)
    for pip in pips:
        assert 2 <= pip <= 12
        assert pip != 7


def test_random_board_has_correct_port_distribution():
    """Le plateau aléatoire doit avoir la bonne distribution de ports."""
    board = Board.random(seed=42)

    # Compter les types de ports
    from collections import Counter
    port_kinds = [port.kind for port in board.ports]
    port_counts = Counter(port_kinds)

    # Vérifier les quantités
    assert port_counts["ANY"] == 4
    assert port_counts["BRICK"] == 1
    assert port_counts["ORE"] == 1
    assert port_counts["WOOL"] == 1
    assert port_counts["GRAIN"] == 1
    assert port_counts["LUMBER"] == 1
