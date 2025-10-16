"""Gymnasium environment for Catan.

Wrapper autour du GameState pour l'entraînement RL.
Compatible avec Gymnasium (successeur de OpenAI Gym).
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from gymnasium.core import RenderFrame
from typing import cast

from ..core.game_state import GameState
from ..core.actions import Action
from ..core.board import Board


class CatanEnv(gym.Env):
    """
    Environment Catan compatible Gymnasium.

    Observations:
    - État du plateau
    - Ressources de chaque joueur
    - Constructions
    - Phase du jeu

    Actions:
    - Toutes les actions possibles (voir actions.py)
    - Action masking pour ne garder que les actions valides

    Rewards:
    - +1 pour gagner
    - 0 sinon
    - Peut être modifié pour du reward shaping
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(
        self,
        num_players: int = 4,
        victory_points: int = 10,
        render_mode: Optional[str] = None,
    ):
        super().__init__()

        self.num_players = num_players
        self.victory_points = victory_points
        self.render_mode = render_mode

        # État du jeu
        self.game_state: Optional[GameState] = None

        # Définir l'espace d'observation (simplifié pour l'instant)
        # TODO: Définir précisément la structure d'observation
        self.observation_space = spaces.Dict({
            "board": spaces.Box(low=0, high=12, shape=(19, 3), dtype=np.int32),
            "resources": spaces.Box(low=0, high=100, shape=(num_players, 5), dtype=np.int32),
            "buildings": spaces.Box(low=0, high=num_players, shape=(54, 3), dtype=np.int32),
            "current_player": spaces.Discrete(num_players),
        })

        # Espace d'action (nombre maximum d'actions possibles)
        # TODO: Calculer précisément en fonction du plateau
        self.max_actions = 1000
        self.action_space = spaces.Discrete(self.max_actions)

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """Réinitialise l'environnement."""
        super().reset(seed=seed)

        # Créer un nouveau plateau
        board = Board.create_standard_board(shuffle=True)

        # Initialiser le game state
        self.game_state = GameState(
            board=board,
            num_players=self.num_players,
            victory_points_to_win=self.victory_points,
        )

        # TODO: Initialiser les joueurs
        # TODO: Phase de setup

        observation = self._get_observation()
        info = self._get_info()

        return observation, info

    def step(
        self, action: int
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """
        Exécute une action.

        Returns:
            observation: nouvelle observation
            reward: récompense
            terminated: True si la partie est terminée
            truncated: True si la partie est tronquée (limite de tours)
            info: informations supplémentaires
        """
        assert self.game_state is not None, "Call reset() first"

        # Convertir l'action entière en Action
        action_obj = self._decode_action(action)

        # Appliquer l'action
        self.game_state = self.game_state.apply_action(action_obj)

        # Calculer la récompense
        reward = self._compute_reward()

        # Vérifier si la partie est terminée
        terminated = self.game_state.is_game_over()
        truncated = False  # TODO: Limite de tours

        observation = self._get_observation()
        info = self._get_info()

        return observation, reward, terminated, truncated, info

    def _get_observation(self) -> Dict[str, Any]:
        """Construit l'observation à partir du game state."""
        assert self.game_state is not None

        # TODO: Encoder l'état du jeu en observation
        return {
            "board": np.zeros((19, 3), dtype=np.int32),
            "resources": np.zeros((self.num_players, 5), dtype=np.int32),
            "buildings": np.zeros((54, 3), dtype=np.int32),
            "current_player": self.game_state.current_player_idx,
        }

    def _get_info(self) -> Dict[str, Any]:
        """Informations supplémentaires."""
        assert self.game_state is not None

        return {
            "turn_number": self.game_state.turn_number,
            "current_player": self.game_state.current_player_idx,
            "valid_actions": self._get_valid_actions_mask(),
        }

    def _get_valid_actions_mask(self) -> np.ndarray:
        """Retourne un masque des actions valides (1 = valide, 0 = invalide)."""
        assert self.game_state is not None

        mask = np.zeros(self.max_actions, dtype=np.int8)
        valid_actions = self.game_state.get_valid_actions()

        for action in valid_actions:
            action_idx = self._encode_action(action)
            if action_idx < self.max_actions:
                mask[action_idx] = 1

        return mask

    def _encode_action(self, action: Action) -> int:
        """Encode une Action en entier."""
        # TODO: Implémenter l'encodage action -> int
        return 0

    def _decode_action(self, action_idx: int) -> Action:
        """Décode un entier en Action."""
        # TODO: Implémenter le décodage int -> action
        from ..core.actions import EndTurnAction
        return EndTurnAction()

    def _compute_reward(self) -> float:
        """Calcule la récompense pour le joueur actuel."""
        assert self.game_state is not None

        # Récompense simple: +1 si gagné, 0 sinon
        if self.game_state.is_game_over():
            winner = self.game_state.check_victory()
            if winner == self.game_state.current_player_idx:
                return 1.0
            else:
                return 0.0

        # TODO: Reward shaping (optionnel)
        return 0.0

    def render(self) -> Optional[RenderFrame] | list[RenderFrame] | None:
        """Affiche l'état du jeu."""
        if self.render_mode == "human":
            # TODO: Affichage texte
            print(f"Game state: {self.game_state}")
        elif self.render_mode == "rgb_array":
            # TODO: Rendu graphique
            return cast(RenderFrame, np.zeros((600, 800, 3), dtype=np.uint8))
        return None

    def close(self) -> None:
        """Nettoie les ressources."""
        pass
