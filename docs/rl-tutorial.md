# Reinforcement Learning pour CatanBot : Guide pour débutants

Ce document explique les concepts de Reinforcement Learning (RL) appliqués à CatanBot, de façon accessible pour quelqu'un qui n'a jamais fait de RL.

---

## Table des matières

1. [L'idée de base : apprendre par l'expérience](#1-lidée-de-base--apprendre-par-lexpérience)
2. [Les 3 composantes clés du RL](#2-les-3-composantes-clés-du-rl)
3. [Architectures de réseaux en RL](#3-architectures-de-réseaux-en-rl)
4. [Comment définir la structure du réseau ?](#4-comment-définir-la-structure-du-réseau-)
5. [MLP vs CNN vs GNN](#5-mlp-vs-cnn-vs-gnn)
6. [Peut-on battre des humains experts ?](#6-peut-on-battre-des-humains-experts-)
7. [Nos choix pour CatanBot](#7-nos-choix-pour-catanbot)

---

## 1. L'idée de base : apprendre par l'expérience

### Analogie : enseigner les échecs à un enfant

Imagine que tu apprends à un enfant à jouer aux échecs. Tu ne lui donnes pas un livre de 500 pages de stratégies. À la place :

1. **Il joue** une partie (il fait des coups, même mauvais)
2. **Il voit le résultat** (il gagne ou perd)
3. **Il ajuste** : "Ah, sacrifier ma reine, c'était pas malin !"
4. **Il rejoue** et devient progressivement meilleur

### Le Reinforcement Learning fait exactement ça

Le **Reinforcement Learning (RL)** applique ce principe à un ordinateur. L'agent apprend en **jouant**, pas en lisant des règles écrites par des humains.

**Différence avec d'autres approches** :
- **Apprentissage supervisé** : On donne des exemples "bonne action" / "mauvaise action"
- **Reinforcement Learning** : L'agent découvre seul quelles actions sont bonnes, en jouant des milliers de parties

---

## 2. Les 3 composantes clés du RL

### 2.1 L'Observation (ce que l'agent "voit")

Quand tu joues à Catan, tu observes :
- Le plateau (hexagones, ports, position du voleur)
- Tes ressources (brique, blé, minerai, bois, laine)
- Les ressources de l'adversaire (visibles)
- Les colonies/villes/routes placées
- Les cartes de développement
- Qui détient le chemin le plus long, la plus grande armée
- Le score actuel

**Pour l'ordinateur**, toutes ces informations sont converties en chiffres ! C'est l'`ObservationTensor` (déjà implémenté dans `catan/rl/features.py`) :

```python
# Exemple simplifié
observation = {
    "board": [0, 1, 0, ...],           # Ressources des hexagones
    "hands": [[2, 3, 1, 0, 4],         # Mes ressources (ego-centré)
              [1, 0, 2, 1, 3]],        # Ressources adversaire
    "settlements": [1, 0, 0, ...],     # Positions de mes colonies
    "metadata": [0, 0, 1, 0.15, ...],  # Phase, tour, titres
    # ... etc
}
```

**Point clé : Normalisation**
Tous ces chiffres sont **normalisés** (généralement entre 0 et 1) pour faciliter l'apprentissage. Par exemple :
- Ressources : divisées par 19 (max théorique)
- Tour : divisé par 200 (normalisation temporelle)
- VP : divisés par 15 (objectif de victoire)

**Point clé : Perspective ego-centrée**
Les informations du joueur actuel sont toujours à l'index 0, l'adversaire à l'index 1. Ainsi l'agent apprend une seule stratégie, pas deux (joueur 0 vs joueur 1).

---

### 2.2 L'Action (ce que l'agent décide)

À ton tour à Catan, tu peux faire plusieurs choses :
- Lancer les dés
- Construire une route, une colonie, une ville
- Échanger avec la banque ou l'adversaire
- Jouer une carte développement (chevalier, progrès)
- Terminer ton tour

**L'ordinateur** a une liste de toutes les actions possibles (c'est l'`ActionEncoder` dans `catan/rl/actions.py`). Le catalogue contient **toutes** les actions théoriques :
- PlaceRoad(edge_id=0), PlaceRoad(edge_id=1), ..., PlaceRoad(edge_id=71)
- PlaceSettlement(vertex_id=0), ..., PlaceSettlement(vertex_id=53)
- TradeBank(give={BRICK:4}, receive={ORE:1}), ...
- Etc.

Mais à un instant donné, **la plupart de ces actions sont illégales** (ex: construire une ville si tu n'as pas 2 minerai + 3 blé).

**Masque d'actions légales**
On crée donc un **masque booléen** :
```python
legal_actions_mask = [1, 0, 1, 1, 0, 0, 1, ...]
# 1 = action légale, 0 = action interdite
```

Ainsi, l'agent ne choisira **jamais** une action interdite (voir section 2.3).

---

### 2.3 Le Réseau de neurones (le "cerveau" de l'agent)

C'est le programme PyTorch qui :

1. **Prend en entrée** : l'observation (plateau, ressources, etc.)
2. **Calcule** avec des couches de neurones
3. **Renvoie 2 sorties** :
   - **Politique** (policy) : "Quelle action choisir ?"
   - **Valeur** (value) : "Est-ce que je suis en train de gagner ?"

#### Anatomie du réseau : les 2 têtes

Imagine un réseau en forme de **Y** :

```
                [ObservationTensor]
                         |
                   [Flatten tout]
                         |
                  [Encoder commun]
               (couches fully-connected)
                  512 → 256 → 128
                         |
                +--------+--------+
                |                 |
         [Tête Politique]    [Tête Valeur]
          128 → action_size   128 → 1
                |                 |
         "Quelle action?"    "Suis-je gagnant?"
          (logits + mask)      (valeur ∈ [-1,1])
```

---

#### Tête 1 : La Politique (Policy Head)

**Objectif** : Décider quelle action jouer.

**Fonctionnement** :
1. Le réseau calcule un **score brut** (appelé "logit") pour chaque action possible
2. On **applique le masque** : les actions illégales reçoivent un score de `-∞`
3. On transforme les scores en **probabilités** via softmax :
   ```python
   logits = [2.3, -1.5, 0.8, -0.2, ...]  # Scores bruts
   mask   = [1,    0,    1,    1,   ...]  # 0 = illégal

   # On masque les actions illégales
   logits_masqués = [2.3, -inf, 0.8, -0.2, ...]

   # Softmax → probabilités
   probs = softmax(logits_masqués)  # [0.62, 0.0, 0.14, 0.09, ...]
   ```

**Résultat** : L'agent obtient une distribution de probabilité sur les actions légales :
- Action A : 62% de chance
- Action B : 0% (illégale, masquée)
- Action C : 14% de chance
- Action D : 9% de chance
- ...

**Pourquoi des probabilités et pas juste "la meilleure" ?**
- Au début de l'entraînement, l'agent est nul → il doit **explorer** (essayer des actions variées)
- Avec l'expérience, il va concentrer ses probabilités sur les bonnes actions (exploitation)
- Ce compromis exploration/exploitation est au cœur du RL

---

#### Tête 2 : La Valeur (Value Head)

**Objectif** : Estimer si la situation actuelle est favorable ou défavorable.

**Fonctionnement** :
Le réseau renvoie un seul chiffre entre **-1** et **+1** :
- `+1` = "Je vais presque certainement gagner !"
- `0` = "C'est 50/50, la partie est serrée..."
- `-1` = "Je suis très mal parti, je vais perdre..."

**Pourquoi c'est utile ?**
- Pendant l'entraînement, on compare cette prédiction avec le **résultat réel** de la partie :
  - Si l'agent pensait gagner (+0.8) mais a perdu → il ajuste ses poids pour être plus pessimiste dans cette situation
  - Si l'agent pensait perdre (-0.6) mais a gagné → il ajuste pour être plus optimiste
- La tête valeur permet aussi de **stabiliser l'entraînement** en réduisant la variance des gradients (concept avancé)

---

#### L'Encoder : la partie commune

Avant de séparer en 2 têtes, on doit **comprendre** l'observation brute. C'est le rôle de l'**encoder** :

```
[ObservationTensor brut]
  board       : (19 hexagones, 6 features)  → 114 floats
  roads       : (72 edges)                   → 72 floats
  settlements : (54 vertices)                → 54 floats
  hands       : (2 joueurs, 5 ressources)    → 10 floats
  dev_cards   : (2 joueurs, 5 types)         → 10 floats
  bank        : (5 ressources)               → 5 floats
  metadata    : (phase, tour, titres, etc.)  → 10 floats

                    ↓ [Flatten tout]

         [Vecteur de ~275 floats]

                    ↓ [Couche FC : 275 → 512 neurones]
                    ↓ [ReLU + LayerNorm]
                    ↓ [Couche FC : 512 → 256 neurones]
                    ↓ [ReLU + LayerNorm]
                    ↓ [Couche FC : 256 → 128 neurones]

         [Représentation compacte : 128 features]
                 (encodage latent)
```

Ces 128 features capturent l'essence de la situation (ex: "je suis en avance", "je manque de minerai", "l'adversaire a beaucoup de routes").

Ensuite, ces 128 features sont envoyées **simultanément** aux 2 têtes (politique et valeur).

---

#### Le masquage d'actions : CRUCIAL !

Imagine que le réseau calcule des scores et dit : "Je veux construire une ville !"... mais tu n'as que 1 minerai (il en faut 3).

**Sans masque** :
- L'agent essaie l'action BuildCity()
- Le moteur rejette l'action (erreur)
- Crash ou comportement incohérent

**Avec masque** :
```python
logits = [2.3, -1.5, 0.8, ...]  # Scores bruts (BuildRoad, BuildCity, TradeBank, ...)
mask   = [1,    0,    1,   ...]  # BuildCity est illégal (mask=0)

# On met -inf sur les actions illégales
masked_logits = torch.where(mask, logits, torch.tensor(-float('inf')))
# → [2.3, -inf, 0.8, ...]

# Softmax → les actions illégales ont 0% de probabilité
probs = F.softmax(masked_logits, dim=-1)
# → [0.85, 0.0, 0.15, ...]  BuildCity a maintenant 0% de chance
```

Ainsi, l'agent ne choisira **jamais** une action interdite ! C'est une contrainte **hard** (pas apprise, mais imposée).

---

## 3. Architectures de réseaux en RL

**Question** : Est-ce toujours 2 têtes (politique + valeur) en RL ?

**Réponse** : Non ! Il existe plusieurs architectures selon le contexte. Voici les principales :

---

### 3.1 Réseau à 2 têtes partagées (Actor-Critic, ce qu'on utilise)

```
Observation → Encoder → ┬→ Tête Politique (Actor)
                        └→ Tête Valeur (Critic)
```

**Utilisé par** :
- AlphaZero (échecs, Go, shogi)
- PPO (Proximal Policy Optimization)
- A2C (Advantage Actor-Critic)

**Avantages** :
- L'encoder est **partagé** → économie de calcul et de mémoire
- Apprentissage plus stable : la valeur guide la politique
- Fonctionne bien pour les jeux de plateau (actions discrètes)

**Inconvénient** :
- Si les objectifs politique/valeur sont trop différents, ils peuvent interférer ("tirer dans des directions opposées")

---

### 3.2 Réseaux séparés (Actor-Critic avec 2 réseaux indépendants)

```
Observation → Réseau Politique (Actor)   → logits
Observation → Réseau Valeur (Critic)     → valeur
```

**Utilisé par** :
- DDPG (Deep Deterministic Policy Gradient)
- TD3 (Twin Delayed DDPG)
- SAC (Soft Actor-Critic)

**Avantages** :
- Chaque réseau est **indépendant** → pas d'interférence
- Plus flexible pour ajuster les taux d'apprentissage séparément

**Inconvénient** :
- 2× plus de paramètres → plus lent, plus gourmand en mémoire
- Nécessite plus de données pour converger

**Quand l'utiliser** : Actions continues (ex: angle de tir, vitesse d'un robot)

---

### 3.3 Réseau de Q-valeurs (DQN)

```
Observation → Réseau → Q(s, a₀), Q(s, a₁), Q(s, a₂), ...
```

**Utilisé par** :
- DQN (Deep Q-Network, Atari)
- Double DQN, Dueling DQN

**Principe** :
Le réseau estime directement la **valeur** de chaque action (Q-value).
L'agent choisit l'action avec la plus grande Q-value (greedy).

**Avantages** :
- Plus simple conceptuellement (1 seule sortie)
- Fonctionne bien avec un replay buffer

**Inconvénients** :
- Ne gère pas bien les **actions continues**
- Nécessite beaucoup de mémoire (replay buffer)
- Moins efficace pour les espaces d'actions très grands (>10k actions)

**Quand l'utiliser** : Jeux vidéo avec actions discrètes (Atari, etc.)

---

### 3.4 Transformers (moderne)

```
[Observation t-n, ..., Observation t] → Transformer → Politique + Valeur
```

**Utilisé par** :
- Decision Transformer (2021)
- Gato (DeepMind, 2022)
- Transdreamer

**Principe** :
Traite l'historique des états comme une **séquence** (comme GPT traite du texte).
Peut apprendre des dépendances temporelles complexes.

**Avantages** :
- Capture la mémoire à long terme (ex: "il y a 20 tours, j'ai vu qu'il avait beaucoup de minerai")
- Peut faire du few-shot learning (apprendre avec peu d'exemples)

**Inconvénients** :
- **Très gourmand** en calcul (attention mechanism est O(n²))
- Nécessite énormément de données
- Complexe à implémenter et déboguer

**Quand l'utiliser** : Environnements partiellement observables, ou quand l'historique est crucial

---

### 3.5 Tableau récapitulatif

| Architecture | Avantages | Inconvénients | Cas d'usage |
|--------------|-----------|---------------|-------------|
| **2 têtes partagées** | Efficace, stable, économe | Possible interférence | **Jeux de plateau, actions discrètes** |
| **2 réseaux séparés** | Flexible, pas d'interférence | 2× paramètres, plus lent | Actions continues (robotique) |
| **DQN** | Simple, replay buffer | Mal adapté aux actions continues | Jeux vidéo (Atari) |
| **Transformer** | Mémoire à long terme | Très coûteux, beaucoup de données | Environnements partiellement observables |

---

### Pourquoi on a choisi 2 têtes partagées pour CatanBot ?

✅ **Efficace** : L'encoder partage les calculs entre politique et valeur
✅ **Prouvé** : AlphaZero (échecs, Go) et PPO utilisent cette architecture avec succès
✅ **Adapté à Catan** : Espace d'actions discret (construire une route à la position X)
✅ **Entraînement stable** : La tête valeur aide à réduire la variance des gradients
✅ **Pas d'overkill** : Pas besoin de transformers pour un jeu à information parfaite

---

## 4. Comment définir la structure du réseau ?

**Question** : Comment sait-on qu'il faut 512 → 256 → 128 neurones ? Pourquoi pas 1000 → 500 → 100 ?

**Réponse** : **C'est un art autant qu'une science !** Il n'y a **pas de formule magique**, mais des règles empiriques et beaucoup d'expérimentation.

---

### 4.1 Règles de base pour la taille de l'encoder

#### Trop petit → Underfitting
- Le réseau n'a pas assez de **capacité** pour apprendre des stratégies complexes
- Symptômes : La loss descend un peu puis plafonne rapidement, l'agent reste faible

#### Trop gros → Overfitting
- Le réseau mémorise des situations spécifiques au lieu de généraliser
- Symptômes : Entraînement lent, performances variables, surapprentissage sur certains adversaires

#### Sweet spot
- Le réseau est **juste assez grand** pour capturer les patterns importants
- On peut toujours augmenter après si ça ne suffit pas

---

### 4.2 Règle empirique pour Catan

Pour dimensionner un encoder, on regarde :
- **Taille de l'observation** : ~275 features (plateau + ressources + metadata)
- **Taille de l'espace d'actions** : ~200-500 actions (selon le catalogue)
- **Complexité du jeu** : Catan est moins complexe que les échecs (10⁴³ états) mais plus que Tic-Tac-Toe

**Règle approximative** : L'encoder doit avoir entre 1× et 5× la taille de l'observation.

Pour Catan :
- Observation : 275 floats
- Première couche : 512 neurones (~2× l'observation)
- Deuxième couche : 256 neurones (réduction progressive)
- Troisième couche : 128 neurones (encodage latent compact)

→ **Total : ~150k paramètres** (raisonnable pour commencer)

---

### 4.3 Profondeur (nombre de couches)

| Profondeur | Capacité | Quand l'utiliser |
|------------|----------|------------------|
| **1-2 couches** | Faible | Problèmes linéaires simples |
| **3-5 couches** | **Sweet spot pour jeux de plateau** | Catan, échecs, Go (sans CNN) |
| **6-10 couches** | Haute | Vision par ordinateur (CNN), NLP |
| **10+ couches** | Très haute | Transformers, GPT, etc. |

Pour CatanBot, **3 couches** (512 → 256 → 128) est un bon point de départ.

---

### 4.4 Fonctions d'activation

| Activation | Formule | Usage | Avantages | Inconvénients |
|------------|---------|-------|-----------|---------------|
| **ReLU** | max(0, x) | Couches cachées | Rapide, simple | Neurones "morts" (gradient=0) |
| **LeakyReLU** | max(0.01x, x) | Couches cachées | Évite neurones morts | Légèrement plus lent |
| **Tanh** | (e^x - e^-x) / (e^x + e^-x) | Tête valeur | Sortie ∈ [-1, 1] | Peut saturer |
| **Softmax** | e^xi / Σe^xj | Tête politique | Sortie = probabilités | Nécessite masquage |

**Choix pour CatanBot** :
- **ReLU** dans l'encoder (standard, rapide)
- **Tanh** pour la tête valeur (sortie entre -1 et +1)
- **Softmax masqué** pour la tête politique (probabilités sur actions légales)

---

### 4.5 Normalisation

Les réseaux profonds (>3 couches) nécessitent une **normalisation** pour stabiliser l'entraînement :

| Technique | Principe | Avantages | Inconvénients |
|-----------|----------|-----------|---------------|
| **BatchNorm** | Normalise par batch | Très efficace en vision | Comportement différent train/test |
| **LayerNorm** | Normalise par couche | Stable, simple | Légèrement moins efficace |
| **GroupNorm** | Normalise par groupe | Indépendant de la taille du batch | Plus complexe |

**Choix pour CatanBot** : **LayerNorm** (simple, stable, standard en RL)

---

### 4.6 Méthode empirique pour ajuster

1. **Commence petit** : Encoder 256 → 128 (baseline rapide)
2. **Entraîne 10k parties** et observe les courbes de loss
3. **Analyse les symptômes** :
   - **Loss stagne vite** (< 500 itérations) → Réseau trop petit, augmente à 512 → 256 → 128
   - **Loss descend lentement mais régulièrement** → Bon dimensionnement, continue
   - **Loss oscille beaucoup** → Learning rate trop élevé ou besoin de dropout
   - **Overfitting** (loss train baisse, loss eval augmente) → Ajoute dropout ou régularisation
4. **Évalue sur baselines** :
   - Si l'agent bat **RandomLegal** (>90%) mais plafonne face à **Heuristic** (<60%) :
     - Option A : Augmenter la capacité (réseau plus gros)
     - Option B : Améliorer l'architecture (passer à CNN/GNN)
     - Option C : Améliorer l'encodage (ajouter des features)
5. **Itère** : Le RL est un processus expérimental !

---

## 5. MLP vs CNN vs GNN

**Question** : Tu as parlé de MLP, CNN, GNN... qu'est-ce que c'est ?

**Réponse** : Ce sont différents types d'**encoders** (la partie qui transforme l'observation brute en représentation compacte).

---

### 5.1 MLP (Multi-Layer Perceptron) = Réseau fully-connected

**Principe** :
```
[Input : 275 floats] → [FC 512] → [FC 256] → [FC 128] → [Output]
```
Chaque neurone est connecté à **tous** les neurones de la couche suivante.

**Avantages** :
- ✅ **Simple** à implémenter (quelques lignes PyTorch)
- ✅ Fonctionne bien pour des inputs "plats" (vecteurs 1D)
- ✅ Rapide à entraîner

**Inconvénients** :
- ❌ Ignore la structure spatiale (ex: voisinage des hexagones)
- ❌ Beaucoup de paramètres si l'input est grand

**Quand l'utiliser** : MVP, prototypage rapide, inputs sans structure spatiale

---

### 5.2 CNN (Convolutional Neural Network) = Réseau convolutif

**Principe** :
```
[Image/Grid 2D] → [Conv2D 3×3] → [Conv2D 3×3] → [Flatten] → [FC] → [Output]
```
Chaque neurone ne regarde qu'une **petite région** (ex: 3×3 pixels).

**Avantages** :
- ✅ Capture la structure **spatiale** (ex: "une colonie voisine d'un hex 6 est forte")
- ✅ Invariance par translation (apprend des patterns locaux réutilisables)
- ✅ Moins de paramètres qu'un MLP pour des images

**Inconvénients** :
- ❌ Nécessite un encodage "image-like" (grille 2D régulière)
- ❌ Catan a un plateau **hexagonal**, pas rectangulaire → besoin de padding/interpolation

**Quand l'utiliser** : Jeux sur grille (Go, échecs), vision par ordinateur

**Exemples célèbres** :
- AlphaGo (19×19 board)
- Atari (frames de jeu 84×84 pixels)

---

### 5.3 GNN (Graph Neural Network) = Réseau sur graphe

**Principe** :
```
[Graphe : vertices + edges] → [GNN layers] → [Pooling] → [FC] → [Output]
```
Chaque neurone "échange des messages" avec ses **voisins** dans le graphe.

**Avantages** :
- ✅ Capture **parfaitement** la structure hexagonale de Catan (vertices, edges, tiles)
- ✅ Invariance par rotation/symétrie (apprend des patterns génériques)
- ✅ Élégant conceptuellement (le plateau EST un graphe)

**Inconvénients** :
- ❌ Plus **complexe** à implémenter (nécessite PyTorch Geometric)
- ❌ Moins de ressources/tutoriels que MLP/CNN
- ❌ Peut être plus lent à entraîner

**Quand l'utiliser** : Quand le domaine a une structure de graphe naturelle

**Exemples célèbres** :
- Molécules (atomes = nœuds, liaisons = arêtes)
- Réseaux sociaux
- Systèmes de recommandation

---

### 5.4 Tableau comparatif pour Catan

| Encoder | Implémentation | Performance attendue | Temps dev | Justesse architecturale |
|---------|----------------|----------------------|-----------|-------------------------|
| **MLP** | Triviale | Bonne pour MVP | 1h | ⭐⭐ |
| **CNN** | Moyenne (padding hex) | Meilleure si bien fait | 3-5h | ⭐⭐⭐ |
| **GNN** | Complexe (PyTorch Geometric) | Optimale en théorie | 1-2j | ⭐⭐⭐⭐⭐ |

---

### 5.5 Stratégie d'itération pour CatanBot

**Phase 1 (RL-005, maintenant)** : MLP 512 → 256 → 128
- Objectif : MVP fonctionnel rapidement
- Validation : Bat RandomLegal (>90%), commence à challenger Heuristic

**Phase 2 (RL-006)** : Entraînement PPO avec MLP
- Objectif : Atteindre ~60-65% de winrate vs Heuristic
- Si ça plafonne → passer à Phase 3

**Phase 3 (RL-011, futur)** : Améliorer l'architecture
- Option A : Passer à un **CNN** avec encodage hex → grid 2D
- Option B : Passer à un **GNN** (PyTorch Geometric)
- Objectif : Franchir la barre des 70-75% vs Heuristic

**Phase 4 (RL-012+, futur lointain)** : Peaufinage
- Hyperparamètres
- Curriculum learning
- Reward shaping
- Objectif : Battre des humains experts

---

## 6. Peut-on battre des humains experts ?

**Question** : Est-on **sûr** d'arriver à un résultat meilleur que n'importe quel humain ?

**Réponse** : **Non, absolument pas !** Mais c'est un objectif atteignable avec suffisamment de travail.

---

### 6.1 Exemples de succès en RL

| Jeu | Agent RL | Niveau atteint | Année | Contexte |
|-----|----------|----------------|-------|----------|
| **Échecs** | AlphaZero | Bat Stockfish (meilleur moteur) | 2017 | 44M parties, 5000 TPUs |
| **Go** | AlphaGo | Bat Lee Sedol (champion monde) | 2016 | 30M parties, 1920 CPUs + 280 GPUs |
| **Poker** | Pluribus | Bat 5 pros simultanément | 2019 | 12 jours, 64 CPU cores |
| **StarCraft II** | AlphaStar | Niveau Grandmaster (top 0.2%) | 2019 | 200 ans de temps de jeu |
| **Dota 2** | OpenAI Five | Bat l'équipe OG (champions TI) | 2018 | 10 mois, 128k CPU + 256 GPUs |

**Constat** : Oui, c'est possible ! Mais ça demande beaucoup de ressources.

---

### 6.2 Pourquoi c'est possible ?

1. **Pas de fatigue** : L'IA peut jouer des millions de parties sans pause
2. **Zéro biais cognitif** : Pas d'émotions, pas de "tilt", pas d'attachement irrationnel à une stratégie
3. **Exploration exhaustive** : L'IA teste des stratégies que les humains n'essaient jamais (ex: sacrifices contre-intuitifs)
4. **Apprentissage continu** : L'IA s'améliore à chaque partie, les humains ont un plateau

---

### 6.3 Pourquoi ça pourrait échouer pour CatanBot ?

1. **Pas assez de données** : AlphaZero a joué 44M parties, on vise 1-10M pour CatanBot
2. **Architecture inadaptée** : Si le MLP ne capture pas la complexité, et qu'on ne passe pas à CNN/GNN
3. **Reward mal défini** :
   - Si on récompense seulement victoire/défaite (+1/-1), l'agent peut stagner
   - Si on récompense trop de sous-objectifs (reward shaping), l'agent peut "tricher"
4. **Hasard** : Catan a beaucoup de randomness (dés, cartes dev) → plus dur d'apprendre qu'aux échecs
5. **Ressources limitées** : On n'a pas 5000 TPUs comme DeepMind 😅

---

### 6.4 Solutions si l'agent plafonne

#### Solution 1 : Augmenter la capacité du réseau
- Passer de MLP (512 → 256 → 128) à MLP plus gros (1024 → 512 → 256)
- Passer à CNN ou GNN
- Ajouter plus de couches

**Quand l'utiliser** : Si la loss descend régulièrement mais l'agent reste faible vs Heuristic

---

#### Solution 2 : Améliorer l'encodage
- Ajouter des features calculées (ex: "distance à la prochaine colonie légale", "probabilité d'obtenir X ressources dans 3 tours")
- Encoder l'historique (ex: "combien de fois j'ai joué un chevalier dans les 5 derniers tours")
- Normalisation adaptative

**Quand l'utiliser** : Si l'agent fait des erreurs "stupides" (ex: ne voit pas une opportunité évidente)

---

#### Solution 3 : Curriculum learning
- Faire jouer l'agent contre des adversaires de plus en plus forts :
  1. RandomLegal (niveau 0)
  2. Heuristique basique (niveau 1)
  3. Heuristique avancée (niveau 2)
  4. Self-play (niveau 3)
- Augmenter progressivement la difficulté

**Quand l'utiliser** : Si l'agent stagne en self-play (pas de signal d'apprentissage)

---

#### Solution 4 : Reward shaping
- Récompenser les sous-objectifs :
  - +0.1 pour chaque colonie construite
  - +0.2 pour chaque ville construite
  - +0.05 pour obtenir le chemin le plus long
  - -0.05 pour se faire voler par le voleur
- **Danger** : Si les récompenses intermédiaires sont mal calibrées, l'agent peut tricher (optimiser les sous-objectifs sans gagner)

**Quand l'utiliser** : En dernier recours, avec précaution

---

#### Solution 5 : Jouer plus de parties
- AlphaZero a joué **44 millions** de parties d'échecs
- On peut viser :
  - **Phase 1** : 100k parties (validation MVP)
  - **Phase 2** : 1M parties (challenger Heuristic)
  - **Phase 3** : 10M parties (battre des humains bons)

**Quand l'utiliser** : Toujours ! Plus de données = meilleur agent (jusqu'à un plateau)

---

#### Solution 6 : Ensembling
- Entraîner **plusieurs agents** avec des seeds/hyperparamètres différents
- À l'évaluation, faire voter les agents ou moyenner leurs politiques
- Technique utilisée par AlphaGo

**Quand l'utiliser** : Quand on veut maximiser la robustesse pour une compétition

---

### 6.5 Objectif réaliste pour CatanBot

| Phase | Objectif | Ressources | Échéance |
|-------|----------|------------|----------|
| **MVP (RL-005 à RL-007)** | Bat RandomLegal (>90%) | 100k parties, 1 GPU, 1 semaine | Court terme |
| **V1 (RL-008 à RL-010)** | Bat Heuristic (>65%) | 1M parties, 1 GPU, 1 mois | Moyen terme |
| **V2 (futur)** | Bat humains bons (>70%) | 5-10M parties, 1-4 GPUs, 3-6 mois | Long terme |
| **V3 (futur lointain)** | Bat humains experts (>80%) | 20M+ parties, architecture avancée | Très long terme |

---

## 7. Nos choix pour CatanBot

### 7.1 Récapitulatif des décisions techniques

| Décision | Justification |
|----------|---------------|
| **Architecture 2 têtes partagées** | Efficace, prouvé (AlphaZero, PPO), standard pour jeux de plateau |
| **Encoder MLP** | Simple pour MVP, on pourra itérer vers CNN/GNN après évaluation |
| **Taille 512 → 256 → 128** | Compromis capacité/vitesse pour Catan (~150k paramètres) |
| **ReLU + LayerNorm** | Standard, stable, rapide |
| **Masquage d'actions** | Indispensable pour éviter les actions illégales |
| **Perspective ego-centrée** | Déjà implémentée dans ObservationTensor (RL-001) |

---

### 7.2 Architecture détaillée pour RL-005

```python
class CatanPolicyValueNetwork(nn.Module):
    def __init__(self, obs_size: int, action_size: int, hidden_sizes: List[int] = [512, 256, 128]):
        # Encoder (MLP)
        self.encoder = nn.Sequential(
            nn.Linear(obs_size, hidden_sizes[0]),
            nn.ReLU(),
            nn.LayerNorm(hidden_sizes[0]),
            nn.Linear(hidden_sizes[0], hidden_sizes[1]),
            nn.ReLU(),
            nn.LayerNorm(hidden_sizes[1]),
            nn.Linear(hidden_sizes[1], hidden_sizes[2]),
            nn.ReLU(),
            nn.LayerNorm(hidden_sizes[2]),
        )

        # Tête politique
        self.policy_head = nn.Linear(hidden_sizes[2], action_size)

        # Tête valeur
        self.value_head = nn.Sequential(
            nn.Linear(hidden_sizes[2], 1),
            nn.Tanh()  # Sortie ∈ [-1, 1]
        )

    def forward(self, obs: torch.Tensor, mask: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # Encoder
        features = self.encoder(obs)  # (batch, 128)

        # Politique
        logits = self.policy_head(features)  # (batch, action_size)
        masked_logits = torch.where(mask, logits, torch.tensor(-float('inf')))

        # Valeur
        value = self.value_head(features)  # (batch, 1)

        return masked_logits, value
```

---

### 7.3 Tests de validation (RL-005)

Les tests unitaires vérifieront :

1. **Shapes** :
   - Input : (batch, obs_size) + (batch, action_size) mask
   - Output : (batch, action_size) logits + (batch, 1) value

2. **Masquage** :
   - Les logits masqués contiennent `-inf` aux bons endroits
   - Softmax(masked_logits) donne 0% aux actions illégales

3. **Valeur** :
   - La sortie de la tête valeur est bien ∈ [-1, 1] (grâce à Tanh)

4. **Gradient flow** :
   - Backpropagation fonctionne (pas de gradient=0 partout)

5. **Intégration** :
   - Le réseau accepte un vrai `ObservationTensor` (de RL-001)
   - Le masque vient d'un vrai `ActionEncoder` (de RL-002)

---

### 7.4 Prochaines étapes après RL-005

1. **RL-006** : Entraînement PPO avec masques
   - Implémenter la boucle d'entraînement (collect experiences → update network)
   - Valider que la loss descend

2. **RL-007** : Évaluation périodique vs baselines
   - Tous les N checkpoints, lancer 200 parties vs RandomLegal et Heuristic
   - Logger winrate, ELO, etc.

3. **RL-008** : Auto-play miroir et ligue
   - Self-play : l'agent joue contre lui-même (ou des versions passées)
   - Créer une "ligue" d'adversaires

4. **RL-011 (futur)** : Améliorer l'architecture
   - Si le MLP plafonne, tester CNN ou GNN

---

## Conclusion

Le Reinforcement Learning est un domaine **empirique** : on construit des hypothèses, on teste, on ajuste. Il n'y a pas de formule magique pour garantir qu'un agent battra des humains experts, mais les succès d'AlphaZero, AlphaGo et autres montrent que c'est possible avec :

1. Une **architecture adaptée** (on commence avec 2 têtes + MLP)
2. Un **encodage pertinent** (perspective ego-centrée, normalisation)
3. Du **volume** (jouer des millions de parties)
4. De l'**itération** (ajuster l'architecture, les hyperparamètres, le curriculum)

CatanBot est sur la bonne voie ! 🚀

---

## Ressources complémentaires

- **Cours** :
  - [Spinning Up in Deep RL (OpenAI)](https://spinningup.openai.com/)
  - [DeepMind x UCL Deep RL Course](https://www.deepmind.com/learning-resources/deep-reinforcement-learning-lecture-series-2021)

- **Papers** :
  - AlphaZero : "Mastering Chess and Shogi by Self-Play with a General Reinforcement Learning Algorithm" (2017)
  - PPO : "Proximal Policy Optimization Algorithms" (2017)

- **Code** :
  - [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3) : Implémentations RL en PyTorch
  - [PyTorch Geometric](https://pytorch-geometric.readthedocs.io/) : Pour les GNN (futur)

---

**Document rédigé pour CatanBot - 2025**
**Auteur : Claude (Agent RL) + Thomas (Human Coach)** 🤖🤝👨‍💻
