# Tests — Contrats (avant moteur)

Ces tests décrivent le contrat minimal attendu côté moteur.
Tant que le moteur n’est pas implémenté, ils seront marqués `xfail` (import manquant).

- `test_rules_variant_contract.py` — vérifie la présence de constantes de règles
  (VP à 15, seuil de défausse à 9) et des coûts de construction.
- `test_board_contract.py` — fixe le contrat d’une API de plateau avec `Board.standard()`
  et des compteurs `tile_count()`, `vertex_count()`, `edge_count()`.

Exécution
- Installer `pytest` puis lancer `pytest -q` à la racine.

Objectif
- Rendre l’API du moteur explicite et testée dès le départ.
- Guider l’implémentation en TDD: faire passer ces tests avec le minimum de code.

