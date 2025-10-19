"""Orchestrateur principal de la GUI Catane 1v1 (GUI-011).

Ce module regroupe les différents contrôleurs (setup, tour, construction,
commerce, HUD) et fournit un modèle testable indépendant de la boucle
pygame. Il expose:
- un objet `CatanH2HApp` coordonnant GameService et contrôleurs,
- un état d'interface (`UIState`) synthétisant le mode courant, les
  surbrillances à afficher et l'activation des actions GUI.

L'objectif est de permettre à la fois:
- l'écriture de tests headless (cf. tests/test_gui_app.py),
- la consommation par une future boucle d'évènements pygame pour
  permettre une partie manuelle complète.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set

import pygame

from catan.app.game_service import GameService
from catan.engine.actions import EndTurn
from catan.engine.state import GameState, SetupPhase, TurnSubPhase
from catan.gui.construction_controller import ConstructionController
from catan.gui.development_controller import DevelopmentController
from catan.gui.hud_controller import HUDController
from catan.gui.renderer import BoardRenderer
from catan.gui.setup_controller import SetupController
from catan.gui.trade_controller import TradeController
from catan.gui.turn_controller import TurnController

__all__ = ["ButtonState", "UIState", "CatanH2HApp"]


@dataclass(frozen=True)
class ButtonState:
    """Représente l'état d'un bouton/action dans l'interface."""

    label: str
    enabled: bool


@dataclass(frozen=True)
class UIState:
    """Données agrégées pour la couche de présentation GUI."""

    mode: str
    phase: SetupPhase
    instructions: str
    highlight_vertices: Set[int]
    highlight_edges: Set[int]
    highlight_tiles: Set[int]
    buttons: Dict[str, ButtonState]


