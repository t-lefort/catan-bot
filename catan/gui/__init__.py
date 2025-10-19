"""GUI package — interface graphique H2H avec pygame (GUI-002+).

Ce package implémente l'interface utilisateur pour jouer à Catane 1v1
entre deux humains, conformément à docs/gui-h2h.md.

Modules:
- renderer: rendu du plateau, pièces et HUD
- geometry: calculs de transformation logique -> écran
- setup_controller: contrôleur pour la phase de placement initial (GUI-003)
- turn_controller: contrôleur du tour de jeu (GUI-004)
- construction_controller: contrôleur construction/achats (GUI-006)
- trade_controller: contrôleur commerce banque/joueurs (GUI-005)
- development_controller: contrôleur cartes de développement (GUI-007)
- hud_controller: contrôleur HUD (GUI-008)
- components: widgets réutilisables (boutons, overlays) [à venir]
- app: orchestrateur principal + boucle pygame
"""

__all__ = [
    "renderer",
    "geometry",
    "setup_controller",
    "turn_controller",
    "construction_controller",
    "trade_controller",
    "development_controller",
    "hud_controller",
    "app",
]
