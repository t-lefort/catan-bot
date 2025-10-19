from dataclasses import replace

import pytest

from catan.app.event_bus import EventBus
from catan.app.events import ActionAppliedEvent, GameEndedEvent, GameStartedEvent
from catan.app.game_service import GameService
from catan.engine.actions import EndTurn, PlaceRoad, PlaceSettlement, RollDice
from catan.engine.state import GameState, SetupPhase


def test_event_bus_publish_and_unsubscribe() -> None:
    bus = EventBus()
    received: list[tuple[str, object]] = []

    unsubscribe_a = bus.subscribe(lambda event: received.append(("a", event)))
    unsubscribe_b = bus.subscribe(lambda event: received.append(("b", event)))

    bus.publish("hello")
    assert received == [("a", "hello"), ("b", "hello")]

    received.clear()
    unsubscribe_a()
    bus.publish("world")
    assert received == [("b", "world")]

    received.clear()
    unsubscribe_b()
    bus.publish("ignored")
    assert received == []


def test_game_service_emits_events_during_setup() -> None:
    bus = EventBus()
    events: list[object] = []
    bus.subscribe(events.append)

    service = GameService(event_bus=bus)
    state = service.start_new_game(player_names=["Alice", "Bob"], seed=1234)

    start_event = events[0]
    assert isinstance(start_event, GameStartedEvent)
    assert start_event.state.phase == SetupPhase.SETUP_ROUND_1
    assert state.phase == SetupPhase.SETUP_ROUND_1

    settlement_action = next(
        action for action in service.legal_actions() if isinstance(action, PlaceSettlement)
    )

    service.dispatch(settlement_action)

    assert len(events) == 2
    applied_event = events[-1]
    assert isinstance(applied_event, ActionAppliedEvent)
    assert applied_event.action == settlement_action
    assert applied_event.new_state.phase == SetupPhase.SETUP_ROUND_1

    next_actions = service.legal_actions()
    assert next_actions
    assert all(isinstance(action, PlaceRoad) for action in next_actions)


def test_game_service_rejects_illegal_action() -> None:
    service = GameService()
    service.start_new_game(player_names=["Alice", "Bob"], seed=1234)

    illegal_action = PlaceRoad(edge_id=0, free=False)

    with pytest.raises(ValueError):
        service.dispatch(illegal_action)


def test_game_service_emits_game_ended_event(monkeypatch: pytest.MonkeyPatch) -> None:
    bus = EventBus()
    events: list[object] = []
    bus.subscribe(events.append)

    service = GameService(event_bus=bus)
    service.start_new_game(player_names=["Alice", "Bob"], seed=123)

    action = next(
        candidate
        for candidate in service.legal_actions()
        if isinstance(candidate, PlaceSettlement)
    )

    original_apply = GameState.apply_action

    def _patched_apply(self: GameState, to_apply: PlaceSettlement) -> GameState:
        new_state = original_apply(self, to_apply)
        return replace(new_state, is_game_over=True, winner_id=0)

    monkeypatch.setattr(GameState, "apply_action", _patched_apply)

    service.dispatch(action)

    end_event = events[-1]
    assert isinstance(end_event, GameEndedEvent)
    assert end_event.winner_id == 0


def test_end_turn_is_legal_after_dice_roll() -> None:
    service = GameService()
    service.start_new_game(player_names=["Alice", "Bob"], seed=2025)

    # Compléter la phase de setup
    while service.state.phase != SetupPhase.PLAY:
        next_action = service.legal_actions()[0]
        service.dispatch(next_action)

    # Lancer les dés pour entrer dans la phase principale du tour
    roll_action = next(
        action for action in service.legal_actions() if isinstance(action, RollDice)
    )
    service.dispatch(roll_action)

    legal_after_roll = service.legal_actions()
    assert EndTurn() in legal_after_roll

    current_player = service.state.current_player_id
    service.dispatch(EndTurn())

    assert service.state.current_player_id != current_player
    assert not service.state.dice_rolled_this_turn
