"""Contrôleur pour le commerce GUI (GUI-005).

Responsabilités principales:
- Calculer les taux banques/ports accessibles au joueur actif
- Exposer les actions de commerce légales (banque, ports)
- Fournir des helpers pour proposer un échange joueur↔joueur et répondre
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pygame

from catan.app.game_service import GameService
from catan.engine.actions import (
    AcceptPlayerTrade,
    Action,
    DeclinePlayerTrade,
    OfferPlayerTrade,
    TradeBank,
)
from catan.engine.state import (
    GameState,
    PendingPlayerTrade,
    RESOURCE_TYPES,
    TurnSubPhase,
)


class TradeController:
    """Contrôleur GUI pour le commerce banque/port et joueur↔joueur."""

    def __init__(self, game_service: GameService, screen: pygame.Surface) -> None:
        self.game_service = game_service
        self.screen = screen
        self.state: GameState = game_service.state

        self._legal_actions_cache: Optional[List[Action]] = None

    # -- Gestion d'état -------------------------------------------------

    def refresh_state(self) -> None:
        """Synchronise le contrôleur avec l'état courant du GameService."""
        self.state = self.game_service.state
        self._legal_actions_cache = None

    def _get_legal_actions(self) -> List[Action]:
        if self._legal_actions_cache is None:
            self._legal_actions_cache = self.state.legal_actions()
        return self._legal_actions_cache

    # -- Commerce banque / ports ---------------------------------------

    def get_bank_trade_rates(self) -> Dict[str, int]:
        """Retourne le taux minimal disponible pour chaque ressource."""
        player = self.state.players[self.state.current_player_id]
        rates = {resource: 4 for resource in RESOURCE_TYPES}

        owned_vertices = set(player.settlements) | set(player.cities)
        if not owned_vertices:
            return rates

        has_any_port = False
        for port in self.state.board.ports:
            if not any(vertex in owned_vertices for vertex in port.vertices):
                continue
            if port.kind == "ANY":
                has_any_port = True
            else:
                rates[port.kind] = min(rates[port.kind], 2)

        if has_any_port:
            for resource in RESOURCE_TYPES:
                rates[resource] = min(rates[resource], 3)

        return rates

    def get_legal_bank_trades(self) -> List[TradeBank]:
        """Retourne la liste des échanges banque/port actuellement légaux."""
        return [
            action
            for action in self._get_legal_actions()
            if isinstance(action, TradeBank)
        ]

    def handle_bank_trade(
        self,
        give_resource: str,
        give_amount: int,
        receive_resource: str,
    ) -> bool:
        """Déclenche un échange banque/port si l'action est légale."""
        if give_amount <= 0:
            return False

        target_give = {give_resource: give_amount}
        target_receive_key = receive_resource

        for action in self.get_legal_bank_trades():
            if action.give != target_give:
                continue
            if len(action.receive) != 1:
                continue
            if target_receive_key not in action.receive:
                continue
            self.game_service.dispatch(action)
            self.refresh_state()
            return True

        return False

    # -- Commerce joueur ↔ joueur --------------------------------------

    def get_legal_player_trade_offers(self) -> List[OfferPlayerTrade]:
        """Retourne les offres joueur↔joueur légales pour le joueur actif."""
        return [
            action
            for action in self._get_legal_actions()
            if isinstance(action, OfferPlayerTrade)
        ]

    def handle_offer_player_trade(
        self,
        give_resource: str,
        receive_resource: str,
        *,
        give_amount: int = 1,
        receive_amount: int = 1,
    ) -> bool:
        """Propose un échange joueur↔joueur si légal."""
        if give_amount <= 0 or receive_amount <= 0:
            return False
        target_give = {give_resource: give_amount}
        target_receive = {receive_resource: receive_amount}

        for action in self.get_legal_player_trade_offers():
            if action.give == target_give and action.receive == target_receive:
                self.game_service.dispatch(action)
                self.refresh_state()
                return True
        return False

    def get_pending_trade(self) -> Optional[PendingPlayerTrade]:
        """Retourne l'échange joueur↔joueur en attente, le cas échéant."""
        return self.state.pending_player_trade

    def is_trade_response_pending(self) -> bool:
        """Indique si un échange attend une réponse de l'adversaire."""
        return self.state.turn_subphase == TurnSubPhase.TRADE_RESPONSE

    def can_accept_trade(self) -> bool:
        """Vérifie si le joueur courant peut accepter l'échange en attente."""
        pending = self.state.pending_player_trade
        if pending is None:
            return False
        return (
            self.is_trade_response_pending()
            and self.state.current_player_id == pending.responder_id
        )

    def can_decline_trade(self) -> bool:
        """Vérifie si le joueur courant peut refuser l'échange en attente."""
        return self.is_trade_response_pending() and self.state.pending_player_trade is not None

    def handle_accept_trade(self) -> bool:
        """Accepte l'échange en attente si possible."""
        if not self.can_accept_trade():
            return False
        self.game_service.dispatch(AcceptPlayerTrade())
        self.refresh_state()
        return True

    def handle_decline_trade(self) -> bool:
        """Refuse l'échange en attente si possible."""
        if not self.can_decline_trade():
            return False
        self.game_service.dispatch(DeclinePlayerTrade())
        self.refresh_state()
        return True


__all__ = ["TradeController"]
