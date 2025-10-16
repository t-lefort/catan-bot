"""Constants and enums for the Catan game."""

from enum import IntEnum, auto


class ResourceType(IntEnum):
    """Types de ressources dans Catan."""
    WOOD = 0      # Bois
    BRICK = 1     # Argile
    SHEEP = 2     # Mouton
    WHEAT = 3     # Blé
    ORE = 4       # Minerai


class TerrainType(IntEnum):
    """Types de terrain."""
    FOREST = 0    # Forêt (Bois)
    HILLS = 1     # Collines (Argile)
    PASTURE = 2   # Pâturage (Mouton)
    FIELDS = 3    # Champs (Blé)
    MOUNTAINS = 4 # Montagnes (Minerai)
    DESERT = 5    # Désert (pas de ressource)


class DevelopmentCardType(IntEnum):
    """Types de cartes développement."""
    KNIGHT = 0        # Chevalier
    VICTORY_POINT = 1 # Point de victoire
    ROAD_BUILDING = 2 # Construction de routes
    YEAR_OF_PLENTY = 3 # Invention
    MONOPOLY = 4      # Monopole


class BuildingType(IntEnum):
    """Types de constructions."""
    SETTLEMENT = 0  # Colonie
    CITY = 1        # Ville
    ROAD = 2        # Route


# Coûts de construction (en ressources)
BUILDING_COSTS = {
    BuildingType.SETTLEMENT: {
        ResourceType.WOOD: 1,
        ResourceType.BRICK: 1,
        ResourceType.SHEEP: 1,
        ResourceType.WHEAT: 1,
    },
    BuildingType.CITY: {
        ResourceType.WHEAT: 2,
        ResourceType.ORE: 3,
    },
    BuildingType.ROAD: {
        ResourceType.WOOD: 1,
        ResourceType.BRICK: 1,
    },
}

# Coût carte développement
DEV_CARD_COST = {
    ResourceType.SHEEP: 1,
    ResourceType.WHEAT: 1,
    ResourceType.ORE: 1,
}

# Règles du jeu
NUM_RESOURCES = 5
NUM_DEV_CARD_TYPES = 5
MAX_HAND_SIZE_BEFORE_DISCARD = 7  # Si dé = 7, défausser si > 7 cartes

# Distribution des cartes développement (jeu de base)
DEV_CARD_DISTRIBUTION = {
    DevelopmentCardType.KNIGHT: 14,
    DevelopmentCardType.VICTORY_POINT: 5,
    DevelopmentCardType.ROAD_BUILDING: 2,
    DevelopmentCardType.YEAR_OF_PLENTY: 2,
    DevelopmentCardType.MONOPOLY: 2,
}

# Points de victoire
VICTORY_POINTS = {
    BuildingType.SETTLEMENT: 1,
    BuildingType.CITY: 2,
    DevelopmentCardType.VICTORY_POINT: 1,
}

LONGEST_ROAD_VP = 2  # Bonus route la plus longue
LARGEST_ARMY_VP = 2  # Bonus armée la plus grande
MIN_ROAD_LENGTH_FOR_BONUS = 5
MIN_ARMY_SIZE_FOR_BONUS = 3

# Configuration du plateau standard
STANDARD_BOARD_HEXES = 19  # 19 hexagones sur le plateau standard
STANDARD_BOARD_NUMBERS = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]

# Limites de construction
MAX_SETTLEMENTS_PER_PLAYER = 5
MAX_CITIES_PER_PLAYER = 4
MAX_ROADS_PER_PLAYER = 15

# Règles de commerce
BANK_TRADE_RATIO = 4  # 4:1 par défaut
PORT_GENERIC_RATIO = 3  # 3:1 port générique
PORT_SPECIFIC_RATIO = 2  # 2:1 port spécialisé
