# hook-main.py
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules('app.qt.app') +
    collect_submodules('app.qt.app_handlers') +
    collect_submodules('app.qt.app_helpers') +
    collect_submodules('app.qt.app_state_manager') +
    collect_submodules('app.qt.ui_manager') +
    collect_submodules('app.qt.ui_generator') +
    collect_submodules('app.qt.ui_s_generator') +
    collect_submodules('static.qt.layout_metadata') +

    collect_submodules('app.qt_browser.mini_browser') + # TODO: check maybe don't needed
    collect_submodules('app.vlc.vlc_player') + # TODO: check maybe don't needed
    collect_submodules('app.mpv.base_engine') +
    collect_submodules('app.mpv.main') + # TODO: check maybe don't needed
    collect_submodules('app.mpv.playback_request') +
    collect_submodules('app.mpv.player_window') +
    collect_submodules('app.mpv.runner') +
    collect_submodules('app.mpv.timing_config') +

    collect_submodules('app._animedia.animedia_client') +
    collect_submodules('app._animedia.animedia_utils') +
    collect_submodules('app._animedia.demo') +
    collect_submodules('app._animedia.playlist_manager') +

    collect_submodules('core.database_manager') +
    collect_submodules('core.get') +
    collect_submodules('core.save') +
    collect_submodules('core.delete') +
    collect_submodules('core.process') +
    collect_submodules('core.tables') +
    collect_submodules('core.utils') +

    collect_submodules('providers.animedia.v0.adapter') +
    collect_submodules('providers.animedia.v0.cache_manager') +
    collect_submodules('providers.animedia.v0.client') +
    collect_submodules('providers.animedia.v0.legacy_mapper') +
    collect_submodules('providers.animedia.v0.qt_async_worker') +

    collect_submodules('providers.aniliberty.v1.adapter') +
    collect_submodules('providers.aniliberty.v1.api') +
    collect_submodules('providers.aniliberty.v1.cache_policy') +
    collect_submodules('providers.aniliberty.v1.endpoints') +
    collect_submodules('providers.aniliberty.v1.legacy_mapper') +
    collect_submodules('providers.aniliberty.v1.service') +
    collect_submodules('providers.aniliberty.v1.settings') +
    collect_submodules('providers.aniliberty.v1.transport') +
    collect_submodules('providers.aniliberty.v1.xml_parser') +

    collect_submodules('utils.config.config_manager') +
    collect_submodules('utils.security.library_loader') +
    collect_submodules('utils.logging.logging_handlers') +
    collect_submodules('utils.playlists.playlist_manager') +
    collect_submodules('utils.playlists.playlist_key') +
    collect_submodules('utils.downloads.poster_manager') +
    collect_submodules('utils.downloads.torrent_manager') +
    collect_submodules('utils.runtime.runtime_manager') +
    collect_submodules('utils.integrations.open_router') +
    collect_submodules('utils.net.net_client') +
    collect_submodules('utils.net.url_resolve_service') +
    collect_submodules('utils.net.url_resolver') +
    collect_submodules('utils.net.url_resolver_settings')





)

datas = collect_data_files('app') + collect_data_files('core') + collect_data_files('utils')
