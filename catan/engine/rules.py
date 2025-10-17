"""Règles et constantes de la variante 1v1.

Ce module expose le contrat minimal attendu par les tests:
- constantes de variante (`VP_TO_WIN`, `DISCARD_THRESHOLD`)
- coûts de construction `COSTS`
"""

# Variante 1v1
VP_TO_WIN: int = 15
DISCARD_THRESHOLD: int = 9

# Coûts de construction (contrat: mapping str -> dict[str, int])
COSTS = {
    "road": {"BRICK": 1, "LUMBER": 1},
    "settlement": {"BRICK": 1, "LUMBER": 1, "WOOL": 1, "GRAIN": 1},
    "city": {"GRAIN": 2, "ORE": 3},
    "development": {"WOOL": 1, "GRAIN": 1, "ORE": 1},
}

__all__ = [
    "VP_TO_WIN",
    "DISCARD_THRESHOLD",
    "COSTS",
]

