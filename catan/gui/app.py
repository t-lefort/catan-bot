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
from typing import Dict, Optional, Set, Tuple

import pygame

from catan.app.game_service import GameService
from catan.engine.actions import BuyDevelopment, EndTurn
from catan.engine.state import GameState, SetupPhase, TurnSubPhase, RESOURCE_TYPES
from catan.engine.rules import DISCARD_THRESHOLD
from catan.gui.construction_controller import ConstructionController
from catan.gui.development_controller import DevelopmentController
from catan.gui.hud_controller import HUDController
from catan.gui.hud_controller import PlayerPanel
from catan.gui.renderer import BoardRenderer
from catan.gui.setup_controller import SetupController
from catan.gui.trade_controller import TradeController
from catan.gui.turn_controller import TurnController

__all__ = ["ButtonState", "UIState", "DiscardPrompt", "BankTradePrompt", "YearOfPlentyPrompt", "CatanH2HApp"]


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
    last_dice_roll: Optional[int]
    dice_rolled_this_turn: bool
    player_panels: Tuple[PlayerPanel, ...]
    discard_prompt: Optional["DiscardPrompt"]
    bank_trade_prompt: Optional["BankTradePrompt"]
    year_of_plenty_prompt: Optional["YearOfPlentyPrompt"]
    buttons: Dict[str, ButtonState]


@dataclass(frozen=True)
class DiscardPrompt:
    """Informations pour le panneau de défausse."""

    player_id: int
    player_name: str
    required: int
    remaining: int
    selection: Dict[str, int]
    hand: Dict[str, int]
    can_confirm: bool
    resource_order: Tuple[str, ...]


@dataclass(frozen=True)
class BankTradePrompt:
    """Informations pour le panneau d'échange banque."""

    player_name: str
    give_selection: Dict[str, int]
    receive_selection: str | None
    hand: Dict[str, int]
    rates: Dict[str, int]
    can_confirm: bool
    resource_order: Tuple[str, ...]


