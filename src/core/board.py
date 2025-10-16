"""Board representation and geometry for Catan.

Le plateau est représenté comme un graphe d'hexagones avec des sommets (vertices) et des arêtes (edges).
Utilise un système de coordonnées cubiques pour les hexagones.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np

from .constants import TerrainType, ResourceType


@dataclass(frozen=True)
class HexCoord:
    """Coordonnées cubiques pour un hexagone (q, r, s avec q+r+s=0)."""
    q: int
    r: int

    def __post_init__(self) -> None:
        """Valide les coordonnées cubiques."""
        # Store s for efficiency
        object.__setattr__(self, '_s', -self.q - self.r)

    @property
    def s(self) -> int:
        """Calcule s à partir de q et r (s = -q - r pour satisfaire q+r+s=0)."""
        return -self.q - self.r

    def neighbors(self) -> list['HexCoord']:
        """Retourne les 6 hexagones voisins."""
        return [
            HexCoord(self.q + 1, self.r - 1),  # NE
            HexCoord(self.q + 1, self.r),      # E
            HexCoord(self.q, self.r + 1),      # SE
            HexCoord(self.q - 1, self.r + 1),  # SW
            HexCoord(self.q - 1, self.r),      # W
            HexCoord(self.q, self.r - 1),      # NW
        ]


@dataclass(frozen=True, eq=True)
class VertexCoord:
    """
    Coordonnées d'un sommet (intersection de 3 hexagones).
    Défini par un hexagone et une direction (0-5).

    Note: Le même sommet physique peut être représenté par différentes paires (hex, direction).
    Pour comparer correctement les sommets, utilisez la méthode is_same_vertex().
    """
    hex: HexCoord
    direction: int  # 0-5, dans le sens horaire à partir du haut

    def __post_init__(self) -> None:
        assert 0 <= self.direction < 6, "Direction must be 0-5"

    def adjacent_vertices(self) -> list['VertexCoord']:
        """Retourne les 3 sommets adjacents."""
        # Chaque sommet est connecté à 3 autres sommets
        neighbors = self.hex.neighbors()
        return [
            VertexCoord(self.hex, (self.direction - 1) % 6),
            VertexCoord(self.hex, (self.direction + 1) % 6),
            # Le troisième sommet adjacent se trouve sur l'hexagone voisin
            # dans la direction actuelle. Sa direction locale doit pointer
            # vers le sommet partagé par l'hex courant (d) et le voisin (d-1).
            # Cela correspond à (direction + 4) % 6, et non (direction + 2).
            VertexCoord(neighbors[self.direction], (self.direction + 4) % 6),
        ]

    def adjacent_hexes(self) -> list[HexCoord]:
        """Retourne les 3 hexagones touchant ce sommet."""
        neighbors = self.hex.neighbors()
        return [
            self.hex,
            neighbors[self.direction],
            neighbors[(self.direction - 1) % 6],
        ]

    def is_same_vertex(self, other: 'VertexCoord') -> bool:
        """
        Vérifie si deux VertexCoord représentent le même sommet physique.
        Deux sommets sont identiques s'ils partagent les mêmes 3 hexagones adjacents.
        """
        # Comparer tous les 3 hexagones adjacents, y compris ceux hors plateau
        # Ceci garantit que deux sommets physiquement différents ne sont pas confondus
        self_hexes = set(self.adjacent_hexes())
        other_hexes = set(other.adjacent_hexes())
        return self_hexes == other_hexes


@dataclass(frozen=True)
class EdgeCoord:
    """
    Coordonnées d'une arête (entre 2 hexagones).
    Défini par un hexagone et une direction (0-5).

    Note: La même arête physique peut être représentée par différentes paires (hex, direction).
    Pour comparer correctement les arêtes, utilisez la méthode is_same_edge().
    """
    hex: HexCoord
    direction: int  # 0-5

    def __post_init__(self) -> None:
        assert 0 <= self.direction < 6, "Direction must be 0-5"

    def adjacent_edges(self) -> list['EdgeCoord']:
        """Retourne les 4 arêtes adjacentes."""
        neighbors = self.hex.neighbors()
        return [
            EdgeCoord(self.hex, (self.direction - 1) % 6),
            EdgeCoord(self.hex, (self.direction + 1) % 6),
            EdgeCoord(neighbors[self.direction], (self.direction + 2) % 6),
            EdgeCoord(neighbors[self.direction], (self.direction + 4) % 6),
        ]

    def vertices(self) -> tuple[VertexCoord, VertexCoord]:
        """Retourne les 2 sommets aux extrémités de cette arête."""
        return (
            VertexCoord(self.hex, self.direction),
            VertexCoord(self.hex, (self.direction + 1) % 6),
        )

    def is_same_edge(self, other: 'EdgeCoord') -> bool:
        """
        Vérifie si deux EdgeCoord représentent la même arête physique.
        Deux arêtes sont identiques si elles partagent les mêmes 2 sommets.
        """
        v1_self, v2_self = self.vertices()
        v1_other, v2_other = other.vertices()
        return (v1_self.is_same_vertex(v1_other) and v2_self.is_same_vertex(v2_other)) or \
               (v1_self.is_same_vertex(v2_other) and v2_self.is_same_vertex(v1_other))


@dataclass
class Hex:
    """Un hexagone sur le plateau."""
    coord: HexCoord
    terrain: TerrainType
    number: Optional[int]  # None pour le désert
    has_robber: bool = False

    def produces_resource(self) -> Optional[ResourceType]:
        """Retourne la ressource produite par ce terrain."""
        if self.terrain == TerrainType.DESERT:
            return None
        return ResourceType(self.terrain.value)


class Board:
    """
    Représentation du plateau de Catan.

    Optimisé pour:
    - Recherche rapide des hexagones, sommets, arêtes
    - Validation efficace des placements
    - Calcul rapide des ressources produites
    """

    def __init__(self, hexes: list[Hex]):
        self.hexes: dict[HexCoord, Hex] = {h.coord: h for h in hexes}

        # Pré-calculer tous les sommets et arêtes valides
        self.vertices: set[VertexCoord] = self._compute_valid_vertices()
        self.edges: set[EdgeCoord] = self._compute_valid_edges()

        # Index inversé pour retrouver rapidement les hexagones par numéro
        self.hexes_by_number: dict[int, list[Hex]] = {}
        for hex in hexes:
            if hex.number is not None:
                self.hexes_by_number.setdefault(hex.number, []).append(hex)

    def _compute_valid_vertices(self) -> set[VertexCoord]:
        """Calcule tous les sommets valides du plateau."""
        vertices = set()
        for hex_coord in self.hexes:
            for direction in range(6):
                vertex = VertexCoord(hex_coord, direction)
                # Vérifier que les 3 hexagones adjacents existent
                adjacent = vertex.adjacent_hexes()
                if all(h in self.hexes for h in adjacent):
                    vertices.add(vertex)
        return vertices

    def is_valid_vertex(self, vertex: VertexCoord) -> bool:
        """Vérifie si un sommet est valide (tous ses hexagones adjacents existent)."""
        return all(h in self.hexes for h in vertex.adjacent_hexes())

    def contains_vertex(self, vertex: VertexCoord) -> bool:
        """Vérifie si un sommet est dans le set des sommets valides du plateau (avec comparaison physique)."""
        for v in self.vertices:
            if vertex.is_same_vertex(v):
                return True
        return False

    def _compute_valid_edges(self) -> set[EdgeCoord]:
        """Calcule toutes les arêtes valides du plateau."""
        edges = set()
        for hex_coord in self.hexes:
            for direction in range(6):
                edge = EdgeCoord(hex_coord, direction)
                # Vérifier que les 2 hexagones adjacents existent
                neighbor = hex_coord.neighbors()[direction]
                if neighbor in self.hexes:
                    edges.add(edge)
        return edges

    def get_hexes_for_roll(self, roll: int) -> list[Hex]:
        """Retourne les hexagones qui produisent pour un jet de dé donné."""
        return [h for h in self.hexes_by_number.get(roll, []) if not h.has_robber]

    @staticmethod
    def create_standard_board(shuffle: bool = True) -> 'Board':
        """
        Crée un plateau standard de Catan.

        Si shuffle=True, mélange aléatoirement les terrains et numéros.
        Sinon, utilise la disposition recommandée du jeu de base.

        Le plateau standard est composé de 19 hexagones disposés ainsi:
               x x x
              x x x x
             x x x x x
              x x x x
               x x x
        """
        # Définir les coordonnées des 19 hexagones du plateau standard
        # En utilisant un système de coordonnées cubiques centré sur (0,0)
        hex_coords = [
            # Rangée du haut (3 hexagones)
            HexCoord(0, -2), HexCoord(1, -2), HexCoord(2, -2),
            # Deuxième rangée (4 hexagones)
            HexCoord(-1, -1), HexCoord(0, -1), HexCoord(1, -1), HexCoord(2, -1),
            # Rangée centrale (5 hexagones)
            HexCoord(-2, 0), HexCoord(-1, 0), HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0),
            # Quatrième rangée (4 hexagones)
            HexCoord(-2, 1), HexCoord(-1, 1), HexCoord(0, 1), HexCoord(1, 1),
            # Rangée du bas (3 hexagones)
            HexCoord(-2, 2), HexCoord(-1, 2), HexCoord(0, 2),
        ]

        # Distribution des terrains dans le jeu standard
        # 4 forêts, 4 pâturages, 4 champs, 3 collines, 3 montagnes, 1 désert
        terrain_distribution = [
            TerrainType.FOREST, TerrainType.FOREST, TerrainType.FOREST, TerrainType.FOREST,
            TerrainType.PASTURE, TerrainType.PASTURE, TerrainType.PASTURE, TerrainType.PASTURE,
            TerrainType.FIELDS, TerrainType.FIELDS, TerrainType.FIELDS, TerrainType.FIELDS,
            TerrainType.HILLS, TerrainType.HILLS, TerrainType.HILLS,
            TerrainType.MOUNTAINS, TerrainType.MOUNTAINS, TerrainType.MOUNTAINS,
            TerrainType.DESERT,
        ]

        # Numéros des dés (pas de 7, et pas de numéro pour le désert)
        # Distribution: 1x(2,12), 2x(3,4,5,6,8,9,10,11)
        number_distribution = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]

        if shuffle:
            # Mélanger les terrains et les numéros
            import random
            random.shuffle(terrain_distribution)
            random.shuffle(number_distribution)

        # Créer les hexagones
        hexes = []
        number_idx = 0

        for i, coord in enumerate(hex_coords):
            terrain = terrain_distribution[i]

            if terrain == TerrainType.DESERT:
                # Le désert n'a pas de numéro et commence avec le voleur
                hexes.append(Hex(coord, terrain, None, has_robber=True))
            else:
                # Assigner un numéro du dé
                number = number_distribution[number_idx]
                number_idx += 1
                hexes.append(Hex(coord, terrain, number, has_robber=False))

        return Board(hexes)
