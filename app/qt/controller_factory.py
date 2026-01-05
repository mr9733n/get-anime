# app/qt/controller_factory.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any
from logging import Logger

from app.qt.controllers.actions import ActionsController, ActionsControllerDeps
from app.qt.controllers.display import DisplayController, DisplayControllerDeps
from app.qt.controllers.persistence import PersistenceController, PersistenceControllerDeps
from app.qt.controllers.posters import PosterController, PosterControllerDeps
from app.qt.controllers.state_runtime import StateRuntimeController, StateRuntimeControllerDeps
from app.qt.controllers.aniliberty import AniLibertyController, AniLibertyControllerDeps
from app.qt.controllers.animedia import AniMediaController, AniMediaControllerDeps
from app.qt.controllers.torrents import TorrentController, TorrentControllerDeps
from app.qt.controllers.players import PlayerController, PlayerControllerDeps
from app.qt.controllers.callback import CallbackController, CallbackControllerDeps
from app.qt.controllers.bootstrap import BootstrapController, BootstrapControllerDeps
from app.core.use_cases.title_search_use_case import TitleSearchUseCase
from app.qt.app_constants import PROVIDER_ANILIBERTY, PROVIDER_ANIMEDIA
from app.qt.ui_notify import Notifier

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from app.qt.app_context import AppContext
    from app.qt.app_services import AppServices


@dataclass
class ControllerFactoryConfig:
    """Конфигурация для фабрики контроллеров."""
    base_al_url: str = ""
    base_am_url: str = ""
    use_libvlc: bool = False
    use_mpv_player: bool = False
    proxy_enabled: bool = False
    proxy_url: str = ""
    log_enabled: bool = False
    verbose: str = "2"
    mpv_log_enabled: bool = False
    mpv_verbose: str = "info"
    mpv_player_executable_name: str = "mpv_player.exe"
    video_player_path: str = ""
    prod_key: str | None = None


