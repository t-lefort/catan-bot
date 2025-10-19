# RL self-play - Objectifs et métriques

## Finalité
- Entrainer des agents Catane 1v1 capables de battre des heuristiques fortes et de progresser en ligue miroir.
- Exploiter le moteur headless et la sérialisation (`docs/schemas.md`) pour générer des transitions reproductibles.
- Fournir des indicateurs clairs pour suivre la progression, détecter les régressions et définir les jalons de livraison.

## Baselines de référence
- **RandomLegal** : choisit uniformément une action légale. Sert de lower bound (winrate cible >= 0.9).
- **Heuristique classique** : bot basé sur règles (priorité villes -> colonies -> routes, gestion ports). Cible initiale : winrate >= 0.65.

## KPIs principaux

| KPI | Définition | Cible / seuil d'alerte | Fréquence |
|-----|------------|------------------------|-----------|
| Winrate vs RandomLegal | % de victoires sur 200 matchs (seedés) | >= 90 % ; alerte si < 85 % | À chaque checkpoint majeur |
| Winrate vs Heuristique | % de victoires sur 500 matchs | >= 65 % ; alerte si < 60 % | Hebdomadaire ou après 5 itérations PPO |
| ELO relatif | Calcul Elo avec Heuristique fixée à 1500 | Cible > 1650 ; alerte si dérive <= -50 | Après chaque run d'évaluation |
| Points / 100 tours | VP moyens accumulés sur 100 tours simulés | Cible >= 73 VP; alerte si < 65 | Monitoring continu (TensorBoard) |
| Longueur moyenne des parties | Tours moyens par partie complète | Cible < 110 tours; hausse > +15 % = régression possible | Monitoring continu |
| Taux de défausse bien géré | % de séquences où discard >9 respecté sans erreur | 100 %; alerte si < 99 % | Tests contractuels + monitoring |

### Métriques secondaires
- Ressources moyennes en main en fin de partie (surplus limité).
- Utilisation des ports (% trades port vs total trades).
- Fréquence de jeu des cartes développement (chevalier, progrès).
- Ratio de victoires en premier joueur vs deuxième (équité).

## Cibles de performance simulation
- **Throughput** : >= 120 parties/s sur machine de référence (MacBook Pro M2, 8 cœurs) avec 4 workers multiprocess.
- **Latency step()** : < 6 us par transition côté moteur (moyenne), < 25 us p95 côté runner RL.
- **Overhead sérialisation** : snapshot complet compressé < 5 KB, conversion `State -> ObservationTensor` < 40 us.
- **Scaling** : doublement des workers (4 -> 8) doit fournir au moins 1.7x le throughput (cible 200 parties/s).

## Cadence d'évaluation
1. **Checkpoints fréquents** : sauvegarde toutes les 5 itérations PPO (ou 50k transitions) -> évaluation vs RandomLegal (200 matchs).
2. **Banc hebdomadaire** : 500 matchs vs Heuristique, calcul ELO, mise à jour dashboard.
3. **Regression suite à merge** : relecture des KPIs (winrate, points/100 tours, longueur) avant release majeure.
4. **Tests de non-régression** : scripts automatiques (TODO) comparant le moteur actuel à un checkpoint de référence.

## Instrumentation et logging
- Export TensorBoard : pertes PPO/A2C, entropie, ratio de clip, valeur moyenne.
- Journal `sim.runner` : jeux/s, latence par action, erreurs de validation moteur.
- Archivage des `ActionRecord` compressés pour analyses offline (stockage rotatif 30 jours).
- Alerting (optionnel) : seuils d'alerte KPI déclenchent une notification (Slack/Email).

## Qualité et reproductibilité
- Toutes les évaluations utilisent seeds fixes communiquées dans `JOURNAL_DE_BORD.md`.
- Les politiques baseline sont versionnées (`external/baselines/heuristic_v1.py` etc.).
- Scripts `tools/` fourniront commandes reproductibles (`python -m catan.sim.eval --policy ppo_latest --vs heuristic_v1 --episodes 500 --seed-suite seeds/rl_eval.yaml`).

## Roadmap liée
- RL-001 : implémenter l'encodage observation conforme à `docs/schemas.md`.
- RL-002 : définir l'espace d'action + masques alignés sur le moteur.
- RL-003 : livrer RandomLegal + Heuristique.
- RL-004/RL-006 : pipeline PPO/A2C avec buffer auto-play.
- RL-007/RL-010 : mise en place du dashboard live avec winrate, ELO, points/100 tours.
