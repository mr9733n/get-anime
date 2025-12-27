# hook-main.py
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules('app.qt') +
    collect_submodules('static') +

    collect_submodules('core') +

    collect_submodules('providers.animedia.v0') +
    collect_submodules('providers.aniliberty.v1') +

    collect_submodules('utils.config') +
    collect_submodules('utils.security') +
    collect_submodules('utils.logging') +
    collect_submodules('utils.playlists') +
    collect_submodules('utils.downloads') +
    collect_submodules('utils.runtime') +
    collect_submodules('utils.integrations') +
    collect_submodules('utils.net') +
    collect_submodules('utils.parsing') +
    collect_submodules('utils.media')
    )

datas = (collect_data_files('app') +
         collect_data_files('core') +
         collect_data_files('utils') +
         collect_data_files('providers')
         )
