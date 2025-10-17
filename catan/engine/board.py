"""Plateau de jeu Catane 1v1 (ENG-001).

Cette implémentation expose un plateau complet conforme aux spécifications:
- coordonnées cube pour chaque tuile
- indexation déterministe des sommets/arêtes (géométrie pointy-top)
- attribution des numéros de dés et ports (9 ports, 5 spécifiques + 4 génériques)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class CubeCoord:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class Tile:
    tile_id: int
    resource: str
    pip: int | None
    cube: CubeCoord
    vertices: Tuple[int, ...]
    edges: Tuple[int, ...]
    has_robber: bool


@dataclass(frozen=True)
class Vertex:
    vertex_id: int
    position: Tuple[float, float]
    adjacent_tiles: Tuple[int, ...]
    edges: Tuple[int, ...]


@dataclass(frozen=True)
class Edge:
    edge_id: int
    vertices: Tuple[int, int]
    tiles: Tuple[int, ...]


@dataclass(frozen=True)
class Port:
    port_id: int
    kind: str
    edge_id: int
    vertices: Tuple[int, int]


class Board:
    """Représentation immuable du plateau standard."""

    # Ressources + coordonnées (spirale autour du désert)
    _TILE_LAYOUT: List[Tuple[int, str, Tuple[int, int, int]]] = [
        (0, "DESERT", (0, 0, 0)),
        (1, "ORE", (1, -1, 0)),
        (2, "GRAIN", (1, 0, -1)),
        (3, "WOOL", (0, 1, -1)),
        (4, "BRICK", (-1, 1, 0)),
        (5, "LUMBER", (-1, 0, 1)),
        (6, "GRAIN", (0, -1, 1)),
        (7, "LUMBER", (2, -1, -1)),
        (8, "BRICK", (2, 0, -2)),
        (9, "WOOL", (1, 1, -2)),
        (10, "ORE", (0, 2, -2)),
        (11, "GRAIN", (-1, 2, -1)),
        (12, "LUMBER", (-2, 2, 0)),
        (13, "BRICK", (-2, 1, 1)),
        (14, "WOOL", (-2, 0, 2)),
        (15, "LUMBER", (-1, -1, 2)),
        (16, "GRAIN", (0, -2, 2)),
        (17, "WOOL", (1, -2, 1)),
        (18, "ORE", (2, -2, 0)),
    ]

    _PIP_NUMBERS: Dict[int, int] = {
        1: 5,
        2: 2,
        3: 6,
        4: 3,
        5: 8,
        6: 10,
        7: 9,
        8: 12,
        9: 11,
        10: 4,
        11: 8,
        12: 10,
        13: 9,
        14: 4,
        15: 5,
        16: 6,
        17: 3,
        18: 11,
    }

    # Port specs exprimés en coordonnées de sommets (pointy-top)
    _PORT_COORDS: List[Tuple[str, Tuple[Tuple[float, float], Tuple[float, float]]]] = [
        ("ANY", ((-4.330127, -0.5), (-3.464102, -1.0))),
        ("BRICK", ((-2.598076, -3.5), (-1.732051, -4.0))),
        ("ANY", ((0.866025, -3.5), (1.732051, -4.0))),
        ("ORE", ((3.464102, -2.0), (3.464102, -1.0))),
        ("ANY", ((3.464102, 1.0), (4.330127, 0.5))),
        ("WOOL", ((2.598076, 2.5), (2.598076, 3.5))),
        ("ANY", ((0.0, 4.0), (0.866025, 3.5))),
        ("GRAIN", ((-2.598076, 3.5), (-1.732051, 4.0))),
        ("LUMBER", ((-3.464102, 1.0), (-3.464102, 2.0))),
    ]

    _SQRT3: float = math.sqrt(3.0)
    _ROUND_PRECISION = 6
    _VERTEX_OFFSETS: Tuple[Tuple[float, float], ...] = tuple(
        (math.cos(math.radians(30 + 60 * k)), math.sin(math.radians(30 + 60 * k)))
        for k in range(6)
    )

    def __init__(
        self,
        tiles: Dict[int, Tile],
        vertices: Dict[int, Vertex],
        edges: Dict[int, Edge],
        ports: Iterable[Port],
    ) -> None:
        self.tiles: Dict[int, Tile] = tiles
        self.vertices: Dict[int, Vertex] = vertices
        self.edges: Dict[int, Edge] = edges
        self.ports: Tuple[Port, ...] = tuple(sorted(ports, key=lambda p: p.port_id))

    # -- API comptage --
    def tile_count(self) -> int:
        return len(self.tiles)

    def vertex_count(self) -> int:
        return len(self.vertices)

    def edge_count(self) -> int:
        return len(self.edges)

    # -- Construction du plateau --
    @classmethod
    def standard(cls) -> "Board":
        tile_vertex_coords: Dict[int, Tuple[Tuple[float, float], ...]] = {}
        tile_edge_coords: Dict[int, Tuple[Tuple[Tuple[float, float], Tuple[float, float]], ...]] = {}
        vertex_tiles: Dict[Tuple[float, float], set[int]] = {}
        edge_tiles: Dict[Tuple[Tuple[float, float], Tuple[float, float]], set[int]] = {}

        def cube_to_axial(cube: Tuple[int, int, int]) -> Tuple[int, int]:
            x, y, z = cube
            return x, z

        def axial_to_pixel(q: int, r: int) -> Tuple[float, float]:
            x = cls._SQRT3 * (q + r / 2)
            y = 1.5 * r
            return x, y

        def round_coord(value: float) -> float:
            return round(value, cls._ROUND_PRECISION)

        # Pré-calcul sommets/arêtes pour chaque tuile
        for tile_id, resource, cube in cls._TILE_LAYOUT:
            q, r = cube_to_axial(cube)
            cx, cy = axial_to_pixel(q, r)
            vertices: List[Tuple[float, float]] = []

            for dx, dy in cls._VERTEX_OFFSETS:
                coord = (round_coord(cx + dx), round_coord(cy + dy))
                vertices.append(coord)
                vertex_tiles.setdefault(coord, set()).add(tile_id)

            tile_vertex_coords[tile_id] = tuple(vertices)

            edges_for_tile: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
            for idx in range(6):
                a = vertices[idx]
                b = vertices[(idx + 1) % 6]
                edge = tuple(sorted((a, b)))
                edges_for_tile.append(edge)
                edge_tiles.setdefault(edge, set()).add(tile_id)
            tile_edge_coords[tile_id] = tuple(edges_for_tile)

        # Indexation déterministe
        sorted_vertex_coords = sorted(vertex_tiles.keys())
        vertex_coord_to_id = {
            coord: idx for idx, coord in enumerate(sorted_vertex_coords)
        }

        sorted_edge_coords = sorted(edge_tiles.keys())
        edge_coord_to_id = {coord: idx for idx, coord in enumerate(sorted_edge_coords)}

        # Construire les sommets/arêtes
        vertex_edges_map: Dict[Tuple[float, float], List[int]] = {
            coord: [] for coord in sorted_vertex_coords
        }
        for edge_coord, edge_id in edge_coord_to_id.items():
            a, b = edge_coord
            vertex_edges_map[a].append(edge_id)
            vertex_edges_map[b].append(edge_id)

        vertices: Dict[int, Vertex] = {}
        for coord, vid in vertex_coord_to_id.items():
            x, y = coord
            tiles = tuple(sorted(vertex_tiles[coord]))
            edges = tuple(sorted(vertex_edges_map[coord]))
            vertices[vid] = Vertex(
                vertex_id=vid,
                position=(x, y),
                adjacent_tiles=tiles,
                edges=edges,
            )

        edges: Dict[int, Edge] = {}
        for coord_pair, edge_id in edge_coord_to_id.items():
            a, b = coord_pair
            vertex_pair = tuple(
                sorted((vertex_coord_to_id[a], vertex_coord_to_id[b]))
            )
            tiles = tuple(sorted(edge_tiles[coord_pair]))
            edges[edge_id] = Edge(
                edge_id=edge_id,
                vertices=vertex_pair,
                tiles=tiles,
            )

        tiles: Dict[int, Tile] = {}
        for tile_id, resource, cube in cls._TILE_LAYOUT:
            cube_coord = CubeCoord(*cube)
            vertex_ids = tuple(vertex_coord_to_id[c] for c in tile_vertex_coords[tile_id])
            edge_ids = tuple(edge_coord_to_id[e] for e in tile_edge_coords[tile_id])
            tile = Tile(
                tile_id=tile_id,
                resource=resource,
                pip=cls._PIP_NUMBERS.get(tile_id),
                cube=cube_coord,
                vertices=vertex_ids,
                edges=edge_ids,
                has_robber=(tile_id == 0),
            )
            tiles[tile_id] = tile

        # Ports
        ports: List[Port] = []
        for port_id, (kind, (coord_a, coord_b)) in enumerate(cls._PORT_COORDS):
            a = tuple(coord_a)
            b = tuple(coord_b)
            vertex_pair = tuple(
                sorted((vertex_coord_to_id[a], vertex_coord_to_id[b]))
            )
            edge_coord = tuple(sorted((a, b)))
            edge_id = edge_coord_to_id[edge_coord]
            ports.append(
                Port(
                    port_id=port_id,
                    kind=kind,
                    edge_id=edge_id,
                    vertices=vertex_pair,
                )
            )

        return cls(tiles=tiles, vertices=vertices, edges=edges, ports=ports)


__all__ = [
    "Board",
    "CubeCoord",
    "Tile",
    "Vertex",
    "Edge",
    "Port",
]