class CatanH2HApp:
    """Orchestrateur principal de la GUI H2H.

    Cette classe ne gère pas la boucle pygame directement mais fournit
    les opérations nécessaires à l'UI:
    - démarrer une partie,
    - déclencher des actions (lancer de dés, terminer tour, sélectionner
      un mode de construction),
    - gérer les clics sur le plateau (sommets/arêtes/hex),
    - exposer un état synthétique prêt à rendre.
    """

    def __init__(
        self,
        *,
        game_service: Optional[GameService] = None,
        screen: Optional[pygame.Surface] = None,
    ) -> None:
        self.game_service = game_service or GameService()
        self.screen = screen

        self._board_renderer: Optional[BoardRenderer] = None

        self.setup_controller: Optional[SetupController] = None
        self.turn_controller: Optional[TurnController] = None
        self.construction_controller: Optional[ConstructionController] = None
        self.development_controller: Optional[DevelopmentController] = None
        self.trade_controller: Optional[TradeController] = None
        self.hud_controller: Optional[HUDController] = None

        self.mode: str = "setup"

    # ------------------------------------------------------------------
    # Initialisation & synchronisation
    # ------------------------------------------------------------------

    def start_new_game(
        self,
        *,
        player_names: Optional[list[str]] = None,
        seed: Optional[int] = None,
    ) -> None:
        """Initialise une nouvelle partie et (ré)instancie les contrôleurs."""

        state = self.game_service.start_new_game(
            player_names=player_names or ["Bleu", "Orange"],
            seed=seed,
        )

        if self.screen is None:
            # Crée une surface si non fournie (utile hors tests)
            self.screen = pygame.display.set_mode((1280, 720))

        board = state.board
        self._board_renderer = BoardRenderer(self.screen, board)

        # Instancie les contrôleurs dépendant du GameService
        self.setup_controller = SetupController(self.game_service, self.screen)
        self.turn_controller = TurnController(self.game_service, self.screen)
        self.construction_controller = ConstructionController(self.game_service, self.screen)
        self.development_controller = DevelopmentController(self.game_service, self.screen)
        self.trade_controller = TradeController(self.game_service, self.screen)
        self.hud_controller = HUDController(self.game_service, self.screen)

        self.mode = "setup"
        self.refresh_state()

    @property
    def state(self) -> GameState:
        """Accès direct à l'état courant de la partie."""

        return self.game_service.state

    @property
    def renderer(self) -> BoardRenderer:
        """Retourne le renderer pygame associé (initialisé après start)."""

        if self._board_renderer is None:
            raise RuntimeError("BoardRenderer indisponible tant que la partie n'est pas démarrée")
        return self._board_renderer

    def refresh_state(self) -> None:
        """Resynchronise les contrôleurs avec l'état courant."""

        if self.setup_controller is None:
            return

        self.setup_controller.refresh_state()
        assert self.turn_controller is not None
        self.turn_controller.refresh_state()
        assert self.construction_controller is not None
        self.construction_controller.refresh_state()
        assert self.development_controller is not None
        self.development_controller.refresh_state()
        assert self.trade_controller is not None
        self.trade_controller.refresh_state()
        assert self.hud_controller is not None
        self.hud_controller.refresh_state()

        if self.state.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2):
            self.mode = "setup"
            return

        # En phase PLAY — ajuster le mode selon les sous-phases forcées
        assert self.turn_controller is not None
        if self.turn_controller.is_in_robber_move_phase():
            self.mode = "move_robber"
            return

        if self.mode == "setup":
            # Transition automatique vers le mode idle une fois le setup terminé
            self.mode = "idle"
        elif self.mode == "move_robber" and not self.turn_controller.is_in_robber_move_phase():
            self.mode = "idle"

    # ------------------------------------------------------------------
    # Gestion des actions bouton/menu
    # ------------------------------------------------------------------

    def trigger_action(self, action: str, **kwargs) -> bool:
        """Déclenche une action de haut niveau (bouton panneau)."""

        if self.setup_controller is None:
            raise RuntimeError("App non initialisée: start_new_game() requis")

        if action == "roll_dice":
            assert self.turn_controller is not None
            result = self.turn_controller.handle_roll_dice(
                forced_value=kwargs.get("forced_value"),
                forced_dice=kwargs.get("forced_dice"),
            )
            if result is None:
                return False
            self.refresh_state()
            return True

        if action == "end_turn":
            end_turn = EndTurn()
            if end_turn not in self.state.legal_actions():
                return False
            self.game_service.dispatch(end_turn)
            self.refresh_state()
            return True

        if action == "select_build_road":
            return self._enter_build_mode("build_road")

        if action == "select_build_settlement":
            return self._enter_build_mode("build_settlement")

        if action == "select_build_city":
            return self._enter_build_mode("build_city")

        if action == "cancel":
            self.mode = "idle" if self.state.phase == SetupPhase.PLAY else "setup"
            return True

        return False

    def _enter_build_mode(self, mode: str) -> bool:
        """Active un mode de construction si des actions sont possibles."""

        if self.state.phase != SetupPhase.PLAY:
            return False

        assert self.construction_controller is not None

        if mode == "build_road":
            legal = self.construction_controller.get_legal_road_positions()
            allowed = legal and self.construction_controller.can_afford_road()
        elif mode == "build_settlement":
            legal = self.construction_controller.get_legal_settlement_positions()
            allowed = legal and self.construction_controller.can_afford_settlement()
        else:  # build_city
            legal = self.construction_controller.get_legal_city_positions()
            allowed = legal and self.construction_controller.can_afford_city()

        if not allowed:
            return False

        self.mode = mode
        return True

    # ------------------------------------------------------------------
    # Gestion des clics plateau (sommets/arêtes/hex)
    # ------------------------------------------------------------------

    def handle_board_vertex_click(self, vertex_id: int) -> bool:
        if self.setup_controller is None:
            raise RuntimeError("App non initialisée")

        if self.mode == "setup":
            result = self.setup_controller.handle_vertex_click(vertex_id)
            if result:
                self.refresh_state()
            return result

        if self.mode == "build_settlement":
            assert self.construction_controller is not None
            result = self.construction_controller.handle_build_settlement(vertex_id)
            if result:
                self.mode = "idle"
                self.refresh_state()
            return result

        if self.mode == "build_city":
            assert self.construction_controller is not None
            result = self.construction_controller.handle_build_city(vertex_id)
            if result:
                self.mode = "idle"
                self.refresh_state()
            return result

        return False

    def handle_board_edge_click(self, edge_id: int) -> bool:
        if self.setup_controller is None:
            raise RuntimeError("App non initialisée")

        if self.mode == "setup":
            result = self.setup_controller.handle_edge_click(edge_id)
            if result:
                self.refresh_state()
            return result

        if self.mode == "build_road":
            assert self.construction_controller is not None
            result = self.construction_controller.handle_build_road(edge_id)
            if result:
                self.mode = "idle"
                self.refresh_state()
            return result

        return False

    def handle_board_tile_click(self, tile_id: int, *, steal_from: Optional[int] = None) -> bool:
        if self.mode != "move_robber":
            return False

        assert self.turn_controller is not None
        legal_tiles = self.turn_controller.get_legal_robber_tiles()
        if tile_id not in legal_tiles:
            return False

        result = self.turn_controller.handle_robber_move(tile_id, steal_from=steal_from)
        if result:
            self.mode = "idle"
            self.refresh_state()
        return result

    # ------------------------------------------------------------------
    # Construction de l'état UI
    # ------------------------------------------------------------------

    def get_ui_state(self) -> UIState:
        if self.setup_controller is None:
            raise RuntimeError("App non initialisée")

        self.refresh_state()

        highlight_vertices: Set[int] = set()
        highlight_edges: Set[int] = set()
        highlight_tiles: Set[int] = set()

        instructions = self._build_instructions()

        if self.mode == "setup":
            highlight_vertices = set(self.setup_controller.get_legal_settlement_vertices())
            highlight_edges = set(self.setup_controller.get_legal_road_edges())
        elif self.mode == "build_road":
            assert self.construction_controller is not None
            highlight_edges = set(self.construction_controller.get_legal_road_positions())
        elif self.mode == "build_settlement":
            assert self.construction_controller is not None
            highlight_vertices = set(self.construction_controller.get_legal_settlement_positions())
        elif self.mode == "build_city":
            assert self.construction_controller is not None
            highlight_vertices = set(self.construction_controller.get_legal_city_positions())
        elif self.mode == "move_robber":
            assert self.turn_controller is not None
            highlight_tiles = set(self.turn_controller.get_legal_robber_tiles())

        buttons = self._build_buttons()

        return UIState(
            mode=self.mode,
            phase=self.state.phase,
            instructions=instructions,
            highlight_vertices=highlight_vertices,
            highlight_edges=highlight_edges,
            highlight_tiles=highlight_tiles,
            buttons=buttons,
        )

    def _build_instructions(self) -> str:
        assert self.turn_controller is not None

        if self.mode == "setup":
            assert self.setup_controller is not None
            return self.setup_controller.get_instructions()

        current_player = self.state.players[self.state.current_player_id]

        if self.mode == "build_road":
            return f"{current_player.name} — Sélectionnez une arête pour construire une route"
        if self.mode == "build_settlement":
            return f"{current_player.name} — Sélectionnez un sommet pour construire une colonie"
        if self.mode == "build_city":
            return f"{current_player.name} — Sélectionnez une ville à améliorer"
        if self.mode == "move_robber":
            return f"{current_player.name} — Déplacez le voleur"

        if not self.state.dice_rolled_this_turn:
            return f"{current_player.name} — Lancez les dés"

        return f"{current_player.name} — Choisissez une action"

    def _build_buttons(self) -> Dict[str, ButtonState]:
        assert self.turn_controller is not None
        assert self.construction_controller is not None

        buttons: Dict[str, ButtonState] = {}

        can_roll = (
            self.state.phase == SetupPhase.PLAY
            and self.turn_controller.can_roll_dice()
            and self.mode not in ("build_road", "build_settlement", "build_city", "move_robber")
        )

        buttons["roll_dice"] = ButtonState("Lancer les dés", can_roll)

        legal_actions = self.state.legal_actions()
        can_end_turn = EndTurn() in legal_actions and self.mode not in ("setup", "move_robber")
        buttons["end_turn"] = ButtonState("Terminer le tour", can_end_turn)

        can_build_road = (
            self.mode == "idle"
            and self.construction_controller.can_afford_road()
            and bool(self.construction_controller.get_legal_road_positions())
        )
        buttons["select_build_road"] = ButtonState("Construire une route", can_build_road)

        can_build_settlement = (
            self.mode == "idle"
            and self.construction_controller.can_afford_settlement()
            and bool(self.construction_controller.get_legal_settlement_positions())
        )
        buttons["select_build_settlement"] = ButtonState("Construire une colonie", can_build_settlement)

        can_build_city = (
            self.mode == "idle"
            and self.construction_controller.can_afford_city()
            and bool(self.construction_controller.get_legal_city_positions())
        )
        buttons["select_build_city"] = ButtonState("Construire une ville", can_build_city)

        # Bouton d'annulation actif lorsqu'un mode temporaire est enclenché
        buttons["cancel"] = ButtonState(
            "Annuler",
            self.mode in {"build_road", "build_settlement", "build_city", "move_robber"},
        )

        return buttons
