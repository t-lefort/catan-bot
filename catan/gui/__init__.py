"""GUI package — interface graphique H2H avec pygame (GUI-002+).

Ce package implémente l'interface utilisateur pour jouer à Catane 1v1
entre deux humains, conformément à docs/gui-h2h.md.

Modules:
- renderer: rendu du plateau, pièces et HUD
- components: widgets réutilisables (boutons, overlays)
- app: boucle principale pygame et gestion des évènements
"""

__all__ = ["renderer", "components", "app"]
