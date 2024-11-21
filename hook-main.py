# hook-main.py
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules('app.qt.app') +
    collect_submodules('app.qt.ui_manager') +
    collect_submodules('app.qt.ui_generator') +
    collect_submodules('app.qt.ui_s_generator') +
    collect_submodules('core.database_manager') +
    collect_submodules('core.get') +
    collect_submodules('core.save') +
    collect_submodules('core.process') +
    collect_submodules('core.tables') +
    collect_submodules('core.utils') +
    collect_submodules('utils.api_client') +
    collect_submodules('utils.config_manager') +
    collect_submodules('utils.logging_handlers') +
    collect_submodules('utils.playlist_manager') +
    collect_submodules('utils.poster_manager') +
    collect_submodules('utils.torrent_manager')
)

datas = collect_data_files('app') + collect_data_files('core') + collect_data_files('utils')
