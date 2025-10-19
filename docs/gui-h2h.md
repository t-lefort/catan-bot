# GUI H2H - Flux et interactions (1v1)

## Objectifs et principes
- Permettre à deux joueurs humains de disputer une partie complète de Catane 1v1 (victoire à 15 VP, défausse lorsqu'une main dépasse 9 cartes sur un 7 ou un chevalier).
- Rester fidèle aux règles décrites dans `docs/specs.md` tout en offrant une ergonomie simple (peu d'écrans, confirmations explicites).
- Conserver une séparation stricte entre présentation et logique : toute action utilisateur se traduit par une commande envoyée au `GameService` qui délègue au moteur (`catan.engine`).
- Favoriser la lisibilité en situation 1v1 : informations essentielles visibles en permanence (mains, titres, historique), overlays temporaires pour les étapes bloquantes (défausse, vol).

## Structure d'écran proposée
- **Zone plateau** (centre) : hexagones, numéros, ports, routes/colonies/villes avec surbrillance des positions jouables.
- **Panneau actions** (droite) : boutons contextuels (lancer les dés, construire, commercer, jouer carte dev, terminer le tour).
- **Inventaires joueurs** (bas) : ressources, cartes développement (séparées en main jouable vs nouveautés), titres (longest road / largest army), VP visibles + cachés.
- **Journal** (gauche) : liste chronologique des actions (`RollDice`, `BuildRoad`, etc.) avec filtrage minimal (tour courant, tours précédents).
- **Overlays modaux** pour les moments critiques : défausse (>9 cartes), choix de tuile pour le voleur, offres de commerce, sélection de cartes progrès.

## Flux d'une partie

### 0. Écran d'accueil / Lobby
1. Choix des noms/couleurs joueurs (par défaut `Bleu` / `Orange`), seed optionnelle, chargement partie sauvegardée.
2. Bouton `Démarrer une nouvelle partie` -> création `GameService` + `State` initial (`Board.standard()` avec voleur sur le désert).

### 1. Phase de placement serpent (setup)
1. Joueur 0 sélectionne un sommet libre (`SETUP_PLACE_SETTLEMENT`), surbrillance des sommets valides.
2. Sélection d'une arête adjacente (`SETUP_PLACE_ROAD`). Validation côté moteur : distance colonie respectée, connexité.
3. Joueur 1 répète étapes 1-2.
4. Joueur 1 place sa seconde colonie + route (ordre serpent inversé).
5. Joueur 0 place sa seconde colonie + route.
6. Après chaque seconde colonie, le moteur attribue les ressources correspondantes; la GUI affiche bannière "Distribution initiale" et incrémente les mains.
7. Passage automatique en phase `Main` une fois le setup terminé.

### 2. Tour standard (sans évènements spéciaux)
1. **Pré-tour** : panneau actions montre uniquement `Lancer les dés` pour le joueur actif.
2. **Lancer de dés** (`ROLL_DICE`) -> mise à jour du journal et des ressources distribuées.
3. **Actions disponibles** : boutons activés selon masques légaux (construction, achat dev, commerce, jouer carte dev autorisée).
4. **Construction** : sélection sur le plateau avec confirmation (coût affiché). Routes, colonies, villes utilisent respectivement `BUILD_ROAD`, `BUILD_SETTLEMENT`, `BUILD_CITY`.
5. **Achat de carte dev** (`BUY_DEVELOPMENT`) : animation pioche, carte placée dans "Nouvelles cartes" (non jouable ce tour).
6. **Jouer une carte dev** (sauf nouveautés) via modal dédié. Gestion spécifique pour `ROAD_BUILDING`, `YEAR_OF_PLENTY`, `MONOPOLY`, `PLAY_KNIGHT`.
7. **Commerce** : boutons dédiés `Banque`, `Port`, `Joueur` (voir section 4).
8. **Fin de tour** (`END_TURN`) disponible uniquement si aucune action obligatoire restante (ex. voleur, défausse).

### 3. Gestion du voleur et défausse (>9)
1. Si un 7 est lancé ou un `PLAY_KNIGHT` est exécuté, overlay "Défausse" apparaît pour chaque joueur dont la main dépasse 9 cartes.
2. Défausse interactive : compteur cible (ramener à 9), validation envoyant `DiscardToThreshold` (action interne future) ou ensemble de transferts vers la banque.
3. Après résolution de la défausse, overlay de sélection de tuile (`MOVE_ROBBER`) avec surbrillance des voisins éligibles.
4. Si un joueur adverse est adjacent, sélection dans une liste pour voler une ressource (action `MOVE_ROBBER` avec `steal_from`).
5. Journal mentionne "Bleu vole une carte à Orange" sans révéler la ressource.

### 4. Commerce
1. **Banque 4:1** : modal avec sélecteurs de ressources à donner/recevoir, validation via `TRADE_BANK`.
2. **Port** : accessible si joueur possède un port. UI propose options 3:1 ou 2:1 selon port sélectionné (`TRADE_PORT`).
3. **Commerce joueur <-> joueur** : unique modal, joueur actif construit une offre (donne/reçoit). Envoi d'une requête `TRADE_PLAYER` -> adversaire voit overlay pour accepter/refuser. En 1v1, réponse binaire.
4. Confirmation visuelle sur le plateau (bannière, journal).

### 5. Construction et cartes développement
1. Choisir pièce sur plateau -> preview position + coût. Confirmation déclenche l'action correspondante (réutilise validations du moteur).
2. `ROAD_BUILDING` : overlay demandant deux arêtes successives, validation même si routes gratuites (flag `free=true`).
3. `YEAR_OF_PLENTY` : sélection de deux ressources disponibles en banque.
4. `MONOPOLY` : choix d'une ressource; la GUI affiche résultat dans le journal.

### 6. Fin de tour et transitions
1. Bouton `Terminer le tour` appelle `END_TURN`. La GUI verrouille les actions et passe au joueur suivant.
2. Journal affiche résumé du tour (construction, échanges, cartes jouées).
3. EventBus informe la GUI -> rafraîchissement complet des panneaux.

### 7. Victoire (15 VP)
1. Lorsque le moteur signale qu'un joueur atteint 15 VP (visibles + cachés révélés), bannière de victoire + modal final avec statistiques (points, cartes restantes, longueur route, armée).
2. Options : `Rejouer` (nouveau `GameService`), `Sauvegarder la partie`, `Quitter`.

## Mapping actions GUI <-> moteur

| Interaction GUI | Action moteur | Validation côté moteur | Notes UX |
|-----------------|--------------|-------------------------|----------|
| Lancer les dés | `ROLL_DICE` | Phase `Main`, pas de lancer précédent ce tour | Bouton dés activé uniquement en début de tour |
| Déplacer le voleur | `MOVE_ROBBER` | Tuile différente, joueur cible adjacent | Overlay obligatoire, highlight tuiles valides |
| Placer route (setup) | `SETUP_PLACE_ROAD` | Connexité au dernier settlement, arête libre | Double confirmation pour éviter missclick |
| Placer colonie (setup) | `SETUP_PLACE_SETTLEMENT` | Distance colonie, vertex libre | UI verrouille les vertex invalides |
| Construire route | `BUILD_ROAD` | Ressources suffisantes ou `free`, arête adjacente réseau | Affiche coût et ressources restantes |
| Construire colonie | `BUILD_SETTLEMENT` | Ressources suffisantes, distance colonie | Prévisualisation position |
| Construire ville | `BUILD_CITY` | Ressources suffisantes, colonie propre existante | Icône colonie -> ville animée |
| Acheter carte dev | `BUY_DEVELOPMENT` | Ressources suffisantes, pioche non vide | Carte ajoutée dans "nouvelles cartes" |
| Jouer chevalier | `PLAY_KNIGHT` | Carte disponible, délai respecté | Chaîne d'overlays identique au voleur |
| Jouer progrès | `PLAY_PROGRESS` | Détail selon carte | UI spécifiques pour routes / ressources / monopole |
| Commerce banque | `TRADE_BANK` | Multiples 4:1, ressources en main, dispo banque | UI refuse validation si solde insuffisant |
| Commerce port | `TRADE_PORT` | Possession port, ratio correct, banque fournie | Port choisi via clic sur plateau ou liste |
| Commerce joueur | `TRADE_PLAYER` | Offre valide, acceptation adverse | Flux 2 étapes, logs côté journal |
| Terminer tour | `END_TURN` | Pas d'action forcée en attente | Bouton désactivé tant que obligations |

## États transverses et feedback
- **Surbrillance contextuelle** : le plateau affiche en temps réel les positions légales selon l'action en cours (données fournies par le moteur/validateur).
- **Historique** : chaque action loggée avec `action_id`, horodatage local, possibilité de cliquer pour afficher les détails (ex. ressources échangées).
- **Défausse** : compteur dynamique indiquant cartes restantes à défausser pour atteindre 9.

## Prochaines étapes GUI
- Valider le toolkit (DOC-003 -> GUI-001).
- Produire des wireframes haute-fidélité pour les principales phases.
- Définir les tests UI smoke (voir tâche TEST-005).
