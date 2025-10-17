# Projet Python — Squelette minimal

Ce dépôt est initialisé avec:
- `README.md` (vous êtes ici)
- `AGENTS.md` (règles et bonnes pratiques pour travailler avec un agent IA de code)
- `docs/` (dossier pour la documentation projet)

Aucun code applicatif n’est encore ajouté volontairement. L’objectif est de documenter, planifier et établir les règles de collaboration avant d’implémenter quoi que ce soit.

## Démarrage
- Lisez `AGENTS.md` pour comprendre comment collaborer efficacement avec l’agent IA.
- Placez la documentation fonctionnelle et technique dans `docs/` (ex. `docs/overview.md`, `docs/specs.md`).
- Utilisez `PLAN.yaml` pour consigner le plan détaillé et l’avancement (source de vérité persistante).
- Une fois la documentation validée, on définira un plan d’implémentation et des tests à écrire en premier.

## Structure actuelle

```
.
├── README.md
├── AGENTS.md
├── JOURNAL_DE_BORD.md
├── PLAN.yaml
└── docs/
    └── README.md
```

## Prochaines étapes
- Renseigner la documentation dans `docs/` (contexte, objectifs, specs, invariants).
- Définir un plan de travail découpé en étapes vérifiables.
- Écrire les tests avant le code selon le plan validé.
- Implémenter ensuite le minimum pour faire passer les tests.

## Docs
- Vue d’ensemble: `docs/overview.md`
- Règles et invariants: `docs/specs.md`

## Installation et environnement virtuel

Pour garantir un environnement de développement reproductible :

```bash
# Créer l'environnement virtuel (une seule fois)
python3 -m venv venv

# Activer l'environnement virtuel
# Sur macOS/Linux :
source venv/bin/activate
# Sur Windows :
venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

## Tests (contrats, avant moteur)
- Activer le venv: `source venv/bin/activate`
- Lancer: `pytest -q`
- Avec couverture: `pytest --cov=catan tests/`
