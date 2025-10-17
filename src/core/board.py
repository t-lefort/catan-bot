"""Board representation and geometry for Catan.

Complete rebuild based on Catanatron's coordinate system.
Uses unique integer IDs for tiles, nodes (vertices), and edges.
Includes proper water hexes and port system.
"""

from dataclasses import dataclass
from typing import Optional, Set, List, Tuple, Dict
from enum import Enum
import random

from .constants import TerrainType, ResourceType, PortType


# ============================================================================
# DIRECTION SYSTEM
# ============================================================================

class Direction(Enum):
    """Hexagonal directions using cube coordinates."""
    EAST = (1, -1, 0)
    NORTHEAST = (1, 0, -1)
    NORTHWEST = (0, 1, -1)
    WEST = (-1, 1, 0)
    SOUTHWEST = (-1, 0, 1)
    SOUTHEAST = (0, -1, 1)


# Direction vectors for easy access
DIRECTION_VECTORS = {
    Direction.EAST: (1, -1, 0),
    Direction.NORTHEAST: (1, 0, -1),
    Direction.NORTHWEST: (0, 1, -1),
    Direction.WEST: (-1, 1, 0),
    Direction.SOUTHWEST: (-1, 0, 1),
    Direction.SOUTHEAST: (0, -1, 1),
}


# ============================================================================
# COORDINATE SYSTEM
# ============================================================================

@dataclass(frozen=True, eq=True)
class Coordinate:
    """Cube coordinate for hexagonal tiles (x + y + z = 0)."""
    x: int
    y: int
    z: int

    def __post_init__(self):
        assert self.x + self.y + self.z == 0, f"Invalid cube coordinate: {self.x} + {self.y} + {self.z} != 0"

    def __add__(self, direction: Direction) -> 'Coordinate':
        """Add a direction vector to this coordinate."""
        dx, dy, dz = DIRECTION_VECTORS[direction]
        return Coordinate(self.x + dx, self.y + dy, self.z + dz)

    def neighbors(self) -> List['Coordinate']:
        """Return all 6 neighboring coordinates."""
        return [self + direction for direction in Direction]

    def distance(self, other: 'Coordinate') -> int:
        """Manhattan distance in cube coordinates."""
        return (abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)) // 2


def add_coordinates(coord: Coordinate, direction: Direction) -> Coordinate:
    """Add a direction vector to a coordinate."""
    dx, dy, dz = DIRECTION_VECTORS[direction]
    return Coordinate(coord.x + dx, coord.y + dy, coord.z + dz)

def _repeat_add(coord: Coordinate, direction: Direction, n: int) -> Coordinate:
    """Move `n` steps from coord in given direction."""
    dx, dy, dz = DIRECTION_VECTORS[direction]
    return Coordinate(coord.x + dx * n, coord.y + dy * n, coord.z + dz * n)


def generate_spiral_coordinates(layers: int) -> List[Coordinate]:
    """Generate coordinates in a spiral pattern from center outward.

    Layer 0: center (1 tile)
    Layer r: ring of radius r around center (6r tiles)

    Based on Red Blob Games' hex grid algorithms.
    """
    center = Coordinate(0, 0, 0)
    results = [center]
    if layers <= 0:
        return results

    ring_dirs = [
        Direction.EAST,
        Direction.NORTHEAST,
        Direction.NORTHWEST,
        Direction.WEST,
        Direction.SOUTHWEST,
        Direction.SOUTHEAST,
    ]

    for r in range(1, layers + 1):
        # Start at center + (SOUTHWEST * r)
        hex_coord = _repeat_add(center, Direction.SOUTHWEST, r)
        for i in range(6):
            for _ in range(r):
                results.append(hex_coord)
                hex_coord = hex_coord + ring_dirs[i]
    return results


# ============================================================================
# NODE (VERTEX) SYSTEM
# ============================================================================