@dataclass(frozen=True)
class YearOfPlentyPrompt:
    """Informations pour le panneau Year of Plenty."""

    player_name: str
    selection: Dict[str, int]
    required: int
    remaining: int
    can_confirm: bool
    resource_order: Tuple[str, ...]


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
        self._discard_selection: Dict[str, int] = {}
        self._discard_required: int = 0
        self._discard_player_id: Optional[int] = None
        self._bank_trade_give: Dict[str, int] = {}
        self._bank_trade_receive: Optional[str] = None
        self._road_building_edges: list[int] = []
        self._year_of_plenty_selection: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Initialisation & synchronisation
    # ------------------------------------------------------------------

    def start_new_game(
        self,
        *,
        player_names: Optional[list[str]] = None,
        seed: Optional[int] = None,
        random_board: bool = False,
    ) -> None:
        """Initialise une nouvelle partie et (ré)instancie les contrôleurs."""

        state = self.game_service.start_new_game(
            player_names=player_names or ["Bleu", "Orange"],
            seed=seed,
            random_board=random_board,
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
        self._discard_selection = {}
        self._discard_required = 0
        self._discard_player_id = None
        self._bank_trade_give = {}
        self._bank_trade_receive = None
        self._road_building_edges = []
        self._year_of_plenty_selection = {}
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
        if self._board_renderer is not None:
            self._board_renderer.update_board(self.state.board)

        if self.state.phase in (SetupPhase.SETUP_ROUND_1, SetupPhase.SETUP_ROUND_2):
            self.mode = "setup"
            return

        assert self.turn_controller is not None

        if self.turn_controller.is_in_discard_phase():
            requirements = self.turn_controller.get_discard_requirements()
            current_id = self.state.current_player_id
            player = self.state.players[current_id]
            calc_required = max(sum(player.resources.values()) - DISCARD_THRESHOLD, 0)
            required = requirements.get(current_id, 0)
            effective_required = max(required, calc_required)
            if effective_required > 0:
                if (
                    self._discard_player_id != current_id
                    or self._discard_required != effective_required
                ):
                    self._discard_selection = {}
                self._discard_player_id = current_id
                self._discard_required = effective_required
                self.mode = "discard"
            else:
                self.mode = "discard_wait"
                self._discard_selection = {}
                self._discard_player_id = None
                self._discard_required = 0
            return

        # Reset discard state when leaving the phase
        self._discard_selection = {}
        self._discard_player_id = None
        self._discard_required = 0

        # En phase PLAY — ajuster le mode selon les sous-phases forcées
        if self.turn_controller.is_in_robber_move_phase():
            self.mode = "move_robber"
            return

        # Préserver les modes interactifs utilisateur
        if self.mode in {"bank_trade", "year_of_plenty", "select_road_building", "build_road", "build_settlement", "build_city"}:
            return

        if self.mode == "setup":
            # Transition automatique vers le mode idle une fois le setup terminé
            self.mode = "idle"
        elif self.mode in {"move_robber", "discard", "discard_wait"} and not self.turn_controller.is_in_robber_move_phase():
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

        if action == "buy_development":
            assert self.construction_controller is not None
            if not self.construction_controller.handle_buy_development():
                return False
            self.refresh_state()
            return True

        if action == "cancel":
            if self.mode == "discard":
                return self.reset_discard_selection()
            if self.mode == "bank_trade":
                self._bank_trade_give = {}
                self._bank_trade_receive = None
                self.mode = "idle"
                return True
            if self.mode == "year_of_plenty":
                self._year_of_plenty_selection = {}
                self.mode = "idle"
                return True
            if self.mode == "select_road_building":
                self._road_building_edges = []
                self.mode = "idle"
                return True
            self.mode = "idle" if self.state.phase == SetupPhase.PLAY else "setup"
            return True

        # Actions pour jouer les cartes de développement
        if action == "play_knight":
            assert self.development_controller is not None
            if not self.development_controller.handle_play_knight():
                return False
            self.refresh_state()
            return True

        if action == "play_year_of_plenty":
            # Ouvrir l'interface de sélection pour Year of Plenty
            assert self.development_controller is not None
            options = self.development_controller.get_legal_year_of_plenty_options()
            if not options:
                return False
            self.mode = "year_of_plenty"
            self._year_of_plenty_selection = {}
            return True

        if action == "play_monopoly":
            # Pour Monopoly, on doit demander à l'utilisateur quelle ressource cibler
            assert self.development_controller is not None
            resources = self.development_controller.get_legal_monopoly_resources()
            if not resources:
                return False
            selected_resource = kwargs.get("resource")
            if selected_resource is None:
                selected_resource = resources[0]
            if selected_resource not in resources:
                return False
            if not self.development_controller.handle_play_monopoly(selected_resource):
                return False
            self.refresh_state()
            return True

        if action == "play_road_building":
            # Passer en mode de sélection interactive pour Road Building
            assert self.development_controller is not None
            targets = self.development_controller.get_legal_road_building_targets()
            if not targets:
                return False
            self.mode = "select_road_building"
            self._road_building_edges = []
            return True

        if action == "bank_trade":
            # Ouvrir l'interface de sélection d'échange banque
            assert self.trade_controller is not None
            if not self.trade_controller.get_legal_bank_trades():
                return False
            self.mode = "bank_trade"
            self._bank_trade_give = {}
            self._bank_trade_receive = None
            return True

        if action == "player_trade":
            # Pour le commerce joueur-joueur, proposer le premier échange disponible
            assert self.trade_controller is not None
            legal_offers = self.trade_controller.get_legal_player_trade_offers()
            if not legal_offers:
                return False
            # Proposer le premier échange légal
            offer = legal_offers[0]
            give_resource = list(offer.give.keys())[0]
            receive_resource = list(offer.receive.keys())[0]
            if not self.trade_controller.handle_offer_player_trade(
                give_resource, receive_resource,
                give_amount=offer.give[give_resource],
                receive_amount=offer.receive[receive_resource]
            ):
                return False
            self.refresh_state()
            return True

        if action == "accept_trade":
            assert self.trade_controller is not None
            if not self.trade_controller.handle_accept_trade():
                return False
            self.refresh_state()
            return True

        if action == "decline_trade":
            assert self.trade_controller is not None
            if not self.trade_controller.handle_decline_trade():
                return False
            self.refresh_state()
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

        if self.mode == "select_road_building":
            # Sélection des routes pour la carte Road Building
            assert self.development_controller is not None

            # Vérifier si cette arête est légale pour la construction
            if edge_id in self._road_building_edges:
                # Déjà sélectionnée, la retirer
                self._road_building_edges.remove(edge_id)
                return True

            if len(self._road_building_edges) >= 2:
                # Déjà 2 routes sélectionnées
                return False

            # Ajouter l'arête à la sélection
            self._road_building_edges.append(edge_id)

            # Si deux routes sont sélectionnées, confirmer
            if len(self._road_building_edges) == 2:
                # Vérifier que la combinaison est légale
                targets = self.development_controller.get_legal_road_building_targets()
                edges_tuple = tuple(sorted(self._road_building_edges))

                if edges_tuple in targets:
                    # Jouer la carte
                    if self.development_controller.handle_play_road_building(self._road_building_edges):
                        self._road_building_edges = []
                        self.mode = "idle"
                        self.refresh_state()
                        return True
                else:
                    # Combinaison invalide, réinitialiser
                    self._road_building_edges = []
                    return False

            return True

        return False

    def handle_board_tile_click(self, tile_id: int, *, steal_from: Optional[int] = None) -> bool:
        if self.mode != "move_robber":
            return False

        assert self.turn_controller is not None
        legal_tiles = self.turn_controller.get_legal_robber_tiles()
        if tile_id not in legal_tiles:
            return False

        if steal_from is None:
            stealable = self.turn_controller.get_stealable_players(tile_id)
            if len(stealable) == 1:
                steal_from = next(iter(stealable))

        result = self.turn_controller.handle_robber_move(tile_id, steal_from=steal_from)
        if result:
            self.mode = "idle"
            self.refresh_state()
        return result

    # ------------------------------------------------------------------
    # Gestion Year of Plenty
    # ------------------------------------------------------------------

    def adjust_year_of_plenty_selection(self, resource: str, delta: int) -> bool:
        """Ajuste la sélection de ressources pour Year of Plenty."""
        if self.mode != "year_of_plenty":
            return False
        if resource not in RESOURCE_TYPES:
            return False
        if delta == 0:
            return False

        current_amount = self._year_of_plenty_selection.get(resource, 0)
        total_selected = sum(self._year_of_plenty_selection.values())
        required = 2  # Year of Plenty donne toujours 2 ressources

        if delta > 0:
            allowed = min(delta, required - total_selected)
            if allowed <= 0:
                return False
            self._year_of_plenty_selection[resource] = current_amount + allowed
            return True

        removal = min(-delta, current_amount)
        if removal <= 0:
            return False
        new_value = current_amount - removal
        if new_value > 0:
            self._year_of_plenty_selection[resource] = new_value
        else:
            self._year_of_plenty_selection.pop(resource, None)
        return True

    def reset_year_of_plenty_selection(self) -> bool:
        """Réinitialise la sélection Year of Plenty."""
        if self.mode != "year_of_plenty":
            return False
        self._year_of_plenty_selection = {}
        return True

    def confirm_year_of_plenty_selection(self) -> bool:
        """Confirme et exécute Year of Plenty avec la sélection."""
        if self.mode != "year_of_plenty":
            return False
        if sum(self._year_of_plenty_selection.values()) != 2:
            return False

        assert self.development_controller is not None

        # Convertir la sélection au format attendu
        selection = dict(self._year_of_plenty_selection)
        success = self.development_controller.handle_play_year_of_plenty(selection)

        if success:
            self._year_of_plenty_selection = {}
            self.mode = "idle"
            self.refresh_state()

        return success

    # ------------------------------------------------------------------
    # Gestion de l'échange banque
    # ------------------------------------------------------------------

    def adjust_bank_trade_give(self, resource: str, delta: int) -> bool:
        """Ajuste la sélection de ressources à donner pour l'échange banque."""
        if self.mode != "bank_trade":
            return False
        if resource not in RESOURCE_TYPES:
            return False
        if delta == 0:
            return False

        player = self.state.players[self.state.current_player_id]
        current_amount = self._bank_trade_give.get(resource, 0)
        available = player.resources.get(resource, 0)

        if delta > 0:
            allowed = min(delta, available - current_amount)
            if allowed <= 0:
                return False
            self._bank_trade_give[resource] = current_amount + allowed
            return True

        removal = min(-delta, current_amount)
        if removal <= 0:
            return False
        new_value = current_amount - removal
        if new_value > 0:
            self._bank_trade_give[resource] = new_value
        else:
            self._bank_trade_give.pop(resource, None)
        return True

    def select_bank_trade_receive(self, resource: str) -> bool:
        """Sélectionne la ressource à recevoir pour l'échange banque."""
        if self.mode != "bank_trade":
            return False
        if resource not in RESOURCE_TYPES:
            return False
        self._bank_trade_receive = resource
        return True

    def reset_bank_trade_selection(self) -> bool:
        """Réinitialise la sélection d'échange banque."""
        if self.mode != "bank_trade":
            return False
        self._bank_trade_give = {}
        self._bank_trade_receive = None
        return True

    def confirm_bank_trade_selection(self) -> bool:
        """Confirme et exécute l'échange banque sélectionné."""
        if self.mode != "bank_trade":
            return False
        if not self._bank_trade_give or not self._bank_trade_receive:
            return False

        assert self.trade_controller is not None

        # Calculer le montant à donner (doit correspondre au taux d'échange)
        if len(self._bank_trade_give) != 1:
            return False

        give_resource = list(self._bank_trade_give.keys())[0]
        give_amount = self._bank_trade_give[give_resource]

        # Vérifier que l'échange est légal
        success = self.trade_controller.handle_bank_trade(
            give_resource, give_amount, self._bank_trade_receive
        )

        if success:
            self._bank_trade_give = {}
            self._bank_trade_receive = None
            self.mode = "idle"
            self.refresh_state()

        return success

    # ------------------------------------------------------------------
    # Gestion de la défausse (voleur)
    # ------------------------------------------------------------------

    def adjust_discard_selection(self, resource: str, delta: int) -> bool:
        if self.mode != "discard":
            return False
        if resource not in RESOURCE_TYPES:
            return False
        if delta == 0:
            return False

        player = self.state.players[self.state.current_player_id]
        current_amount = self._discard_selection.get(resource, 0)
        available = player.resources.get(resource, 0)
        required = self._discard_required
        total_selected = sum(self._discard_selection.values())

        if delta > 0:
            allowed = min(delta, available - current_amount, required - total_selected)
            if allowed <= 0:
                return False
            self._discard_selection[resource] = current_amount + allowed
            return True

        removal = min(-delta, current_amount)
        if removal <= 0:
            return False
        new_value = current_amount - removal
        if new_value > 0:
            self._discard_selection[resource] = new_value
        else:
            self._discard_selection.pop(resource, None)
        return True

    def reset_discard_selection(self) -> bool:
        if self.mode != "discard":
            return False
        if not self._discard_selection:
            return False
        self._discard_selection = {}
        return True

    def confirm_discard_selection(self) -> bool:
        if self.mode != "discard":
            return False
        if sum(self._discard_selection.values()) != self._discard_required:
            return False
        assert self.turn_controller is not None
        selection = dict(self._discard_selection)
        success = self.turn_controller.handle_discard(
            self.state.current_player_id, selection
        )
        if success:
            self._discard_selection = {}
            self._discard_player_id = None
            self._discard_required = 0
            self.refresh_state()
        return success

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
        elif self.mode == "select_road_building":
            # Pour Road Building, montrer toutes les positions légales pour les routes
            assert self.development_controller is not None
            all_legal_edges: Set[int] = set()
            targets = self.development_controller.get_legal_road_building_targets()
            for edge_pair in targets:
                all_legal_edges.add(edge_pair[0])
                all_legal_edges.add(edge_pair[1])
            highlight_edges = all_legal_edges

        buttons = self._build_buttons()
        assert self.hud_controller is not None
        player_panels = tuple(self.hud_controller.get_player_panels())

        discard_prompt: Optional[DiscardPrompt] = None
        if self.mode == "discard" and self._discard_player_id is not None:
            player = self.state.players[self._discard_player_id]
            required = self._discard_required
            selected_total = sum(self._discard_selection.values())
            remaining = max(0, required - selected_total)
            discard_prompt = DiscardPrompt(
                player_id=player.player_id,
                player_name=player.name,
                required=required,
                remaining=remaining,
                selection=dict(self._discard_selection),
                hand=dict(player.resources),
                can_confirm=remaining == 0 and required > 0,
                resource_order=RESOURCE_TYPES,
            )

        bank_trade_prompt: Optional[BankTradePrompt] = None
        if self.mode == "bank_trade":
            player = self.state.players[self.state.current_player_id]
            assert self.trade_controller is not None
            rates = self.trade_controller.get_bank_trade_rates()

            # Vérifier si l'échange est valide
            can_confirm = False
            if self._bank_trade_give and self._bank_trade_receive:
                if len(self._bank_trade_give) == 1:
                    give_resource = list(self._bank_trade_give.keys())[0]
                    give_amount = self._bank_trade_give[give_resource]
                    required_rate = rates.get(give_resource, 4)
                    can_confirm = give_amount == required_rate

            bank_trade_prompt = BankTradePrompt(
                player_name=player.name,
                give_selection=dict(self._bank_trade_give),
                receive_selection=self._bank_trade_receive,
                hand=dict(player.resources),
                rates=rates,
                can_confirm=can_confirm,
                resource_order=RESOURCE_TYPES,
            )

        year_of_plenty_prompt: Optional[YearOfPlentyPrompt] = None
        if self.mode == "year_of_plenty":
            player = self.state.players[self.state.current_player_id]
            required = 2
            selected_total = sum(self._year_of_plenty_selection.values())
            remaining = max(0, required - selected_total)

            year_of_plenty_prompt = YearOfPlentyPrompt(
                player_name=player.name,
                selection=dict(self._year_of_plenty_selection),
                required=required,
                remaining=remaining,
                can_confirm=remaining == 0 and required > 0,
                resource_order=RESOURCE_TYPES,
            )

        return UIState(
            mode=self.mode,
            phase=self.state.phase,
            instructions=instructions,
            highlight_vertices=highlight_vertices,
            highlight_edges=highlight_edges,
            highlight_tiles=highlight_tiles,
            last_dice_roll=self.state.last_dice_roll,
            dice_rolled_this_turn=self.state.dice_rolled_this_turn,
            player_panels=player_panels,
            discard_prompt=discard_prompt,
            bank_trade_prompt=bank_trade_prompt,
            year_of_plenty_prompt=year_of_plenty_prompt,
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
        if self.mode == "discard":
            remaining = max(0, self._discard_required - sum(self._discard_selection.values()))
            return f"{current_player.name} — Défaussez {remaining} carte(s) (cliquez sur +/-)"
        if self.mode == "discard_wait":
            return self.turn_controller.get_instructions()
        if self.mode == "bank_trade":
            if not self._bank_trade_give:
                return f"{current_player.name} — Sélectionnez les ressources à donner"
            if not self._bank_trade_receive:
                return f"{current_player.name} — Sélectionnez la ressource à recevoir"
            return f"{current_player.name} — Confirmez l'échange"
        if self.mode == "select_road_building":
            num_selected = len(self._road_building_edges)
            if num_selected == 0:
                return f"{current_player.name} — Sélectionnez la 1ère route (Construction de routes)"
            elif num_selected == 1:
                return f"{current_player.name} — Sélectionnez la 2ème route (Construction de routes)"
            return f"{current_player.name} — Construction de routes"
        if self.mode == "year_of_plenty":
            remaining = max(0, 2 - sum(self._year_of_plenty_selection.values()))
            if remaining > 0:
                return f"{current_player.name} — Sélectionnez {remaining} ressource(s) (Année d'Abondance)"
            return f"{current_player.name} — Confirmez votre sélection (Année d'Abondance)"

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
            and self.mode not in ("build_road", "build_settlement", "build_city", "move_robber", "discard", "discard_wait")
        )

        buttons["roll_dice"] = ButtonState("Lancer les dés", can_roll)

        legal_actions = self.state.legal_actions()
        can_end_turn = (
            EndTurn() in legal_actions
            and self.mode not in ("setup", "move_robber", "discard", "discard_wait")
        )
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

        can_buy_development = (
            self.mode == "idle"
            and BuyDevelopment() in legal_actions
        )
        buttons["buy_development"] = ButtonState("Acheter carte dev", can_buy_development)

        # Boutons pour jouer les cartes de développement
        assert self.development_controller is not None
        can_play_knight = (
            self.mode == "idle"
            and self.development_controller.can_play_knight()
        )
        buttons["play_knight"] = ButtonState("Jouer Chevalier", can_play_knight)

        can_play_yop = (
            self.mode == "idle"
            and bool(self.development_controller.get_legal_year_of_plenty_options())
        )
        buttons["play_year_of_plenty"] = ButtonState("Jouer Année d'Abondance", can_play_yop)

        can_play_monopoly = (
            self.mode == "idle"
            and bool(self.development_controller.get_legal_monopoly_resources())
        )
        buttons["play_monopoly"] = ButtonState("Jouer Monopole", can_play_monopoly)

        can_play_road_building = (
            self.mode == "idle"
            and bool(self.development_controller.get_legal_road_building_targets())
        )
        buttons["play_road_building"] = ButtonState("Jouer Construction de Routes", can_play_road_building)

        # Boutons pour le commerce
        assert self.trade_controller is not None
        can_bank_trade = (
            self.mode == "idle"
            and bool(self.trade_controller.get_legal_bank_trades())
        )
        buttons["bank_trade"] = ButtonState("Échanger avec la banque", can_bank_trade)

        can_player_trade = (
            self.mode == "idle"
            and bool(self.trade_controller.get_legal_player_trade_offers())
        )
        buttons["player_trade"] = ButtonState("Proposer échange joueur", can_player_trade)

        can_accept_trade = self.trade_controller.can_accept_trade()
        buttons["accept_trade"] = ButtonState("Accepter l'échange", can_accept_trade)

        can_decline_trade = self.trade_controller.can_decline_trade()
        buttons["decline_trade"] = ButtonState("Refuser l'échange", can_decline_trade)

        # Bouton d'annulation actif lorsqu'un mode temporaire est enclenché
        cancel_label = "Réinitialiser" if self.mode == "discard" else "Annuler"
        buttons["cancel"] = ButtonState(
            cancel_label,
            self.mode
            in {
                "build_road",
                "build_settlement",
                "build_city",
                "move_robber",
                "discard",
                "bank_trade",
                "year_of_plenty",
                "select_road_building",
            },
        )

        return buttons
