"""Tests unitaires pour TradeController (GUI-005).

Ces tests couvrent:
- Calcul des taux de commerce banque/ports selon les ports possédés
- Filtrage et exécution des échanges banque/ports
- Gestion des offres joueur↔joueur (création, acceptation, refus)
- Accès aux données d'échange en attente pour l'UI
"""

from __future__ import annotations

import os
from typing import Dict

import pygame
import pytest

from catan.app.game_service import GameService
from catan.engine.actions import TradeBank
from catan.engine.state import (
    GameState,
    PendingPlayerTrade,
    RESOURCE_TYPES,
    SetupPhase,
    TurnSubPhase,
)


def _make_trade_ready_state() -> GameState:
    """Create a PLAY-phase state ready for trading interactions."""
    state = GameState.new_1v1_game()
    state.phase = SetupPhase.PLAY
    state.turn_subphase = TurnSubPhase.MAIN
    state.turn_number = 1
    state.current_player_id = 0
    state.dice_rolled_this_turn = True
    state.pending_player_trade = None
    return state


@pytest.fixture
def pygame_screen():
    """Initialise pygame en mode headless."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    yield screen
    pygame.quit()


@pytest.fixture
def trade_controller(pygame_screen):
    """Retourne un TradeController prêt pour les tests."""
    from catan.gui.trade_controller import TradeController

    service = GameService()
    service._state = _make_trade_ready_state()
    controller = TradeController(service, pygame_screen)
    return controller, service


def test_bank_trade_rates_without_ports(trade_controller):
    """Sans port, tous les taux doivent rester à 4:1."""
    controller, service = trade_controller
    rates = controller.get_bank_trade_rates()
    assert rates == {resource: 4 for resource in RESOURCE_TYPES}


def test_bank_trade_rates_with_any_port(trade_controller):
    """Un port ANY doit ramener les taux à 3:1 pour toutes les ressources."""
    controller, service = trade_controller
    state = service.state

    any_port = next(port for port in state.board.ports if port.kind == "ANY")
    state.players[0].settlements.append(any_port.vertices[0])
    controller.refresh_state()

    rates = controller.get_bank_trade_rates()
    assert rates == {resource: 3 for resource in RESOURCE_TYPES}


def test_bank_trade_rates_with_specific_port(trade_controller):
    """Un port spécifique doit donner un taux 2:1 uniquement pour sa ressource."""
    controller, service = trade_controller
    state = service.state

    wool_port = next(port for port in state.board.ports if port.kind == "WOOL")
    state.players[0].settlements.append(wool_port.vertices[0])
    controller.refresh_state()

    rates = controller.get_bank_trade_rates()
    assert rates["WOOL"] == 2
    for resource in RESOURCE_TYPES:
        expected = 2 if resource == "WOOL" else 4
        assert rates[resource] == expected


def test_get_legal_bank_trades_matches_state(trade_controller):
    """Les actions TradeBank retournées doivent correspondre aux actions légales."""
    controller, service = trade_controller
    state = service.state
    state.players[0].resources.update({"BRICK": 4})
    controller.refresh_state()

    legal_actions = controller.get_legal_bank_trades()
    state_actions = [action for action in state.legal_actions() if isinstance(action, TradeBank)]

    assert len(legal_actions) == len(state_actions)
    for action in state_actions:
        assert any(candidate == action for candidate in legal_actions)
    assert any(
        action.give == {"BRICK": 4} and action.receive == {"WOOL": 1}
        for action in legal_actions
    )


def test_handle_bank_trade_success(trade_controller):
    """Exécuter un échange banque 4:1 valide doit mettre à jour l'état."""
    controller, service = trade_controller
    state = service.state

    state.players[0].resources.update({"BRICK": 4})
    state.bank_resources["WOOL"] = 10
    controller.refresh_state()

    assert controller.handle_bank_trade("BRICK", 4, "WOOL")
    updated_state = service.state
    player_resources = updated_state.players[0].resources

    assert player_resources["BRICK"] == 0
    assert player_resources["WOOL"] == 1
    assert updated_state.bank_resources["BRICK"] == 23  # 19 + 4
    assert updated_state.bank_resources["WOOL"] == 9