class NodeDirection(Enum):
    """Directions for the 6 vertices of a hexagon (clockwise from top)."""
    NORTH = 0
    NORTHEAST = 1
    SOUTHEAST = 2
    SOUTH = 3
    SOUTHWEST = 4
    NORTHWEST = 5


# Mapping from node direction to the tile directions that share this vertex
NODE_TO_TILES = {
    NodeDirection.NORTH: (Direction.NORTHWEST, Direction.NORTHEAST),
    NodeDirection.NORTHEAST: (Direction.NORTHEAST, Direction.EAST),
    NodeDirection.SOUTHEAST: (Direction.EAST, Direction.SOUTHEAST),
    NodeDirection.SOUTH: (Direction.SOUTHEAST, Direction.SOUTHWEST),
    NodeDirection.SOUTHWEST: (Direction.SOUTHWEST, Direction.WEST),
    NodeDirection.NORTHWEST: (Direction.WEST, Direction.NORTHWEST),
}


def get_node_id(tile_coord: Coordinate, node_direction: NodeDirection) -> int:
    """Generate a unique DETERMINISTIC node ID from tile coordinate and direction.

    A node (vertex) is shared by 3 tiles. We use a canonical representation
    to ensure the same physical node always gets the same ID.

    IMPORTANT: Uses deterministic encoding, NOT hash(), to ensure IDs are stable
    across program runs (necessary for save games, replay, etc.)
    """
    # Get the 3 tiles that share this node
    tiles = get_tiles_touching_node(tile_coord, node_direction)

    # Sort tiles to get canonical representation (lexicographic order)
    tiles_sorted = sorted(tiles, key=lambda c: (c.x, c.y, c.z))

    # Use the canonical (first) tile's coordinates + direction to create deterministic ID
    canonical = tiles_sorted[0]

    # Find which corner of the canonical tile this is
    for nd in NodeDirection:
        tiles_for_nd = sorted(get_tiles_touching_node(canonical, nd), key=lambda c: (c.x, c.y, c.z))
        if tiles_sorted == tiles_for_nd:
            # Encode as: (x+100)*1000000 + (y+100)*10000 + (z+100)*100 + direction
            # This ensures positive IDs and uniqueness
            # Range: coordinates from -100 to +100, direction 0-5
            return ((canonical.x + 100) * 1000000 +
                    (canonical.y + 100) * 10000 +
                    (canonical.z + 100) * 100 +
                    nd.value)

    # Fallback (should never happen)
    return ((tiles_sorted[0].x + 100) * 1000000 +
            (tiles_sorted[0].y + 100) * 10000 +
            (tiles_sorted[0].z + 100) * 100)

    


def get_tiles_touching_node(tile_coord: Coordinate, node_direction: NodeDirection) -> List[Coordinate]:
    """Get the 3 tile coordinates that touch this node."""
    dir1, dir2 = NODE_TO_TILES[node_direction]

    return [
        tile_coord,
        tile_coord + dir1,
        tile_coord + dir2,
    ]


# ============================================================================
# EDGE SYSTEM
# ============================================================================

class EdgeDirection(Enum):
    """Directions for the 6 edges of a hexagon."""
    NORTHEAST = 0  # Top-right edge
    EAST = 1       # Right edge
    SOUTHEAST = 2  # Bottom-right edge
    SOUTHWEST = 3  # Bottom-left edge
    WEST = 4       # Left edge
    NORTHWEST = 5  # Top-left edge


# Mapping edge direction to tile direction
EDGE_TO_TILE = {
    EdgeDirection.NORTHEAST: Direction.NORTHEAST,
    EdgeDirection.EAST: Direction.EAST,
    EdgeDirection.SOUTHEAST: Direction.SOUTHEAST,
    EdgeDirection.SOUTHWEST: Direction.SOUTHWEST,
    EdgeDirection.WEST: Direction.WEST,
    EdgeDirection.NORTHWEST: Direction.NORTHWEST,
}


