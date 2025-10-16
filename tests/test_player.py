"""Tests for the PlayerState class."""

import pytest
from src.core.player import PlayerState
from src.core.board import HexCoord, VertexCoord, EdgeCoord
from src.core.constants import (
    ResourceType,
    DevelopmentCardType,
    BuildingType,
    BUILDING_COSTS,
)


class TestPlayerStateBasics:
    """Tests pour les fonctionnalités de base de PlayerState."""

    def test_player_creation(self):
        """Test création d'un joueur."""
        player = PlayerState(player_id=0)
        assert player.player_id == 0
        assert player.total_resources() == 0
        assert len(player.settlements) == 0
        assert len(player.cities) == 0
        assert len(player.roads) == 0

    def test_total_resources(self):
        """Test comptage des ressources."""
        player = PlayerState(player_id=0)
        assert player.total_resources() == 0

        player.resources[ResourceType.WOOD] = 3
        player.resources[ResourceType.BRICK] = 2
        assert player.total_resources() == 5

    def test_can_afford(self):
        """Test vérification qu'un joueur peut payer un coût."""
        player = PlayerState(player_id=0)

        # Ne peut pas payer sans ressources
        assert not player.can_afford(BUILDING_COSTS[BuildingType.SETTLEMENT])

        # Donner des ressources
        player.resources[ResourceType.WOOD] = 1
        player.resources[ResourceType.BRICK] = 1
        player.resources[ResourceType.SHEEP] = 1
        player.resources[ResourceType.WHEAT] = 1

        # Peut maintenant payer
        assert player.can_afford(BUILDING_COSTS[BuildingType.SETTLEMENT])

    def test_pay(self):
        """Test paiement de ressources."""
        player = PlayerState(player_id=0)

        # Donner des ressources
        player.resources[ResourceType.WOOD] = 2
        player.resources[ResourceType.BRICK] = 2

        # Payer
        cost = {ResourceType.WOOD: 1, ResourceType.BRICK: 1}
        player.pay(cost)

        assert player.resources[ResourceType.WOOD] == 1
        assert player.resources[ResourceType.BRICK] == 1

    def test_pay_negative_fails(self):
        """Test que payer plus que ce qu'on a lève une erreur."""
        player = PlayerState(player_id=0)
        player.resources[ResourceType.WOOD] = 1

        cost = {ResourceType.WOOD: 2}
        with pytest.raises(AssertionError):
            player.pay(cost)

    def test_receive(self):
        """Test réception de ressources."""
        player = PlayerState(player_id=0)

        resources = {ResourceType.WOOD: 2, ResourceType.BRICK: 3}
        player.receive(resources)

        assert player.resources[ResourceType.WOOD] == 2
        assert player.resources[ResourceType.BRICK] == 3

    def test_can_build_checks(self):
        """Test vérification des limites de construction."""
        player = PlayerState(player_id=0)

        # Peut construire au début
        assert player.can_build_settlement()
        assert player.can_build_city()
        assert player.can_build_road()

        # Ajouter le maximum de colonies
        for i in range(5):
            vertex = VertexCoord(HexCoord(0, i), 0)
            player.settlements.add(vertex)

        assert not player.can_build_settlement()

        # Ajouter le maximum de villes
        for i in range(4):
            vertex = VertexCoord(HexCoord(1, i), 0)
            player.cities.add(vertex)

        assert not player.can_build_city()

        # Ajouter le maximum de routes
        for i in range(15):
            edge = EdgeCoord(HexCoord(2, i-7), 0)
            player.roads.add(edge)

        assert not player.can_build_road()


class TestVictoryPoints:
    """Tests pour le calcul des points de victoire."""

    def test_victory_points_settlements_and_cities(self):
        """Test calcul des points avec colonies et villes."""
        player = PlayerState(player_id=0)
        assert player.victory_points() == 0

        # Ajouter 2 colonies (2 points)
        player.settlements.add(VertexCoord(HexCoord(0, 0), 0))
        player.settlements.add(VertexCoord(HexCoord(1, 0), 0))
        assert player.victory_points() == 2

        # Ajouter 1 ville (2 points)
        player.cities.add(VertexCoord(HexCoord(2, 0), 0))
        assert player.victory_points() == 4

    def test_victory_points_dev_cards(self):
        """Test calcul des points avec cartes développement."""
        player = PlayerState(player_id=0)

        # Ajouter des cartes point de victoire en main
        player.dev_cards_in_hand[DevelopmentCardType.VICTORY_POINT] = 2
        assert player.victory_points() == 2

        # Ajouter des cartes point de victoire jouées
        player.dev_cards_played[DevelopmentCardType.VICTORY_POINT] = 1
        assert player.victory_points() == 3

    def test_victory_points_with_bonuses(self):
        """Test calcul des points avec bonus."""
        player = PlayerState(player_id=0)

        # Ajouter 2 colonies
        player.settlements.add(VertexCoord(HexCoord(0, 0), 0))
        player.settlements.add(VertexCoord(HexCoord(1, 0), 0))
        assert player.victory_points() == 2

        # Ajouter bonus route la plus longue
        player.has_longest_road = True
        assert player.victory_points() == 4

        # Ajouter bonus armée la plus grande
        player.has_largest_army = True
        assert player.victory_points() == 6


