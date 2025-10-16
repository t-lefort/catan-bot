# Journal de bord

## Etape 1
Il crée le projet tout seul, avec la structure de base du projet. Il met des TODO de partout dans le code pour simplifier la création de l'architecture complète. Après seulement une itération, j'ai un plateau qui se génère automatiquement selon les bonnes règles du jeu et une interface qui m'affiche l'état du plateau.
Les constantes et structures de classes créé correspondent bien à l'ensemble des règles du jeu.

## Etape 2
Je lui demande de continer à développer les fonctionnalités qu'il à mis dans sa TODO dans CLAUDE.md.
Il en fait enormément d'un coup. Je me demande s'il faut que je relise tout ou si je lui fait confiance et que je teste juste le résultat final pour voir s'il n'y a pas de bug.
Je pense que lui demander de m'expliquer en détail ce qu'il a fait pourrait peut-être l'aider lui même à se debugguer.
Quand je run pytest j'ai directement un bug que je lui donne à corriger. Ca semble être un problème de typage lié à l'utilisation de Python 3.9 au lieu de Python 3.10+
Je suis passé sur Python 3.12 du coup

En lisant le code je me rend compte que la règle de ne pouvoir utiliser qu'une seule carte développement par tour n'a pas été intégré, quand je lui explique, il le comprend rapidement et corrige le problème.

Je lui fait commit les changements

## Etape 3
En lui demandant si les test sont bien exhaustifs, il se rend compte de lui même que de nombreuses règles ne sont pas vérifiées dans les tests.
Il en crée une centaine de nouveaux.
Quand j'execute les tests, il y en a 6 qui échouent. Je lui fais corriger et il semble bien trouver des bugs dans le code, l'analyse qu'il fait à postériori grâce aux tests semble bon, ce qui indique que les tests l'aide à créer du code de meilleur qualité.
Il reste tout de même 3 tests qui ne passent toujours pas donc je lui redonne le resultat des tests.
