"""Architecture de réseau de neurones pour le RL Catan (RL-005)."""

from typing import Dict, Optional, Sequence, Tuple

import torch
import torch.nn as nn


class CatanPolicyValueNetwork(nn.Module):
    """Réseau de politique et de valeur pour l'agent Catan.

    Architecture:
        - Encodeur partagé qui traite toutes les composantes de l'observation
        - Tête de politique (policy head) qui produit des logits d'actions
        - Tête de valeur (value head) qui estime V(s)

    L'observation est encodée de manière ego-centrée (voir features.py), ce qui
    permet à l'agent d'apprendre plus efficacement sans dépendre de sa position
    dans l'ordre des joueurs.

    Args:
        action_size: taille de l'espace d'actions (dimension de sortie politique)
        hidden_sizes: liste des dimensions des couches cachées partagées
    """

    def __init__(
        self,
        *,
        action_size: int,
        hidden_sizes: Optional[Sequence[int]] = None,
    ) -> None:
        super().__init__()

        if action_size <= 0:
            raise ValueError("action_size doit être strictement positif")

        self.action_size = action_size
        self.hidden_sizes = list(hidden_sizes or [256, 128])

        # Calcul de la taille totale après aplatissement des composantes
        # board: (19, 6), roads: (72,), settlements: (54,), hands: (2,5),
        # dev_cards: (2,5), bank: (5,), metadata: (10,)
        board_size = 19 * 6  # 114
        roads_size = 72
        settlements_size = 54
        hands_size = 2 * 5  # 10
        dev_cards_size = 2 * 5  # 10
        bank_size = 5
        metadata_size = 10

        self.input_size = (
            board_size
            + roads_size
            + settlements_size
            + hands_size
            + dev_cards_size
            + bank_size
            + metadata_size
        )  # Total: 275

        # Encodeur partagé (backbone)
        layers = []
        prev_size = self.input_size
        for hidden_size in self.hidden_sizes:
            layers.extend(
                [
                    nn.Linear(prev_size, hidden_size),
                    nn.ReLU(),
                    nn.LayerNorm(hidden_size),
                ]
            )
            prev_size = hidden_size

        self.shared_encoder = nn.Sequential(*layers)

        # Tête de politique
        self.policy_head = nn.Sequential(
            nn.Linear(prev_size, prev_size // 2),
            nn.ReLU(),
            nn.Linear(prev_size // 2, action_size),
        )

        # Tête de valeur
        self.value_head = nn.Sequential(
            nn.Linear(prev_size, prev_size // 2),
            nn.ReLU(),
            nn.Linear(prev_size // 2, 1),
        )

    def forward(
        self, obs_dict: Dict[str, torch.Tensor]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass du réseau.

        Args:
            obs_dict: dictionnaire contenant les tenseurs d'observation:
                - "board": (B, 19, 6)
                - "roads": (B, 72)
                - "settlements": (B, 54)
                - "hands": (B, 2, 5)
                - "development_cards": (B, 2, 5)
                - "bank": (B, 5)
                - "metadata": (B, 10)

        Returns:
            Tuple (policy_logits, value):
                - policy_logits: (B, action_size) logits pour chaque action
                - value: (B,) estimation de la valeur de l'état
        """
        # Aplatir toutes les composantes et les concaténer
        board_flat = obs_dict["board"].flatten(start_dim=1)  # (B, 114)
        roads_flat = obs_dict["roads"].flatten(start_dim=1)  # (B, 72)
        settlements_flat = obs_dict["settlements"].flatten(start_dim=1)  # (B, 54)
        hands_flat = obs_dict["hands"].flatten(start_dim=1)  # (B, 10)
        dev_cards_flat = obs_dict["development_cards"].flatten(start_dim=1)  # (B, 10)
        bank_flat = obs_dict["bank"].flatten(start_dim=1)  # (B, 5)
        metadata_flat = obs_dict["metadata"].flatten(start_dim=1)  # (B, 10)

        # Concaténation de toutes les features
        x = torch.cat(
            [
                board_flat,
                roads_flat,
                settlements_flat,
                hands_flat,
                dev_cards_flat,
                bank_flat,
                metadata_flat,
            ],
            dim=-1,
        )  # (B, 275)

        # Passage dans l'encodeur partagé
        shared_features = self.shared_encoder(x)  # (B, hidden_size)

        # Têtes de politique et de valeur
        policy_logits = self.policy_head(shared_features)  # (B, action_size)
        value = self.value_head(shared_features).squeeze(-1)  # (B,)

        return policy_logits, value

    def masked_softmax(
        self, logits: torch.Tensor, mask: torch.Tensor, temperature: float = 1.0
    ) -> torch.Tensor:
        """Applique un softmax masqué pour obtenir une distribution de probabilité.

        Les actions illégales (mask=False) reçoivent une probabilité de 0.

        Args:
            logits: (B, action_size) logits bruts
            mask: (B, action_size) masque booléen (True = légal, False = illégal)
            temperature: température pour contrôler l'entropie (défaut 1.0)

        Returns:
            probs: (B, action_size) distribution de probabilité normalisée
        """
        # Remplacer les logits des actions illégales par -inf
        masked_logits = torch.where(
            mask, logits / temperature, torch.tensor(float("-inf"), device=logits.device)
        )

        # Appliquer softmax
        probs = torch.softmax(masked_logits, dim=-1)

        return probs

    def select_action(
        self,
        obs_dict: Dict[str, torch.Tensor],
        mask: torch.Tensor,
        deterministic: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sélectionne une action selon la politique apprise.

        Args:
            obs_dict: observation actuelle
            mask: masque des actions légales
            deterministic: si True, choisit l'action avec la plus haute probabilité

        Returns:
            Tuple (action_indices, log_probs, value):
                - action_indices: (B,) indices des actions sélectionnées
                - log_probs: (B,) log-probabilités des actions choisies
                - value: (B,) estimations de valeur
        """
        with torch.no_grad():
            policy_logits, value = self.forward(obs_dict)
            probs = self.masked_softmax(policy_logits, mask)

            if deterministic:
                # Choisir l'action avec la plus haute probabilité
                action_indices = torch.argmax(probs, dim=-1)
            else:
                # Échantillonner selon la distribution
                action_indices = torch.multinomial(probs, num_samples=1).squeeze(-1)

            # Calculer les log-probabilités
            log_probs = torch.log(probs.gather(-1, action_indices.unsqueeze(-1)).squeeze(-1) + 1e-8)

        return action_indices, log_probs, value


__all__ = ["CatanPolicyValueNetwork"]
