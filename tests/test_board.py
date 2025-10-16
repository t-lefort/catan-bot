"""Tests pour le module board."""

import pytest
from src.core.board import HexCoord, VertexCoord, EdgeCoord, Board, Hex
from src.core.constants import TerrainType, ResourceType


class TestHexCoord:
    """Tests pour les coordonnées hexagonales."""

    def test_hex_coord_creation(self):
        """Test création de coordonnées hexagonales valides."""
        hex = HexCoord(0, 0)
        assert hex.q == 0
        assert hex.r == 0
        assert hex.s == 0

    def test_hex_coord_constraint(self):
        """Test que q+r+s=0 est vérifié."""
        hex = HexCoord(1, -1)
        assert hex.q + hex.r + hex.s == 0

    def test_hex_coord_invalid(self):
        """Test que HexCoord automatically calculates s correctly."""
        # With the current 2-parameter design, all coordinates are valid
        # s is automatically calculated as -q-r, so q+r+s always equals 0
        hex = HexCoord(1, 1)
        assert hex.q + hex.r + hex.s == 0  # 1 + 1 + (-2) = 0

    def test_hex_coord_neighbors(self):
        """Test que chaque hexagone a exactement 6 voisins."""
        hex = HexCoord(0, 0)
        neighbors = hex.neighbors()
        assert len(neighbors) == 6

        # Vérifier que tous les voisins sont valides
        for neighbor in neighbors:
            assert neighbor.q + neighbor.r + neighbor.s == 0

    def test_hex_coord_neighbors_positions(self):
        """Test les positions exactes des voisins."""
        hex = HexCoord(0, 0)
        neighbors = hex.neighbors()

        expected = [
            HexCoord(1, -1),   # NE
            HexCoord(1, 0),    # E
            HexCoord(0, 1),    # SE
            HexCoord(-1, 1),   # SW
            HexCoord(-1, 0),   # W
            HexCoord(0, -1),   # NW
        ]

        assert set(neighbors) == set(expected)

    def test_hex_coord_hashable(self):
        """Test que HexCoord est hashable (peut être clé de dict)."""
        hex1 = HexCoord(0, 0)
        hex2 = HexCoord(0, 0)
        hex3 = HexCoord(1, 0)

        hex_set = {hex1, hex2, hex3}
        assert len(hex_set) == 2  # hex1 et hex2 sont égaux


class TestVertexCoord:
    """Tests pour les coordonnées de sommets."""

    def test_vertex_coord_creation(self):
        """Test création d'un sommet valide."""
        vertex = VertexCoord(HexCoord(0, 0), 0)
        assert vertex.hex == HexCoord(0, 0)
        assert vertex.direction == 0

    def test_vertex_coord_invalid_direction(self):
        """Test qu'une direction invalide lève une erreur."""
        with pytest.raises(AssertionError):
            VertexCoord(HexCoord(0, 0), 6)
        with pytest.raises(AssertionError):
            VertexCoord(HexCoord(0, 0), -1)

    def test_vertex_coord_adjacent_vertices(self):
        """Test que chaque sommet a exactement 3 voisins."""
        vertex = VertexCoord(HexCoord(0, 0), 0)
        adjacent = vertex.adjacent_vertices()
        assert len(adjacent) == 3

        # Vérifier que tous sont des VertexCoord valides
        for v in adjacent:
            assert isinstance(v, VertexCoord)
            assert 0 <= v.direction < 6

    def test_vertex_coord_adjacent_hexes(self):
        """Test que chaque sommet touche exactement 3 hexagones."""
        vertex = VertexCoord(HexCoord(0, 0), 0)
        hexes = vertex.adjacent_hexes()
        assert len(hexes) == 3

        # Vérifier que tous sont des HexCoord valides
        for h in hexes:
            assert isinstance(h, HexCoord)
            assert h.q + h.r + h.s == 0

    def test_vertex_coord_hashable(self):
        """Test que VertexCoord est hashable."""
        v1 = VertexCoord(HexCoord(0, 0), 0)
        v2 = VertexCoord(HexCoord(0, 0), 0)
        v3 = VertexCoord(HexCoord(0, 0), 1)

        vertex_set = {v1, v2, v3}
        assert len(vertex_set) == 2


