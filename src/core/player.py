"""Player state representation."""

from dataclasses import dataclass, field
import numpy as np

from .constants import (
    ResourceType,
    DevelopmentCardType,
    BuildingType,
    NUM_RESOURCES,
    MAX_SETTLEMENTS_PER_PLAYER,
    MAX_CITIES_PER_PLAYER,
    MAX_ROADS_PER_PLAYER,
)
from .board import VertexCoord, EdgeCoord


@dataclass
class PlayerState:
    """
    État d'un joueur.

    Optimisé pour:
    - Accès rapide aux ressources (numpy array)
    - Recherche efficace des constructions
    - Calcul rapide des points de victoire
    """

    player_id: int

    # Ressources (indexées par ResourceType)
    resources: np.ndarray = field(default_factory=lambda: np.zeros(NUM_RESOURCES, dtype=np.int32))

    # Cartes développement
    dev_cards_in_hand: dict[DevelopmentCardType, int] = field(default_factory=dict)
    dev_cards_played: dict[DevelopmentCardType, int] = field(default_factory=dict)
    dev_cards_bought_this_turn: list[DevelopmentCardType] = field(default_factory=list)
    dev_card_played_this_turn: bool = False  # Une seule carte développement par tour

    # Constructions sur le plateau
    settlements: set[VertexCoord] = field(default_factory=set)
    cities: set[VertexCoord] = field(default_factory=set)
    roads: set[EdgeCoord] = field(default_factory=set)

    # Chevaliers joués (pour l'armée la plus grande)
    knights_played: int = 0

    # Bonus
    has_longest_road: bool = False
    has_largest_army: bool = False

    def total_resources(self) -> int:
        """Retourne le nombre total de ressources."""
        return int(np.sum(self.resources))

    def can_afford(self, cost: dict[ResourceType, int]) -> bool:
        """Vérifie si le joueur peut payer un coût."""
        for resource, amount in cost.items():
            if self.resources[resource] < amount:
                return False
        return True

    def pay(self, cost: dict[ResourceType, int]) -> None:
        """Paie un coût en ressources."""
        for resource, amount in cost.items():
            self.resources[resource] -= amount
            assert self.resources[resource] >= 0, f"Negative resources for {resource}"

    def receive(self, resources: dict[ResourceType, int]) -> None:
        """Reçoit des ressources."""
        for resource, amount in resources.items():
            self.resources[resource] += amount

    def victory_points(self) -> int:
        """Calcule le nombre de points de victoire."""
        points = 0

        # Points des colonies et villes
        points += len(self.settlements) * 1
        points += len(self.cities) * 2

        # Points des cartes développement "Point de victoire"
        points += self.dev_cards_in_hand.get(DevelopmentCardType.VICTORY_POINT, 0)
        points += self.dev_cards_played.get(DevelopmentCardType.VICTORY_POINT, 0)

        # Bonus
        if self.has_longest_road:
            points += 2
        if self.has_largest_army:
            points += 2

        return points

    def can_build_settlement(self) -> bool:
        """Vérifie si le joueur a encore des colonies disponibles."""
        return len(self.settlements) < MAX_SETTLEMENTS_PER_PLAYER

    def can_build_city(self) -> bool:
        """Vérifie si le joueur a encore des villes disponibles."""
        return len(self.cities) < MAX_CITIES_PER_PLAYER

    def can_build_road(self) -> bool:
        """Vérifie si le joueur a encore des routes disponibles."""
        return len(self.roads) < MAX_ROADS_PER_PLAYER

    def longest_road_length(self) -> int:
        """
        Calcule la longueur de la plus longue route.

        Algorithme de parcours en profondeur pour trouver le plus long chemin.
        Suit les arêtes (edges) plutôt que les sommets pour gérer correctement les boucles.
        """
        if not self.roads:
            return 0

        # Créer une clé unique pour chaque arête basée sur ses sommets
        def edge_key(e: EdgeCoord) -> tuple:
            v1, v2 = e.vertices()
            # Créer des clés de sommets basées sur les hexagones adjacents
            k1 = tuple(sorted([(h.q, h.r) for h in v1.adjacent_hexes()]))
            k2 = tuple(sorted([(h.q, h.r) for h in v2.adjacent_hexes()]))
            # Normaliser l'arête (ordre des sommets n'importe pas)
            return tuple(sorted([k1, k2]))

        def vertex_key(v: VertexCoord) -> tuple:
            """Crée une clé unique pour un sommet physique basée sur ses hexagones adjacents."""
            return tuple(sorted([(h.q, h.r) for h in v.adjacent_hexes()]))

        # Construire un graphe: vertex -> list of (neighbor_vertex, edge_key)
        graph: dict[tuple, list[tuple[tuple, tuple]]] = {}

        for edge in self.roads:
            v1, v2 = edge.vertices()
            k1, k2 = vertex_key(v1), vertex_key(v2)
            ek = edge_key(edge)

            graph.setdefault(k1, []).append((k2, ek))
            graph.setdefault(k2, []).append((k1, ek))

        # DFS depuis chaque sommet pour trouver le plus long chemin
        # En suivant les arêtes (pas les sommets)
        max_length = 0

        def dfs(current_vertex: tuple, visited_edges: set[tuple], length: int) -> int:
            max_len = length
            for neighbor, edge_k in graph.get(current_vertex, []):
                if edge_k not in visited_edges:
                    visited_edges.add(edge_k)
                    max_len = max(max_len, dfs(neighbor, visited_edges, length + 1))
                    visited_edges.remove(edge_k)
            return max_len

        for start_vertex in graph:
            visited_edges: set[tuple] = set()
            length = dfs(start_vertex, visited_edges, 0)
            max_length = max(max_length, length)

        return max_length

    def __repr__(self) -> str:
        return (
            f"Player{self.player_id}("
            f"VP={self.victory_points()}, "
            f"resources={self.total_resources()}, "
            f"settlements={len(self.settlements)}, "
            f"cities={len(self.cities)}, "
            f"roads={len(self.roads)})"
        )
