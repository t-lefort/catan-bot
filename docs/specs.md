# Spécifications et invariants — CatanBot 1v1

## Checklist des règles (fonctionnelles)
- Plateau standard: 19 hex, désert unique, numéros 2–12 distribués, ports 4:1/3:1/2:1.
- Setup initial: ordre serpent, 2 placements (colonie+route), ressources distribuées après le 2e placement.
- Tour de jeu: lancer de dés, distribution, actions (construire, acheter/jouer dev, commercer), fin de tour.
- Voleur: sur 7 (ou chevalier), défausse puis déplacement du voleur, vol d’1 carte à un voisin valide.
- Construction: règles d’adjacence, distance d’une colonie, connexité des routes.
- Coûts: route (Argile+Bois), colonie (Argile+Bois+Laine+Blé), ville (2×Blé+3×Minerai), dev (Laine+Blé+Minerai).
- Commerce: banque (4:1), ports (3:1 générique, 2:1 spécifique), commerce J↔J (1v1) avec acceptation explicite.
- Cartes de développement: pioche aléatoire, délai d’usage (pas le tour d’achat), effets normés.
- Titres: Plus longue route / Plus grande armée, attribution et retrait dynamiques.
- Victoire: 15 points de victoire.

## Variantes (1v1) à implémenter
- Seuil de défausse: si main > 9 lors d’un 7, réduire la main à 9 cartes (au lieu du 7 standard « >7 → défausser moitié »).
- Périmètre 1v1: UI/UX simplifiée pour les échanges joueur‑joueur.

## Invariants (techniques et règles)
- Comptages plateau: 19 tuiles, 54 intersections (sommets), ~72 arêtes (référence Catane standard).
- Un seul désert, aucun numéro sur le désert, voleur démarre sur le désert.
- Contrats de coûts immuables durant une partie; inventaire banque fini (quantités standard de cartes dev/ressources).
- Actions légales toujours validées par le moteur; impossibilité de produire un état invalide via l’API publique.
- RNG seedable et sérialisable; tout état doit être sérialisable/cloneable.
- Pas d’auto‑échange implicite: tout transfert passe par une action explicite validée.

## Décisions d’API (proposition minimale à valider)
- `catan.engine.Board` — représentation du plateau, accès aux tuiles/ports/indexations.
- `catan.engine.State` — état de partie (joueurs, mains, titres, position du voleur, plateau, pioche dev, RNG).
- `catan.engine.Action` — type + paramètres (ex: BuildRoad(edge_id), RollDice(), MoveRobber(tile_id)…).
- `catan.engine.rules` — constantes de règles (coûts, seuils, VP cible) et validateurs.
- `catan.engine.serialize` — (dé)sérialisation d’état et d’actions, seed.

## Cas de test prioritaires (tests‑first)
- Règles de variante: `VP_TO_WIN == 15`, `DISCARD_THRESHOLD == 9`.
- Coûts immuables et complets pour {route, colonie, ville, dev}.
- Setup: 2 placements par joueur en ordre serpent; distrib après 2e placement.
- Voleur/défausse: si main > 9, défausser jusqu’à 9; vol d’un voisin uniquement.
- Longest road: calcul cohérent avec une référence (ex: catanatron) sur des cas canoniques.
- Sérialisation: état complet clonable et reproductible (RNG).

## Liens
- Vue d’ensemble: `docs/overview.md`
- Architecture (à rédiger): `docs/architecture.md`
- Schémas de données (à rédiger): `docs/schemas.md`

