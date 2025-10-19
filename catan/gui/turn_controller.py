"""Contrôleur pour le tour de jeu GUI (GUI-004).

Ce module gère l'interaction utilisateur durant le tour de jeu principal.
Conforme aux specs docs/gui-h2h.md section "2. Tour standard" et "3. Gestion du voleur".

Responsabilités:
- Gérer le lancer de dés
- Gérer la phase de défausse (main > 9 cartes)
- Gérer le déplacement du voleur
- Gérer le vol de ressource
- Fournir les instructions contextuelles pour l'UI
- Maintenir la synchronisation avec l'état du jeu
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import pygame

from catan.app.game_service import GameService
from catan.engine.state import GameState, TurnSubPhase
from catan.engine.actions import Action, RollDice, DiscardResources, MoveRobber


class TurnController:
    """Contrôleur pour le tour de jeu GUI.

    Gère l'interaction utilisateur durant le tour de jeu et fournit
    les données nécessaires pour l'affichage (positions légales, instructions).
    """

    def __init__(self, game_service: GameService, screen: pygame.Surface) -> None:
        """Initialize turn controller.

        Args:
            game_service: Service de jeu orchestrant l'état
            screen: Surface pygame pour l'affichage
        """
        self.game_service = game_service
        self.screen = screen
        self.state: GameState = game_service.state

        # Cache for legal actions to avoid recomputation
        self._legal_actions_cache: Optional[List[Action]] = None

    def refresh_state(self) -> None:
        """Refresh internal state from game service.

        Doit être appelé après chaque action pour synchroniser l'état.
        """
        self.state = self.game_service.state
        self._legal_actions_cache = None

    def _get_legal_actions(self) -> List[Action]:
        """Get legal actions with caching."""
        if self._legal_actions_cache is None:
            self._legal_actions_cache = self.state.legal_actions()
        return self._legal_actions_cache

    # === Dice rolling ===

    def can_roll_dice(self) -> bool:
        """Check if dice can be rolled.

        Returns:
            True if dice can be rolled, False otherwise
        """
        return not self.state.dice_rolled_this_turn

    def handle_roll_dice(
        self,
        forced_value: Optional[int] = None,
        forced_dice: Optional[tuple[int, int]] = None
    ) -> Optional[int]:
        """Handle dice roll action.

        Args:
            forced_value: Optional forced total value (for testing, converted to dice pair)
            forced_dice: Optional forced dice pair (for testing)

        Returns:
            Dice roll result, or None if roll was not legal
        """
        if not self.can_roll_dice():
            return None

        # Convert forced_value to dice pair if provided
        dice_pair = None
        if forced_dice is not None:
            dice_pair = forced_dice
        elif forced_value is not None:
            # Convert total to a valid dice pair
            # For example, 7 could be (3, 4), 2 is (1, 1), 12 is (6, 6)
            if forced_value == 2:
                dice_pair = (1, 1)
            elif forced_value == 12:
                dice_pair = (6, 6)
            else:
                # For other values, split evenly if possible
                # e.g., 7 -> (3, 4), 8 -> (4, 4)
                die1 = forced_value // 2
                die2 = forced_value - die1
                # Ensure both dice are in valid range [1, 6]
                if die1 < 1:
                    die1 = 1
                    die2 = forced_value - 1
                elif die2 > 6:
                    die2 = 6
                    die1 = forced_value - 6
                dice_pair = (die1, die2)

        # Create and dispatch roll dice action
        action = RollDice(forced_value=dice_pair)
        self.game_service.dispatch(action)

        # Refresh state
        self.refresh_state()

        return self.state.last_dice_roll

    # === Discard phase ===

    def is_in_discard_phase(self) -> bool:
        """Check if currently in discard phase.

        Returns:
            True if in discard phase
        """
        return self.state.turn_subphase == TurnSubPhase.ROBBER_DISCARD

    def get_discard_requirements(self) -> Dict[int, int]:
        """Get discard requirements for each player.

        Returns:
            Dictionary mapping player_id to number of cards to discard
        """
        return dict(self.state.pending_discards)

    def handle_discard(
        self,
        player_id: int,
        resources: Dict[str, int]
    ) -> bool:
        """Handle discard action for a player.

        Args:
            player_id: Player performing the discard
            resources: Resources to discard

        Returns:
            True if discard was successful, False otherwise
        """
        if not self.is_in_discard_phase():
            return False

        if player_id not in self.state.pending_discards:
            return False

        # Create and dispatch discard action
        action = DiscardResources(resources=resources)

        # Check if action is legal
        legal_actions = self._get_legal_actions()
        if action not in legal_actions:
            return False

        self.game_service.dispatch(action)
        self.refresh_state()

        return True

    # === Robber movement ===

    def is_in_robber_move_phase(self) -> bool:
        """Check if currently in robber move phase.

        Returns:
            True if in robber move phase
        """
        return self.state.turn_subphase == TurnSubPhase.ROBBER_MOVE

    def get_legal_robber_tiles(self) -> Set[int]:
        """Get set of tile IDs where robber can be moved.

        Returns:
            Set of legal tile IDs
        """
        legal_actions = self._get_legal_actions()
        return {
            action.tile_id
            for action in legal_actions
            if isinstance(action, MoveRobber)
        }

    def get_stealable_players(self, tile_id: int) -> Set[int]:
        """Get set of player IDs that can be stolen from at given tile.

        Args:
            tile_id: Tile where robber will be placed

        Returns:
            Set of player IDs that can be stolen from
        """
        legal_actions = self._get_legal_actions()
        stealable = set()

        for action in legal_actions:
            if isinstance(action, MoveRobber) and action.tile_id == tile_id:
                if action.steal_from is not None:
                    stealable.add(action.steal_from)

        return stealable

    def handle_robber_move(
        self,
        tile_id: int,
        steal_from: Optional[int] = None
    ) -> bool:
        """Handle robber movement.

        Args:
            tile_id: Tile to move robber to
            steal_from: Optional player ID to steal from

        Returns:
            True if move was successful, False otherwise
        """
        if not self.is_in_robber_move_phase():
            return False

        # Create action
        action = MoveRobber(tile_id=tile_id, steal_from=steal_from)

        # Check if action is legal
        legal_actions = self._get_legal_actions()
        if action not in legal_actions:
            return False

        self.game_service.dispatch(action)
        self.refresh_state()

        return True

    # === Instructions ===

    def get_instructions(self) -> str:
        """Get contextual instructions for the current player.

        Returns:
            Instruction text to display to user
        """
        current_player = self.state.players[self.state.current_player_id]
        player_name = current_player.name

        # Discard phase
        if self.is_in_discard_phase():
            if self.state.current_player_id in self.state.pending_discards:
                to_discard = self.state.pending_discards[self.state.current_player_id]
                return f"{player_name}: Défaussez {to_discard} carte(s)"
            else:
                # Waiting for other player to discard
                other_player_id = next(iter(self.state.pending_discards.keys()))
                other_player = self.state.players[other_player_id]
                return f"En attente de {other_player.name} (défausse)..."

        # Robber move phase
        if self.is_in_robber_move_phase():
            return f"{player_name}: Déplacez le voleur"

        # Main phase - check if dice rolled
        if not self.state.dice_rolled_this_turn:
            return f"{player_name}: Lancez les dés"

        # Dice rolled, main actions available
        return f"{player_name}: Choisissez une action (Construire, Commercer, Fin de tour)"


__all__ = ["TurnController"]
