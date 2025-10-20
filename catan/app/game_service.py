"""Service d'orchestration pour une partie Catane 1v1."""

from __future__ import annotations

from typing import Iterable, List, Mapping, Sequence

from catan.app.event_bus import EventBus
from catan.app.events import ActionAppliedEvent, GameEndedEvent, GameStartedEvent
from catan.engine.actions import Action
from catan.engine.state import GameState


class GameService:
    """Wrappe `GameState` et publie les évènements nécessaires à la GUI/sim."""

    def __init__(self, *, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus or EventBus()
        self._state: GameState | None = None

    @property
    def event_bus(self) -> EventBus:
        """Retourne le bus d'évènements utilisé par le service."""

        return self._event_bus

    @property
    def state(self) -> GameState:
        """État courant de la partie (erreur si aucune partie lancée)."""

        if self._state is None:
            raise RuntimeError("Aucune partie initialisée. Utiliser start_new_game().")
        return self._state

    def start_new_game(
        self,
        player_names: Sequence[str] | None = None,
        *,
        seed: int | None = None,
        dev_deck: Iterable[str] | None = None,
        bank_resources: Mapping[str, int] | None = None,
        random_board: bool = False,
    ) -> GameState:
        """Initialise une nouvelle partie et publie l'évènement associé."""

        state = GameState.new_1v1_game(
            player_names=list(player_names) if player_names is not None else None,
            seed=seed,
            dev_deck=list(dev_deck) if dev_deck is not None else None,
            bank_resources=dict(bank_resources) if bank_resources is not None else None,
            random_board=random_board,
        )
        self._state = state
        self._event_bus.publish(GameStartedEvent(state=state))
        return state

    def legal_actions(self) -> List[Action]:
        """Retourne les actions légales pour l'état courant."""

        return self.state.legal_actions()

    def dispatch(self, action: Action) -> GameState:
        """Valide et applique une action, puis notifie les observateurs."""

        current_state = self.state
        if not current_state.is_action_legal(action):
            raise ValueError(f"Action illégale: {action}")

        new_state = current_state.apply_action(action)
        self._state = new_state

        self._event_bus.publish(
            ActionAppliedEvent(
                action=action,
                previous_state=current_state,
                new_state=new_state,
            )
        )

        if new_state.is_game_over:
            self._event_bus.publish(
                GameEndedEvent(state=new_state, winner_id=new_state.winner_id)
            )

        return new_state