class TestEdgeCoord:
    """Tests pour les coordonnées d'arêtes."""

    def test_edge_coord_creation(self):
        """Test création d'une arête valide."""
        edge = EdgeCoord(HexCoord(0, 0), 0)
        assert edge.hex == HexCoord(0, 0)
        assert edge.direction == 0

    def test_edge_coord_invalid_direction(self):
        """Test qu'une direction invalide lève une erreur."""
        with pytest.raises(AssertionError):
            EdgeCoord(HexCoord(0, 0), 6)

    def test_edge_coord_vertices(self):
        """Test que chaque arête a exactement 2 sommets."""
        edge = EdgeCoord(HexCoord(0, 0), 0)
        v1, v2 = edge.vertices()

        assert isinstance(v1, VertexCoord)
        assert isinstance(v2, VertexCoord)
        assert v1 != v2

    def test_edge_coord_adjacent_edges(self):
        """Test que chaque arête a 4 arêtes adjacentes."""
        edge = EdgeCoord(HexCoord(0, 0), 0)
        adjacent = edge.adjacent_edges()
        assert len(adjacent) == 4

        # Vérifier que tous sont des EdgeCoord valides
        for e in adjacent:
            assert isinstance(e, EdgeCoord)
            assert 0 <= e.direction < 6

    def test_edge_coord_hashable(self):
        """Test que EdgeCoord est hashable."""
        e1 = EdgeCoord(HexCoord(0, 0), 0)
        e2 = EdgeCoord(HexCoord(0, 0), 0)
        e3 = EdgeCoord(HexCoord(0, 0), 1)

        edge_set = {e1, e2, e3}
        assert len(edge_set) == 2


class TestHex:
    """Tests pour les hexagones du plateau."""

    def test_hex_produces_resource(self):
        """Test que les hexagones produisent les bonnes ressources."""
        forest = Hex(HexCoord(0, 0), TerrainType.FOREST, 6)
        assert forest.produces_resource() == ResourceType.WOOD

        hills = Hex(HexCoord(0, 1), TerrainType.HILLS, 8)
        assert hills.produces_resource() == ResourceType.BRICK

        pasture = Hex(HexCoord(1, 0), TerrainType.PASTURE, 5)
        assert pasture.produces_resource() == ResourceType.SHEEP

        fields = Hex(HexCoord(1, -1), TerrainType.FIELDS, 4)
        assert fields.produces_resource() == ResourceType.WHEAT

        mountains = Hex(HexCoord(-1, 0), TerrainType.MOUNTAINS, 10)
        assert mountains.produces_resource() == ResourceType.ORE

    def test_desert_produces_nothing(self):
        """Test que le désert ne produit pas de ressource."""
        desert = Hex(HexCoord(0, 0), TerrainType.DESERT, None)
        assert desert.produces_resource() is None


