# CatanBot — Variante 1v1 (15 VP, défausse >9)

Objectif
- Construire un moteur complet de Catane 1v1 avec une interface H2H, une simulation headless performante et un socle RL pour self‑play.
- Varier légèrement les règles: victoire à 15 points, défausse lorsqu’une main dépasse 9 cartes (ramener à 9 au déclenchement du voleur).

Périmètre
- Plateau standard (19 hexagones) avec ports, numéros de dés et voleur.
- Deux joueurs humains (H2H) pour la GUI; bots/agents via la simulation headless.
- Moteur déterministe avec RNG seedable; sérialisation d’état et d’actions.

Règles inchangées (exemples non exhaustifs)
- Coûts de construction: route (Argile+Bois), colonie (Argile+Bois+Laine+Blé), ville (2×Blé+3×Minerai), dev (Laine+Blé+Minerai).
- Placement: distance d’une colonie, connexité des routes.
- Distribution de ressources par lancer (2–12), 7 déclenche le voleur.
- Ports: 4:1 banque, 3:1 générique, 2:1 spécifique ressource.
- Cartes de développement: délais d’usage, effets (chevalier, progrès, PV).
- Plus longue route / plus grande armée: tuiles titres et recalcul dynamique.

Variantes (1v1) et clarifications
- Victoire à 15 VP (au lieu de 10).
- Sur un 7, défausse si main > 9: on réduit à 9 cartes avant déplacement du voleur et vol.
- Commerce joueur‑joueur possible mais limité à 1v1 (UX simplifiée côté GUI).

Livrables DOC
- Cette vue d’ensemble (ce fichier).
- Une checklist des règles et invariants: docs/specs.md.
- Esquisse d’architecture (engine, sim, GUI, RL) et schémas de données (à itérer).

Références
- catanatron (bcollazo/catanatron) pour inspirations de représentation d’état, actions et longest road.