def test_handle_bank_trade_invalid_amount(trade_controller):
    """Un échange illégal (ex: 3:1 sans port) doit être refusé."""
    controller, service = trade_controller
    state = service.state

    state.players[0].resources.update({"BRICK": 3})
    before_resources: Dict[str, int] = dict(state.players[0].resources)
    controller.refresh_state()

    assert not controller.handle_bank_trade("BRICK", 3, "WOOL")
    assert state.players[0].resources == before_resources


def test_offer_player_trade_creates_pending_trade(trade_controller):
    """Une offre joueur↔joueur valide doit créer un échange en attente."""
    controller, service = trade_controller
    state = service.state

    state.players[0].resources.update({"BRICK": 1})
    state.players[1].resources.update({"WOOL": 1})
    controller.refresh_state()

    assert controller.handle_offer_player_trade("BRICK", "WOOL")
    pending = service.state.pending_player_trade
    assert isinstance(pending, PendingPlayerTrade)
    assert pending.give == {"BRICK": 1}
    assert pending.receive == {"WOOL": 1}
    assert service.state.turn_subphase == TurnSubPhase.TRADE_RESPONSE
    assert service.state.current_player_id == 1
    assert controller.get_pending_trade() == pending


def test_get_legal_player_trade_offers_filters_resources(trade_controller):
    """Les offres légales doivent dépendre des ressources réellement possédées."""
    controller, service = trade_controller
    state = service.state

    state.players[0].resources.update({"BRICK": 1})
    state.players[1].resources.update({"WOOL": 1})
    controller.refresh_state()

    offers = controller.get_legal_player_trade_offers()
    assert any(
        offer.give == {"BRICK": 1} and offer.receive == {"WOOL": 1}
        for offer in offers
    )
    assert not any(
        offer.give == {"WOOL": 1} and offer.receive == {"BRICK": 1}
        for offer in offers
    )


def test_accept_player_trade_transfers_resources(trade_controller):
    """Accepter un échange doit transférer les ressources et rendre la main au proposeur."""
    controller, service = trade_controller
    state = service.state

    state.players[0].resources.update({"BRICK": 2, "WOOL": 0})
    state.players[1].resources.update({"BRICK": 0, "WOOL": 2})
    controller.refresh_state()

    assert controller.handle_offer_player_trade("BRICK", "WOOL")
    controller.refresh_state()

    assert controller.handle_accept_trade()
    updated_state = service.state
    assert updated_state.turn_subphase == TurnSubPhase.MAIN
    assert updated_state.current_player_id == 0
    assert updated_state.pending_player_trade is None
    assert updated_state.players[0].resources["BRICK"] == 1
    assert updated_state.players[0].resources["WOOL"] == 1
    assert updated_state.players[1].resources["BRICK"] == 1
    assert updated_state.players[1].resources["WOOL"] == 1


def test_decline_player_trade_returns_to_main_phase(trade_controller):
    """Refuser un échange laisse les ressources intactes et annule l'échange en attente."""
    controller, service = trade_controller
    state = service.state

    state.players[0].resources.update({"BRICK": 1})
    state.players[1].resources.update({"WOOL": 1})
    controller.refresh_state()

    assert controller.handle_offer_player_trade("BRICK", "WOOL")
    controller.refresh_state()

    assert controller.handle_decline_trade()
    updated_state = service.state
    assert updated_state.turn_subphase == TurnSubPhase.MAIN
    assert updated_state.current_player_id == 0
    assert updated_state.pending_player_trade is None
    assert updated_state.players[0].resources["BRICK"] == 1
    assert updated_state.players[1].resources["WOOL"] == 1
