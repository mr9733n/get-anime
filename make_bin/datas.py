# make_bin/datas.py
"""
Конфигурация datas для PyInstaller Analysis.
"""
import os
from make_bin.config import PROJECT_DIR


def get_main_app_datas(build_config_path: str) -> list[tuple[str, str]]:
    """
    Возвращает список datas для основного приложения.

    Args:
        build_config_path: Путь к временному config.ini

    Returns:
        Список кортежей (source, dest) для PyInstaller
    """
    datas = [
        # Статические файлы
        (os.path.join(PROJECT_DIR, 'static', '*'), 'static'),
        (os.path.join(PROJECT_DIR, 'templates'), 'templates'),
        (os.path.join(PROJECT_DIR, 'config', 'logging.conf'), 'config'),
        (os.path.join(PROJECT_DIR, 'db', '*'), 'db'),
        (os.path.join(PROJECT_DIR, 'libs'), 'libs'),

        # Скомпилированные .pyc файлы - App
        (os.path.join(PROJECT_DIR, 'app', 'qt', '__pycache__'), 'app/qt/__pycache__'),
        (os.path.join(PROJECT_DIR, 'app', 'vlc', '__pycache__'), 'app/vlc/__pycache__'),
        (os.path.join(PROJECT_DIR, 'app', 'mpv', '__pycache__'), 'app/mpv/__pycache__'),
        (os.path.join(PROJECT_DIR, 'app', 'qt_browser', '__pycache__'), 'app/qt_browser/__pycache__'),

        # Core
        (os.path.join(PROJECT_DIR, 'core', '__pycache__'), 'core/__pycache__'),

        # Utils подмодули (исправленные пути!)
        (os.path.join(PROJECT_DIR, 'utils', 'config', '__pycache__'), 'utils/config/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'security', '__pycache__'), 'utils/security/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'logging', '__pycache__'), 'utils/logging/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'playlists', '__pycache__'), 'utils/playlists/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'downloads', '__pycache__'), 'utils/downloads/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'runtime', '__pycache__'), 'utils/runtime/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'integrations', '__pycache__'), 'utils/integrations/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'net', '__pycache__'), 'utils/net/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'parsing', '__pycache__'), 'utils/parsing/__pycache__'),
        (os.path.join(PROJECT_DIR, 'utils', 'media', '__pycache__'), 'utils/media/__pycache__'),

        # Providers
        (os.path.join(PROJECT_DIR, 'providers', 'animedia', 'v0', '__pycache__'), 'providers/animedia/v0/__pycache__'),
        (os.path.join(PROJECT_DIR, 'providers', 'aniliberty', 'v1', '__pycache__'),
         'providers/aniliberty/v1/__pycache__'),

        # Корневые файлы
        (os.path.join(PROJECT_DIR, 'favicon.ico'), '.'),
        (os.path.join(PROJECT_DIR, 'anime_player_app_roadmap.md'), '.'),
        (os.path.join(PROJECT_DIR, 'LICENSE.md'), '.'),
        (os.path.join(PROJECT_DIR, 'README.md'), '.'),
        (os.path.join(PROJECT_DIR, 'sql_commands.md'), '.'),

        # Временный конфиг
        (build_config_path, 'config/.'),
    ]

    # НЕ добавляем logs - создаётся при старте приложения

    return datas


def get_player_datas() -> list[tuple[str, str]]:
    """
    Возвращает список datas для плееров (VLC, MPV).
    """
    datas = [
        (os.path.join(PROJECT_DIR, 'config', 'logging.conf'), 'config'),
        (os.path.join(PROJECT_DIR, 'static', 'icon.png'), 'static'),
        # libs нужен для MPV (libmpv-2.dll) и security
        (os.path.join(PROJECT_DIR, 'libs'), 'libs'),
    ]

    return datas


def get_mpv_binaries() -> list[tuple[str, str]]:
    """
    Возвращает binaries для MPV плеера (libmpv-2.dll).
    """
    binaries = []

    # libmpv-2.dll должен быть в корне или рядом с exe
    libmpv_path = os.path.join(PROJECT_DIR, 'libs', 'libmpv-2.dll')
    if os.path.exists(libmpv_path):
        # '.' означает корень dist папки (рядом с exe)
        binaries.append((libmpv_path, '.'))

    return binaries


def get_lite_app_datas() -> list[tuple[str, str]]:
    """
    Возвращает список datas для Lite версии приложения.
    """
    return [
        (os.path.join(PROJECT_DIR, 'config', 'config.ini'), 'config'),
        (os.path.join(PROJECT_DIR, 'favicon.ico'), '.'),
    ]


# === Путь к хукам ===
def get_hookspath() -> list[str]:
    """
    Возвращает пути к директориям с хуками PyInstaller.
    """
    return [
        PROJECT_DIR,  # Где лежат hook-main.py, hook-sqlalchemy.py
    ]


# === Списки для очистки после сборки ===

def get_folders_to_delete() -> dict[str, list[str]]:
    """
    Возвращает папки для удаления после сборки (уменьшение размера / антивирусы).
    """
    return {
        'AnimePlayer/_internal': [
            "importlib_metadata-*.dist-info",
            "MarkupSafe-*.dist-info",
            "numpy-*.dist-info",
            "h2-*.dist-info",
            "cryptography-*.dist-info",
            "attrs-*.dist-info",
            "cryptography",  # VirusTotal false positive
            "charset_normalizer",  # VirusTotal false positive
            "markupsafe",  # VirusTotal false positive
        ],
        'AnimePlayerLite/_internal': [
            "h2-*.dist-info",
            "charset_normalizer",  # VirusTotal false positive
        ]
    }


def get_files_to_delete() -> dict[str, list[str]]:
    """
    Возвращает файлы для удаления после сборки.
    """
    return {
        'AnimePlayer/_internal/PIL': [
            "_imagingtk.cp312-win_amd64.pyd",  # VirusTotal false positive
            "_webp.cp312-win_amd64.pyd",  # VirusTotal false positive
            "_imagingtk.cp313-win_amd64.pyd",  # Python 3.13
            "_webp.cp313-win_amd64.pyd",  # Python 3.13
        ]
    }


def get_folders_to_move() -> dict[str, tuple[str, list[str]]]:
    """
    Возвращает папки для перемещения из _internal в корень.

    Returns:
        { source_internal: (dest_root, [folder_names]) }
    """
    return {
        'AnimePlayer/_internal': (
            'AnimePlayer',
            ["app", "config", "core", "db", "libs", "static", "templates", "utils", "providers"]
        ),
        'AnimePlayerLite/_internal': (
            'AnimePlayerLite',
            ["config"]
        ),
    }


def get_files_to_copy() -> dict[str, list[str]]:
    """
    Возвращает файлы для копирования в целевую директорию.
    """
    return {
        'AnimePlayer': [
            "anime_player_app_roadmap.md",
            "LICENSE.md",
            "sql_commands.md",
            "README.md",
        ]
    }