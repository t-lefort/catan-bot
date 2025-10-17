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
J'ai du itérer plusieurs fois pour qu'il y ait moins de tests qui fail. Au bout d'un moment j'ai arreté d'essayer de comprendre tout ce qu'il faisait.
Et je passe sur gpt-5-high pour regler le dernier bug qui persiste après plusieurs itérations avec Claude Code. 
ChatGPT semble avoir trouvé le problème tout de suite, je n'ai pas l'impression qu'il a contourné le test, il a juste corrigé une formule mathématique qui devait être une erreur de résonnement de Claude.

## Etape 4
Je lui demande de pouvoir jouer dans la GUI à une partie complète. Il y a pas mal de choses qui fonctionne très bien mais des bugs bizarre aussi alors que les 124 tests passent. Par exemple il n'y a que 2 des 3 arretes qui fonctionne pour créer une route, ça ne donne pas toutes les ressources de la deuxième colonie et ne donne pas les ressources lors des lancées de dés.
Il a l'air de comprendre qu'il y a plusieurs définition d'un même vertex et donc se met à utiliser la fonction qu'il avait créé plus tôt is_same_vertex(). Quand il l'a créé la première fois il n'a pas corrigé le problème partout.

## Etape 5
Finalement je lui fait remarquer que j'ai l'impression qu'il a mis une grosse partie de la logique de jeu dans la GUI plutôt que dans le GameState et donc que ça risque de ne pas correctement fonctionner quand je vais vouloir faire du RL sans GUI. Il reconnait l'erreur et me propose un refactoring complet.

## Etape 6
Je commence à tester et lui faire part de petits bugs à droite à gauche. C'est fou que les 124 tests passent mais qu'il y ait autant de bugs non detectées. J'ai l'impression qu'il n'est pas très bon pour rédiger des tests pertinents en tout cas pas pour un jeu avec des aspects logiques un peu complexe comme Catan.

## Etape 7
J'essaye de passer sur ChatGPT pour corriger les bugs car il y en a qu'en même beaucoup avec Claude Code.
Claude code galère a positionner correctement les ports dans la GUI

## Etape 8
Le système de coordonée hexagonale ne fonctionnait pas bien.
Je lui ai donné l'example d'un autre projet de bot catan en lui demandant d'analyser la solution qu'ils utilisaient. Il reconnais qu'il y a plein de problème (je ne sais plus si c'est vrai il est toujours d'accord de toute façon). Il me propose de tout refactoriser ce que j'accepte. Le refactor est tellement gros qu'il crée un fichier .md pour suivre l'avancement.
Je recommence une session une fois qu'il a fait ce fichier pour eviter d'exploser la fenetre de contexte.

## Etape 9
Bon j'ai testé pleins de trucs depuis la dernière fois mais rien ne marche. Comme la dernière fois, gros progrès au début mais grosse lacune dans le code et du coup rien ne marche correctement, je vais me renseigner sur une façon d'améliorer le workflow de developpement et je repars à 0 sur le projet.

## Etape 10
J'essaye une nouvelles approche. D'abord je lui demande de préparer un projet avec les best practices sans lui dire exactement ce qu'est le projet : "Tu vas m'aider à développer un projet en python avec une interface graphique et du RL. Prépare un projet générique avec les consignes pour que tu travailles en suivants clairement un plan et en testant toi-même au fur et à mesure si ce que tu fais fonctionne bien. Ensuite je t'expliquerai en détail quel est le projet", puis "ttends tu pars déjà trop loin. Je voulais juste que t'initialise un README, un AGENTS.md et un dossier dans lequel mettre la documentation du projet. Dans le AGENTS.md tu décrives de bien regarder la documentation avant de commencer à travailler, d'écrire des tests avant de code, de suivre le plan à la lettre etc. Les bonnes practices en général pour travailler avec un agent IA de code. Ne commence pas à faire du python déjà."

## Etape 11
"Parfait, maintenant je vais t'expliquer mon projet pour que tu planifies le développement complet, n'écris pas encore de code pour que je valide le plan. Je souhaite développer un bot pour le jeu Colon de Catan. Il faut d'abord créer toutes les classes qui permettent de gérer toutes les règles du jeu. Tu peux t'inspirer du projet https://github.com/bcollazo/catanatron. Ensuite une interface graphique avec toutes les fonctionnalités pour jouer une partie complète (pour le moment les deux joueurs sont joués par l'humain, plus tard un des deux joueurs sera joué par le bot pour tester sa performance). Ensuite je veux essayer de mettre en place un apprentissage par renforcement pour rendre le bot plus fort que n'importe quel humain. Je veux pouvoir lancer pleins de simulation où le bot joue contre lui-même pour s'améliorer, il faut que les simulations soient très rapide. J'aimerai aussi qu'il y ait un affichage live au cours de l'entrainement pour constater si le bot progresse ou pas. Pour le moment je veux juste que ça fonctionne en 1V1, c'est à dire en 15 points gagnant et défausse si plus de 9 cartes, le reste des règles ne change pas. Fais le plan"

Il a généré un plan super détaillé, facile à relire et que me semble très cohérent. Il y a juste les tests qui sont à la fin donc j'espère qu'il ne va pas le réaliser de haut en bas, il semble avoir mis un système de priorité, à voir si c'est bien géré.

## Etape 12
Je vais lui demander de commencer à faire la doc et faire les tests avant de créer le moteur de jeu. Je lui donne le PLAN.yaml, le AGENTS.md et les README en context plutôt que d'utiliser le contexte automatique. Je reset régulièrement le context et lui dis "Continue le projet selon le plan". J'essaye de passer sur gpt-5-codex-high pour l'execution du plan

## Etape 13
La méthode a l'air de bien fonctionner avec ChatGPT, je vais faire une passe avec Claude Code pour voir comment il s'en sort. Si ça marche bien, ça serait bien de pouvoir les faire bosser en parallèle, il y a des outils pour ça, il faudrait que je test. Claude est plus rapide mais il ne me donne pas l'impression de bien faire les chose dans l'ordre. Il crée bien les tests avant de dev la fonctionnalité mais je ne pense pas que c'est ce qu'aurait fait ChatGPT. 

## Etape 14
Il faudrait aussi définir un template pour les commits comme Claude fait. Chatgpt fais des commits tout pourris sans détail. Et il faudra que je passe ce journal dans une IA pour en tirer les idées et faire un boilerplate pour projets IA
J'ai aussi arreté d'utiliser le mode "Plan" de Claude que j'avais testé et qui marche bien.