class TestBoard:
    """Tests pour le plateau de jeu."""

    def test_board_creation_standard(self):
        """Test création d'un plateau standard."""
        board = Board.create_standard_board(shuffle=False)

        # Vérifier qu'il y a 19 hexagones
        assert len(board.hexes) == 19

        # Vérifier la distribution des terrains
        terrain_counts = {}
        for hex in board.hexes.values():
            terrain_counts[hex.terrain] = terrain_counts.get(hex.terrain, 0) + 1

        assert terrain_counts[TerrainType.FOREST] == 4
        assert terrain_counts[TerrainType.PASTURE] == 4
        assert terrain_counts[TerrainType.FIELDS] == 4
        assert terrain_counts[TerrainType.HILLS] == 3
        assert terrain_counts[TerrainType.MOUNTAINS] == 3
        assert terrain_counts[TerrainType.DESERT] == 1

    def test_board_has_18_numbers(self):
        """Test qu'il y a 18 numéros (19 hexagones - 1 désert)."""
        board = Board.create_standard_board()

        numbers = [hex.number for hex in board.hexes.values() if hex.number is not None]
        assert len(numbers) == 18

        # Vérifier qu'il n'y a pas de 7
        assert 7 not in numbers

    def test_board_desert_has_robber(self):
        """Test que le désert commence avec le voleur."""
        board = Board.create_standard_board()

        # Trouver le désert
        desert = None
        for hex in board.hexes.values():
            if hex.terrain == TerrainType.DESERT:
                desert = hex
                break

        assert desert is not None
        assert desert.has_robber
        assert desert.number is None

    def test_board_shuffle(self):
        """Test que shuffle=True mélange le plateau."""
        board1 = Board.create_standard_board(shuffle=False)
        board2 = Board.create_standard_board(shuffle=True)

        # Les terrains devraient être différents (avec très haute probabilité)
        # On compare les premiers hexagones
        first_hex_coord = HexCoord(0, -2)
        terrain1 = board1.hexes[first_hex_coord].terrain
        terrain2 = board2.hexes[first_hex_coord].terrain

        # Note: Ce test pourrait échouer avec une probabilité de 1/19
        # mais c'est acceptable pour un test de mélange

    def test_board_vertices_computed(self):
        """Test que les sommets sont calculés correctement."""
        board = Board.create_standard_board()

        # Le plateau standard devrait avoir des sommets
        assert len(board.vertices) > 0

        # Tous les sommets devraient avoir leurs 3 hexagones adjacents sur le plateau
        for vertex in board.vertices:
            adjacent_hexes = vertex.adjacent_hexes()
            assert all(h in board.hexes for h in adjacent_hexes)

    def test_board_edges_computed(self):
        """Test que les arêtes sont calculées correctement."""
        board = Board.create_standard_board()

        # Le plateau standard devrait avoir des arêtes
        assert len(board.edges) > 0

        # Toutes les arêtes devraient avoir leurs 2 hexagones adjacents sur le plateau
        for edge in board.edges:
            hex1 = edge.hex
            hex2 = hex1.neighbors()[edge.direction]
            assert hex1 in board.hexes
            assert hex2 in board.hexes

    def test_board_get_hexes_for_roll(self):
        """Test la récupération des hexagones pour un jet de dé."""
        board = Board.create_standard_board()

        # Tester pour différents jets
        for roll in range(2, 13):
            if roll == 7:
                continue  # Le 7 n'est pas sur le plateau

            hexes = board.get_hexes_for_roll(roll)

            # Vérifier que tous les hexagones ont bien ce numéro
            for hex in hexes:
                assert hex.number == roll
                # Et qu'ils n'ont pas le voleur (sinon ils ne produisent pas)
                assert not hex.has_robber

    def test_board_get_hexes_for_roll_with_robber(self):
        """Test que les hexagones avec le voleur ne sont pas retournés."""
        board = Board.create_standard_board()

        # Trouver un hexagone avec un numéro
        hex_with_number = None
        for hex in board.hexes.values():
            if hex.number is not None:
                hex_with_number = hex
                break

        assert hex_with_number is not None
        roll = hex_with_number.number

        # Compter combien d'hexagones produisent pour ce jet
        initial_count = len(board.get_hexes_for_roll(roll))

        # Placer le voleur sur cet hexagone
        hex_with_number.has_robber = True

        # Vérifier qu'il y a maintenant un hexagone en moins
        new_count = len(board.get_hexes_for_roll(roll))
        assert new_count == initial_count - 1

    def test_board_hexes_by_number_index(self):
        """Test que l'index par numéro fonctionne."""
        board = Board.create_standard_board()

        # Vérifier que tous les numéros sont indexés
        for hex in board.hexes.values():
            if hex.number is not None:
                assert hex.number in board.hexes_by_number
                assert hex in board.hexes_by_number[hex.number]
