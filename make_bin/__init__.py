# make_bin/__init__.py
"""
AnimePlayer Build System

Модульная система сборки для PyInstaller.

Структура:
    make_bin/
    ├── __init__.py          # Этот файл
    ├── config.py            # Общие настройки (пути, имена, версии)
    ├── utils.py             # Утилиты (хэш, копирование, бэкап)
    ├── version.py           # Windows Version Resource
    ├── datas.py             # Конфигурация datas для Analysis
    ├── hiddenimports.py     # Конфигурация hiddenimports
    ├── post_build.py        # Пост-сборочные операции
    ├── main.spec            # Главный spec файл (всё вместе)
    └── specs/               # Отдельные spec файлы
        ├── vlc_player.spec
        ├── mpv_player.spec
        ├── mini_browser.spec
        ├── main_app.spec
        └── lite_app.spec

Использование:
    # Полная сборка
    pyinstaller make_bin/main.spec

    # Или через make
    make build          # Unix/macOS
    make.bat build      # Windows

    # Отдельные компоненты
    make vlc
    make mpv
    make main
"""

__version__ = "1.0.0"
__author__ = "666s.dev"

from make_bin.config import (
    PROJECT_DIR,
    DIST_DIR,
    PACKAGES_FOLDER,
    IS_WINDOWS,
    IS_MAC,
    IS_LINUX,
    AppNames,
    Versions,
)

from make_bin.utils import (
    calculate_sha256,
    compile_directories,
    backup_database,
    copy_executable,
    update_hash_in_file,
    ensure_logs_directory,
)

from make_bin.version import version_from_dict

__all__ = [
    'PROJECT_DIR',
    'DIST_DIR',
    'PACKAGES_FOLDER',
    'IS_WINDOWS',
    'IS_MAC',
    'IS_LINUX',
    'AppNames',
    'Versions',
    'calculate_sha256',
    'compile_directories',
    'backup_database',
    'copy_executable',
    'update_hash_in_file',
    'ensure_logs_directory',
    'version_from_dict',
]