"""GUI package — interface graphique H2H avec pygame (GUI-002+).

Ce package implémente l'interface utilisateur pour jouer à Catane 1v1
entre deux humains, conformément à docs/gui-h2h.md.

Modules:
- renderer: rendu du plateau, pièces et HUD
- geometry: calculs de transformation logique -> écran
- setup_controller: contrôleur pour la phase de placement initial (GUI-003)
- components: widgets réutilisables (boutons, overlays) [à venir]
- app: boucle principale pygame et gestion des évènements [à venir]
"""

__all__ = ["renderer", "geometry", "setup_controller"]
