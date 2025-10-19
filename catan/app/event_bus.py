"""Bus d'évènements minimaliste pour la couche application."""

from __future__ import annotations

from typing import Callable, List

Subscriber = Callable[[object], None]


class EventBus:
    """Publie des évènements aux observateurs enregistrés.

    L'implémentation est volontairement synchrone et simple : chaque publication
    appelle immédiatement les abonnés dans l'ordre d'enregistrement. Les
    callbacks peuvent renvoyer `None` ou lever une exception ; une exception
    interrompra la diffusion (c'est souhaité pour détecter les erreurs tôt).
    """

    __slots__ = ("_subscribers",)

    def __init__(self) -> None:
        self._subscribers: List[Subscriber] = []

    def subscribe(self, callback: Subscriber) -> Callable[[], None]:
        """Enregistre un abonné et retourne une fonction d'unsubscribe."""

        self._subscribers.append(callback)

        def unsubscribe() -> None:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                # L'abonné a déjà été retiré — ignorer pour idempotence.
                pass

        return unsubscribe

    def publish(self, event: object) -> None:
        """Diffuse l'évènement à tous les abonnés courants."""

        # Utiliser une copie au cas où des abonnés se désinscrivent pendant l'itération.
        for callback in list(self._subscribers):
            callback(event)