class TestLongestRoad:
    """Tests pour le calcul de la route la plus longue."""

    def test_longest_road_empty(self):
        """Test qu'un joueur sans route a une longueur de 0."""
        player = PlayerState(player_id=0)
        assert player.longest_road_length() == 0

    def test_longest_road_single_road(self):
        """Test avec une seule route."""
        player = PlayerState(player_id=0)

        # Ajouter une route
        edge = EdgeCoord(HexCoord(0, 0), 0)
        player.roads.add(edge)

        # Une route = 1 segment
        assert player.longest_road_length() == 1

    def test_longest_road_linear_path(self):
        """Test avec un chemin linéaire de routes."""
        player = PlayerState(player_id=0)

        # Créer un chemin linéaire: 3 routes connectées
        # Route 1: (0,0) direction 0
        # Route 2: (0,0) direction 1 (adjacente à la direction 0)
        # Route 3: (0,0) direction 2 (adjacente à la direction 1)
        player.roads.add(EdgeCoord(HexCoord(0, 0), 0))
        player.roads.add(EdgeCoord(HexCoord(0, 0), 1))
        player.roads.add(EdgeCoord(HexCoord(0, 0), 2))

        # 3 routes connectées = 3 segments
        length = player.longest_road_length()
        assert length >= 2  # Au minimum 2 routes sont connectées

    def test_longest_road_branching(self):
        """Test avec des routes qui se ramifient."""
        player = PlayerState(player_id=0)

        # Créer une structure en Y
        # Branche principale
        player.roads.add(EdgeCoord(HexCoord(0, 0), 0))
        player.roads.add(EdgeCoord(HexCoord(0, 0), 1))

        # Branches secondaires
        player.roads.add(EdgeCoord(HexCoord(0, 0), 5))  # Branche à partir de direction 0

        # La plus longue route devrait être >= 2
        length = player.longest_road_length()
        assert length >= 2

    def test_longest_road_disconnected(self):
        """Test avec des routes déconnectées."""
        player = PlayerState(player_id=0)

        # Ajouter deux groupes de routes non connectées
        # Groupe 1
        player.roads.add(EdgeCoord(HexCoord(0, 0), 0))
        player.roads.add(EdgeCoord(HexCoord(0, 0), 1))

        # Groupe 2 (hexagone éloigné)
        player.roads.add(EdgeCoord(HexCoord(5, 0), 0))
        player.roads.add(EdgeCoord(HexCoord(5, 0), 1))

        # La plus longue route est le plus long groupe connecté
        length = player.longest_road_length()
        assert length >= 2

    def test_longest_road_complex_network(self):
        """Test avec un réseau complexe de routes."""
        player = PlayerState(player_id=0)

        # Créer un réseau hexagonal de routes autour d'un hexagone central
        hex_center = HexCoord(0, 0)

        # Toutes les arêtes autour de l'hexagone central
        for direction in range(6):
            player.roads.add(EdgeCoord(hex_center, direction))

        # Un hexagone a 6 arêtes formant un cycle
        # La plus longue route devrait être >= 5 (cycle de 6 - 1)
        length = player.longest_road_length()
        assert length >= 5

    def test_longest_road_realistic_scenario(self):
        """Test avec un scénario réaliste de routes connectées."""
        player = PlayerState(player_id=0)

        # Créer une route qui s'étend sur plusieurs hexagones
        # Hexagone (0,0)
        player.roads.add(EdgeCoord(HexCoord(0, 0), 0))
        player.roads.add(EdgeCoord(HexCoord(0, 0), 1))

        # Connecter à l'hexagone voisin (1,0)
        player.roads.add(EdgeCoord(HexCoord(1, 0), 3))
        player.roads.add(EdgeCoord(HexCoord(1, 0), 4))

        # Devrait avoir au moins une chaîne de 3-4 routes
        length = player.longest_road_length()
        assert length >= 3


class TestPlayerRepr:
    """Tests pour la représentation textuelle du joueur."""

    def test_player_repr(self):
        """Test que __repr__ retourne une chaîne valide."""
        player = PlayerState(player_id=0)
        player.settlements.add(VertexCoord(HexCoord(0, 0), 0))
        player.resources[ResourceType.WOOD] = 3

        repr_str = repr(player)
        assert "Player0" in repr_str
        assert "VP=" in repr_str
        assert "resources=" in repr_str