class ControllerFactory:
    """
    Фабрика для создания контроллеров.
    Решает проблему циклических зависимостей через lazy callbacks.
    """

    def __init__(
            self,
            logger: Logger,
            context: AppContext,
            svc: AppServices,
            parent_widget: QWidget,
            config: ControllerFactoryConfig,
            layout_metadata: list[dict],
            # External dependencies
            config_manager: Any,
            animedia_adapter: Any,
            animedia_cache: Any,
            ui_generator: Any,
            ui_am_generator: Any,
            ui_s_generator: Any,
            poster_manager: Any,
            torrent_manager: Any,
            playlist_manager: Any,
            api_adapter: Any,
            url_resolver: Any = None,
            router_getter: Callable[[], Any] | None = None,
    ):
        self._logger = logger
        self._context = context
        self._svc = svc
        self._parent_widget = parent_widget
        self._config = config
        self._layout_metadata = layout_metadata

        # External deps
        self._config_manager = config_manager
        self._animedia_adapter = animedia_adapter
        self._animedia_cache = animedia_cache
        self._ui_generator = ui_generator
        self._ui_am_generator = ui_am_generator
        self._ui_s_generator = ui_s_generator
        self._poster_manager = poster_manager
        self._torrent_manager = torrent_manager
        self._playlist_manager = playlist_manager
        self._api_adapter = api_adapter
        self._url_resolver = url_resolver
        self._router_getter = router_getter

        # Controllers
        self.bootstrap: BootstrapController | None = None
        self.persistence: PersistenceController | None = None
        self.poster: PosterController | None = None
        self.torrent: TorrentController | None = None
        self.state: StateRuntimeController | None = None
        self.display: DisplayController | None = None
        self.actions: ActionsController | None = None
        self.aniliberty: AniLibertyController | None = None
        self.animedia: AniMediaController | None = None
        self.player: PlayerController | None = None
        self.callback: CallbackController | None = None

    def build(self) -> ControllerFactory:
        """Создаёт все контроллеры в правильном порядке."""

        # === Phase 1: Bootstrap + Independent ===

        self.bootstrap = BootstrapController(
            BootstrapControllerDeps(
                logger=self._logger,
                config_manager=self._config_manager,
            )
        )

        self.persistence = PersistenceController(
            PersistenceControllerDeps(
                logger=self._logger,
                db=self._svc.db,
            )
        )

        self.poster = PosterController(
            PosterControllerDeps(
                logger=self._logger,
                db=self._svc.db,
                context=self._context,
                poster_manager=self._poster_manager,
                base_al_url=self._config.base_al_url,
                base_am_url=self._config.base_am_url,
            )
        )

        self.torrent = TorrentController(
            TorrentControllerDeps(
                logger=self._logger,
                torrent_manager=self._torrent_manager,
            )
        )

        # === Phase 2: State ===

        self.state = StateRuntimeController(
            StateRuntimeControllerDeps(
                logger=self._logger,
                db=self._svc.db,
                context=self._context,
                get_display_controller=lambda: self.display,
                get_animedia_controller=lambda: self.animedia,
            )
        )

        # === Phase 3: Provider Controllers ===

        self.aniliberty = AniLibertyController(
            AniLibertyControllerDeps(
                logger=self._logger,
                db=self._svc.db,
                ui=self._svc.ui,
                api=self._api_adapter,
                context=self._context,
                persistence=self.persistence,
                get_display_controller=lambda: self.display,
                get_state_controller=lambda: self.state,
            )
        )

        # === Phase 4: Display (central) ===

        self.display = DisplayController(
            DisplayControllerDeps(
                logger=self._logger,
                db=self._svc.db,
                ui=self._svc.ui,
                context=self._context,
                ui_generator=self._ui_generator,
                ui_am_generator=self._ui_am_generator,
                ui_s_generator=self._ui_s_generator,
                parent_widget=self._parent_widget,
                get_poster_controller=lambda: self.poster,
                get_state_controller=lambda: self.state,
                get_aniliberty_controller=lambda: self.aniliberty,
            )
        )

        # === Phase 5: Actions ===
        notifier = Notifier(self._parent_widget)

        title_search_use_case = TitleSearchUseCase(
            db=self._svc.db,
            api=self._api_adapter,
            persistence=self.persistence,
            animedia_adapter=self._animedia_adapter,
            provider_aniliberty=PROVIDER_ANILIBERTY,
            provider_animedia=PROVIDER_ANIMEDIA,
        )

        self.actions = ActionsController(
            ActionsControllerDeps(
                logger=self._logger,
                db=self._svc.db,
                api=self._api_adapter,
                ui=self._svc.ui,
                display=self.display,
                persistence=self.persistence,
                context=self._context,
                animedia_adapter=self._animedia_adapter,
                use_case=title_search_use_case,
                on_show_title=lambda tid: self.display.display_info(tid),
                on_show_titles=lambda tids: self.display.display_titles(tids),

                on_notify_error=lambda t, m: notifier.error(t, m),
                on_notify_warning=lambda t, m: notifier.warning(t, m),
                on_notify_info=lambda t, m: notifier.info(t, m),
                on_notify_success=lambda t, m: notifier.success(t, m),

                on_refresh=lambda: self.display.refresh_display(),

            )
        )

        # === Phase 6: AniMedia ===

        self.animedia = AniMediaController(
            AniMediaControllerDeps(
                logger=self._logger,
                db=self._svc.db,
                ui=self._svc.ui,
                context=self._context,
                animedia_adapter=self._animedia_adapter,
                animedia_cache=self._animedia_cache,
                get_display_controller=lambda: self.display,
                get_state_controller=lambda: self.state,
                get_actions_controller=lambda: self.actions,
            )
        )

        # === Phase 7: Player ===

        self.player = PlayerController(
            PlayerControllerDeps(
                logger=self._logger,
                db=self._svc.db,
                context=self._context,
                playlist_manager=self._playlist_manager,
                url_resolver=self._url_resolver,
                use_libvlc=self._config.use_libvlc,
                use_mpv_player=self._config.use_mpv_player,
                proxy_enabled=self._config.proxy_enabled,
                proxy_url=self._config.proxy_url,
                log_enabled=self._config.log_enabled,
                verbose=self._config.verbose,
                mpv_log_enabled=self._config.mpv_log_enabled,
                mpv_verbose=self._config.mpv_verbose,
                mpv_player_executable_name=self._config.mpv_player_executable_name,
                video_player_path=self._config.video_player_path,
                prod_key=self._config.prod_key,
                get_router=self._router_getter,
            )
        )

        # === Phase 8: Callback ===

        self.callback = CallbackController(
            CallbackControllerDeps(
                logger=self._logger,
                context=self._context,
                layout_metadata=self._layout_metadata,
                get_actions=lambda: self.actions,
                get_display=lambda: self.display,
                get_aniliberty=lambda: self.aniliberty,
                get_animedia=lambda: self.animedia,
                get_player=lambda: self.player,
            )
        )

        return self

    def get_callbacks(self) -> dict[str, Callable]:
        """Возвращает callbacks для UI."""
        if self.callback is None:
            raise RuntimeError("Controllers not built. Call build() first.")
        return self.callback.generate_callbacks()