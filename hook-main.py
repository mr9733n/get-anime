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
    collect_submodules('app.qt.vlc_player') +

    collect_submodules('app._animedia.animedia_client') +
    collect_submodules('app._animedia.animedia_utils') +
    collect_submodules('app._animedia.demo') +
    collect_submodules('app._animedia.playlist_manager') +

    collect_submodules('core.database_manager') +
    collect_submodules('core.get') +
    collect_submodules('core.save') +
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

    collect_submodules('utils.config_manager') +
    collect_submodules('utils.library_loader') +
    collect_submodules('utils.logging_handlers') +
    collect_submodules('utils.playlist_manager') +
    collect_submodules('utils.poster_manager') +
    collect_submodules('utils.runtime_manager') +
    collect_submodules('utils.torrent_manager')
)

datas = collect_data_files('app') + collect_data_files('core') + collect_data_files('utils')
