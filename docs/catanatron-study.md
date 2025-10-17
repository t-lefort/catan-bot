# Catanatron — étude de réutilisation

## Source analysée
- Dépôt : https://github.com/bcollazo/catanatron
- Révision : c986945ca5a9364529d54cb3876ab954dc5c45ea (consultée localement dans `external/catanatron`)
- Portée de l’étude : modules moteur (plateau, état, génération d’actions), données de cartes et tooling existant.

## Architecture synthétique
- **Boucle de jeu** : `catanatron.game.Game` encapsule l’état (`State`), orchestre le tour par tour et expose des accumulateurs de statistiques.
- **État de partie** : `catanatron.state.State` + `state_functions` gèrent toute la logique métier (build, échanges, dev cards) via un gros objet mutable, des fonctions utilitaires et de nombreux caches.
- **Génération des coups** : `models.actions.generate_playable_actions` produit les actions légales en se basant sur les decks et l’état courant.
- **Plateau et coordonnées** : `models.map`, `models.board` et `models.coordinate_system` décrivent le plateau standard (54 sommets, 72 arêtes), s’appuient sur NetworkX pour le calcul de routes et de distances, et encapsulent la topologie hexagonale cube.
- **Banques & decks** : `models.decks` gère les ressources/dev cards via des « freqdecks » (listes d’occurrences) et fournit les coûts standards.
- **Joueurs & IA** : `players/` (bots heuristiques), `gym/` (enveloppe Gym) et `utils.py` (features) ciblent le self-play RL.
- **Tests** : dossiers `tests/` (unitaires et d’intégration) couvrent règles de base, longue route, commerce, etc., mais sont liés étroitement à l’implémentation actuelle.

## Licence et implications
- Licence GPL-3.0-only : toute redistribution de code dérivé impose de placer **CatanBot** sous GPL-3.0 ou licence compatible. L’intégration directe de modules copier-coller n’est donc pas compatible avec un futur packaging plus permissif (MIT/BSD) sans changement de licence.
- Deux approches possibles :
  1. **Réutilisation par dépendance optionnelle** : garder `catanatron` comme dépendance de développement pour du cross-check (simulation oracle, génération de fixtures) sans en redistribuer le code. Nécessite d’isoler les interfaces et de charger dynamiquement.
  2. **Réimplémentation inspirée** : s’appuyer sur l’étude fonctionnelle pour écrire une implémentation propre (typage fort, performances RL), en évitant tout copier-coller. Permet de choisir une licence plus permissive.
- Décision retenue : partir sur une **réimplémentation inspirée** afin de maîtriser les invariants 1v1 (15 VP, défausse à 9), optimiser pour le self-play massif et garder la liberté de licence.

## Mapping de réutilisation

| Domaine | Modules Catanatron | Décision | Motivation principale |
| --- | --- | --- | --- |
| Plateau & coordonnées | `models.map`, `models.board`, `models.coordinate_system` | Adapter (réimplémenté) | Topologie cube pertinente, mais le code dépend de NetworkX et mélange état & structure. Nous reproduirons le schéma (IDs, ports) avec des structures légères immuables et un graphe spécialisé pour les routes. |
| Algorithme « longest road » | `models.board.longest_acyclic_path` & caches | Réimplémenter | L’algorithme existant fonctionne mais est imbriqué dans Board et dépend de caches mutables. Nous voulons une version testable isolée et optimisée (poss. DFS custom ou memo). |
| Génération d’actions | `models.actions` | Réécriture complète | Couplage fort aux freqdecks et prompts historiques (multijoueur). Pour la variante 1v1, nous définirons un système d’actions typé (enums + payload) avec contraintes explicites et seuils 15 VP / défausse 9. |
| Règles & banques | `models.decks`, `models.enums`, coûts constants | Adapter (réimplémenté) | Les coûts et banques standard sont communs. Nous repartons de la spec officielle pour recréer les constantes et decks, en gardant l’idée de freqdecks mais avec types dédiés et tests propriété. |
| État de partie | `state.py`, `state_functions.py` | Réécriture complète | Implémentation monolithique, difficile à typer et à sérialiser rapidement. Nous viserons une séparation claire (State immuable ou semi-immuable, reducers, validations) et une sérialisation compacte pour le self-play. |
| Boucle de jeu / Game | `game.py` | Réimplémenter | Nécessaire pour intégrer nos prompts/tests et les hooks RL. Nous conserverons l’idée d’accumulateurs mais avec API explicite async-friendly. |
| Joueurs, UI, Gym | `players/`, `ui/`, `gym/` | Non retenu (référence) | Non aligné sur les besoins immédiats (1v1 GUI spécifique, pipeline RL maison). Peut servir d’inspiration pour les heuristiques baselines. |
| Tests | `tests/` | Référence conceptuelle | Les scénarios sont utiles pour inspirer nos propres tests, mais ils sont trop liés à l’implémentation GPL actuelle. Nous rédigerons nos cas de test (property-based, scénarios 1v1) en nous basant sur les specs. |
| Données / fixtures | `maps/*.json`, `documentation/` | Référence | À utiliser pour valider notre topologie. Aucune donnée ne sera copiée telle quelle ; nous regénérerons nos tables à partir des règles publiques. |

## Modalités d’intégration proposées
- Garder `external/catanatron` cloné (ou ajouté en sous-module ignoré) uniquement à des fins d’étude comparative. Ne pas l’inclure dans les artefacts distribués.
- Prévoir un script de cross-validation (plus tard) qui charge notre moteur et, si `catanatron` est installé, rejoue des scénarios pour détecter des divergences — sans embarquer de code GPL.
- Documenter dans `docs/architecture.md` comment notre State/Board mappe sur les concepts traits dans catanatron afin de faciliter l’écriture de tests différentiés.

## Prochaines étapes liées
1. DOC-005 : formaliser l’architecture (modules `catan.engine.*`, simulation, GUI, RL) en intégrant les décisions ci-dessus.
2. DOC-006 : définir les schémas sérialisables (state/action) compatibles avec nos objectifs RL.
3. TEST-001 : étendre les tests de contrat (board/rules) vers les nouvelles structures décidées (ex. représentation des noeuds/aretes, seuil de défausse à 9).