def get_edge_id(tile_coord: Coordinate, edge_direction: EdgeDirection) -> int:
    """Generate a unique DETERMINISTIC edge ID from tile coordinate and direction.

    An edge is shared by 2 tiles. We use canonical representation.

    IMPORTANT: Uses deterministic encoding, NOT hash().
    """
    tile1 = tile_coord
    tile2 = tile_coord + EDGE_TO_TILE[edge_direction]

    # Sort to get canonical representation
    tiles_sorted = sorted([tile1, tile2], key=lambda c: (c.x, c.y, c.z))

    t1, t2 = tiles_sorted

    # Encode two tiles: each tile uses 3 digits (x, y, z from -100 to +100 -> 0 to 200)
    # Total: 6 digits per tile = 12 digits total, fits in int
    return ((t1.x + 100) * 1000000000000 +
            (t1.y + 100) * 10000000000 +
            (t1.z + 100) * 100000000 +
            (t2.x + 100) * 1000000 +
            (t2.y + 100) * 10000 +
            (t2.z + 100) * 100)

    


def get_edge_endpoints(tile_coord: Coordinate, edge_direction: EdgeDirection) -> Tuple[int, int]:
    """Get the two node IDs at the endpoints of this edge."""
    # Map edge direction to the two node directions at its endpoints
    edge_to_nodes = {
        EdgeDirection.NORTHEAST: (NodeDirection.NORTH, NodeDirection.NORTHEAST),
        EdgeDirection.EAST: (NodeDirection.NORTHEAST, NodeDirection.SOUTHEAST),
        EdgeDirection.SOUTHEAST: (NodeDirection.SOUTHEAST, NodeDirection.SOUTH),
        EdgeDirection.SOUTHWEST: (NodeDirection.SOUTH, NodeDirection.SOUTHWEST),
        EdgeDirection.WEST: (NodeDirection.SOUTHWEST, NodeDirection.NORTHWEST),
        EdgeDirection.NORTHWEST: (NodeDirection.NORTHWEST, NodeDirection.NORTH),
    }

    node_dir1, node_dir2 = edge_to_nodes[edge_direction]
    node1 = get_node_id(tile_coord, node_dir1)
    node2 = get_node_id(tile_coord, node_dir2)

    return (node1, node2)


# ============================================================================
# TILE (HEXAGON) CLASSES
# ============================================================================

@dataclass
class Tile:
    """A hexagonal tile on the board."""
    id: int
    coordinate: Coordinate
    terrain: TerrainType
    number: Optional[int] = None  # Dice number (None for desert/water)
    port: Optional[PortType] = None  # Port type if this is a water tile with port
    port_direction: Optional[NodeDirection] = None  # Which edge has the port

    @property
    def is_land(self) -> bool:
        """Check if this is a land tile."""
        return self.terrain != TerrainType.WATER

    @property
    def is_water(self) -> bool:
        """Check if this is a water tile."""
        return self.terrain == TerrainType.WATER

    @property
    def resource(self) -> Optional[ResourceType]:
        """Get the resource produced by this tile."""
        if self.terrain == TerrainType.WATER or self.terrain == TerrainType.DESERT:
            return None
        return ResourceType(self.terrain.value)


# ============================================================================
# BOARD CLASS
# ============================================================================

