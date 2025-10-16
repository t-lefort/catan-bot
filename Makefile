.PHONY: help install test lint format clean gui simulate train

help:
	@echo "CatanBot - Commandes disponibles:"
	@echo ""
	@echo "  make install     - Installer les dépendances"
	@echo "  make test        - Lancer les tests"
	@echo "  make lint        - Vérifier le code (mypy + ruff)"
	@echo "  make format      - Formatter le code (black + ruff)"
	@echo "  make clean       - Nettoyer les fichiers temporaires"
	@echo ""
	@echo "  make gui         - Lancer l'interface graphique"
	@echo "  make simulate    - Lancer des simulations rapides"
	@echo "  make train       - Entraîner le modèle RL"

install:
	pip install -r requirements.txt

test:
	pytest -v

test-coverage:
	pytest --cov=src --cov-report=html --cov-report=term

lint:
	mypy src/
	ruff check src/ tests/

format:
	black src/ tests/
	ruff check --fix src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage

gui:
	python -m src.gui.game_window

simulate:
	python -m src.simulate

train:
	python -m src.rl.train

# Alias pour la simulation avec arguments
simulate-fast:
	python -m src.simulate --num-games 10000

benchmark:
	python -m src.simulate --num-games 10000 --benchmark