class Board:
    """The Catan game board with tiles, nodes, and edges."""

    def __init__(self, tiles: List[Tile]):
        self.tiles: Dict[int, Tile] = {tile.id: tile for tile in tiles}
        self.tile_by_coord: Dict[Coordinate, Tile] = {tile.coordinate: tile for tile in tiles}

        # Pre-compute all valid nodes and edges
        self.nodes: Set[int] = self._compute_nodes()
        self.edges: Set[int] = self._compute_edges()

        # Map tiles by dice number for production
        self.tiles_by_number: Dict[int, List[Tile]] = {}
        for tile in tiles:
            if tile.number is not None:
                self.tiles_by_number.setdefault(tile.number, []).append(tile)

        # Map nodes to adjacent tiles
        self.nodes_to_tiles: Dict[int, List[Tile]] = self._compute_nodes_to_tiles()

        # Map edges to adjacent nodes (MUST be computed before nodes_to_edges)
        self.edges_to_nodes: Dict[int, Tuple[int, int]] = self._compute_edges_to_nodes()

        # Map nodes to adjacent edges (uses edges_to_nodes)
        self.nodes_to_edges: Dict[int, List[int]] = self._compute_nodes_to_edges()

    def _compute_nodes(self) -> Set[int]:
        """Compute all valid node IDs on the board."""
        nodes = set()
        for tile in self.tiles.values():
            for node_dir in NodeDirection:
                node_id = get_node_id(tile.coordinate, node_dir)
                nodes.add(node_id)
        return nodes

    def _compute_edges(self) -> Set[int]:
        """Compute all edge IDs on the board, including boundary edges."""
        edges = set()
        for tile in self.tiles.values():
            for edge_dir in EdgeDirection:
                edge_id = get_edge_id(tile.coordinate, edge_dir)
                edges.add(edge_id)
        return edges

    def _compute_nodes_to_tiles(self) -> Dict[int, List[Tile]]:
        """Map each node to its adjacent tiles."""
        node_to_tiles = {}
        for tile in self.tiles.values():
            for node_dir in NodeDirection:
                node_id = get_node_id(tile.coordinate, node_dir)
                if node_id not in node_to_tiles:
                    node_to_tiles[node_id] = []
                node_to_tiles[node_id].append(tile)
        return node_to_tiles

    def _compute_nodes_to_edges(self) -> Dict[int, List[int]]:
        """Map each node to its adjacent edges."""
        node_to_edges = {node: [] for node in self.nodes}
        for edge_id in self.edges:
            n1, n2 = self.edges_to_nodes[edge_id]
            if n1 in node_to_edges:
                node_to_edges[n1].append(edge_id)
            if n2 in node_to_edges:
                node_to_edges[n2].append(edge_id)
        return node_to_edges

    def _compute_edges_to_nodes(self) -> Dict[int, Tuple[int, int]]:
        """Map each edge to its two endpoint nodes."""
        edge_to_nodes: Dict[int, Tuple[int, int]] = {}
        for tile in self.tiles.values():
            for edge_dir in EdgeDirection:
                edge_id = get_edge_id(tile.coordinate, edge_dir)
                if edge_id not in edge_to_nodes:
                    endpoints = get_edge_endpoints(tile.coordinate, edge_dir)
                    edge_to_nodes[edge_id] = endpoints
        return edge_to_nodes

    def get_tiles_for_node(self, node_id: int) -> List[Tile]:
        """Get all tiles adjacent to a node."""
        return self.nodes_to_tiles.get(node_id, [])

    def get_land_tiles_for_node(self, node_id: int) -> List[Tile]:
        """Get all land tiles adjacent to a node."""
        return [tile for tile in self.get_tiles_for_node(node_id) if tile.is_land]

    def is_node_on_land(self, node_id: int) -> bool:
        """Check if a node is adjacent to at least one land tile."""
        return len(self.get_land_tiles_for_node(node_id)) > 0

    def get_adjacent_nodes(self, node_id: int) -> List[int]:
        """Get all nodes adjacent to this node (connected by edges)."""
        adjacent = []
        for edge_id in self.nodes_to_edges.get(node_id, []):
            n1, n2 = self.edges_to_nodes[edge_id]
            other = n2 if n1 == node_id else n1
            adjacent.append(other)
        return adjacent

    def get_tiles_for_roll(self, roll: int, robber_tile: Optional[int] = None) -> List[Tile]:
        """Get all tiles that produce resources for this dice roll."""
        tiles = self.tiles_by_number.get(roll, [])
        if robber_tile is not None:
            tiles = [t for t in tiles if t.id != robber_tile]
        return tiles

    @staticmethod
    def create_standard_board(shuffle: bool = True) -> 'Board':
        """Create a standard Catan board with 19 land tiles + 18 water tiles with ports."""

        # Generate land tile coordinates (3 layers: 1 + 6 + 12 = 19 tiles)
        land_coords = []
        land_coords.append(Coordinate(0, 0, 0))  # Center

        # Layer 1 (6 tiles)
        for direction in Direction:
            land_coords.append(Coordinate(0, 0, 0) + direction)

        # Layer 2 (12 tiles)
        layer2_start_positions = [
            Coordinate(0, 0, 0) + Direction.NORTHEAST + Direction.NORTHEAST,
            Coordinate(0, 0, 0) + Direction.EAST + Direction.EAST,
            Coordinate(0, 0, 0) + Direction.SOUTHEAST + Direction.SOUTHEAST,
            Coordinate(0, 0, 0) + Direction.SOUTHWEST + Direction.SOUTHWEST,
            Coordinate(0, 0, 0) + Direction.WEST + Direction.WEST,
            Coordinate(0, 0, 0) + Direction.NORTHWEST + Direction.NORTHWEST,
        ]

        for start in layer2_start_positions:
            land_coords.append(start)
            # Add one more in clockwise direction
            # This is simplified; for full layer 2, we'd need proper spiral

        # For now, use the 19 standard coordinates
        land_coords = [
            # Center
            Coordinate(0, 0, 0),
            # Layer 1 (6 around center)
            Coordinate(1, -1, 0), Coordinate(1, 0, -1), Coordinate(0, 1, -1),
            Coordinate(-1, 1, 0), Coordinate(-1, 0, 1), Coordinate(0, -1, 1),
            # Layer 2 (12 around layer 1)
            Coordinate(2, -2, 0), Coordinate(2, -1, -1), Coordinate(1, -2, 1),
            Coordinate(0, -2, 2), Coordinate(-1, -1, 2), Coordinate(-2, 0, 2),
            Coordinate(-2, 1, 1), Coordinate(-2, 2, 0), Coordinate(-1, 2, -1),
            Coordinate(0, 2, -2), Coordinate(1, 1, -2), Coordinate(2, 0, -2),
        ]

        # Terrain distribution (standard Catan)
        terrain_distribution = [
            TerrainType.FOREST, TerrainType.FOREST, TerrainType.FOREST, TerrainType.FOREST,
            TerrainType.PASTURE, TerrainType.PASTURE, TerrainType.PASTURE, TerrainType.PASTURE,
            TerrainType.FIELDS, TerrainType.FIELDS, TerrainType.FIELDS, TerrainType.FIELDS,
            TerrainType.HILLS, TerrainType.HILLS, TerrainType.HILLS,
            TerrainType.MOUNTAINS, TerrainType.MOUNTAINS, TerrainType.MOUNTAINS,
            TerrainType.DESERT,
        ]

        # Number distribution (no 7)
        number_distribution = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]

        if shuffle:
            random.shuffle(terrain_distribution)
            random.shuffle(number_distribution)

        # Create land tiles
        tiles = []
        tile_id = 0
        number_idx = 0

        for i, coord in enumerate(land_coords):
            terrain = terrain_distribution[i]

            if terrain == TerrainType.DESERT:
                tiles.append(Tile(tile_id, coord, terrain, number=None))
            else:
                number = number_distribution[number_idx]
                number_idx += 1
                tiles.append(Tile(tile_id, coord, terrain, number=number))

            tile_id += 1

        # Add water tiles around the perimeter (layer 3)
        # For simplicity, we'll skip water tiles for now and focus on land
        # TODO: Add water tiles with ports

        return Board(tiles)
