# make_bin/config.py
"""
Общие настройки для сборки PyInstaller
"""
import os
import sys
import site
import platform

# === Определение платформы ===
IS_WINDOWS = sys.platform == 'win32'
IS_MAC = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')


def get_platform_name():
    return platform.system()


# === Пути ===
# make_bin/config.py -> PROJECT_DIR это родительская папка
MAKE_BIN_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(MAKE_BIN_DIR)
DIST_DIR = os.path.join(PROJECT_DIR, 'dist')
BUILD_DIR = os.path.join(PROJECT_DIR, 'build')

# === Расширения ===
EXE_EXT = '.exe' if IS_WINDOWS else ''

# === Пакеты Python ===
if IS_WINDOWS:
    try:
        # Пробуем получить site-packages из виртуального окружения
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            # Мы в виртуальном окружении
            PACKAGES_FOLDER = os.path.join(sys.prefix, 'Lib', 'site-packages')
        else:
            python_root = site.getsitepackages()[0]
            PACKAGES_FOLDER = python_root
    except Exception:
        PACKAGES_FOLDER = os.path.join(sys.prefix, 'Lib', 'site-packages')
else:
    try:
        PACKAGES_FOLDER = site.getsitepackages()[0]
    except AttributeError:
        import sysconfig

        PACKAGES_FOLDER = sysconfig.get_paths()["purelib"]

# === Директории приложений ===
APP_DIR = "app"


# === Имена приложений ===
class AppNames:
    MAIN = 'AnimePlayer'
    VLC = 'vlc_player'
    MPV = 'mpv_player'
    BROWSER = 'mini_browser'
    LITE = 'AnimePlayerLite'
    SYNC = 'PlayerDBSync'
    SYNC_LAN = 'PlayerDBSyncLAN'


# === Пути к исходникам (АБСОЛЮТНЫЕ!) ===
class SourceFiles:
    MAIN = os.path.join(PROJECT_DIR, 'main.py')
    VLC = os.path.join(PROJECT_DIR, 'app', 'vlc', 'vlc_player.py')
    MPV = os.path.join(PROJECT_DIR, 'app', 'mpv', 'main.py')
    BROWSER = os.path.join(PROJECT_DIR, 'app', 'qt_browser', 'mini_browser.py')
    LITE = os.path.join(PROJECT_DIR, 'app', 'tinker_v1', 'app.py')
    SYNC = os.path.join(PROJECT_DIR, 'app', 'sync', 'db_sync_gui.py')


# === Скомпилированные директории ===
class CompiledDirs:
    @staticmethod
    def get(name):
        return os.path.join(DIST_DIR, name)

    @staticmethod
    def internal(name):
        return os.path.join(DIST_DIR, name, '_internal')


# === Версии приложений ===
class Versions:
    MAIN = {
        "FileVersion": "0.3.8.37",
        "ProductVersion": "0.3.8",
        "CompanyName": "666s.dev",
        "FileDescription": "AnimePlayer",
        "InternalName": "AnimePlayer",
        "LegalCopyright": "© 2025 666s.dev",
        "OriginalFilename": "AnimePlayer.exe",
        "ProductName": "AnimePlayer",
    }

    VLC = {
        "FileVersion": "0.3.8.37",
        "ProductVersion": "0.3.8",
        "CompanyName": "666s.dev",
        "FileDescription": "AnimePlayerVlc",
        "InternalName": "AnimePlayerVlc",
        "LegalCopyright": "© 2025 666s.dev",
        "OriginalFilename": "AnimePlayerVlc.exe",
        "ProductName": "AnimePlayerVlc",
    }

    MPV = {
        "FileVersion": "0.3.8.37",
        "ProductVersion": "0.3.8",
        "CompanyName": "666s.dev",
        "FileDescription": "AnimePlayerMpv",
        "InternalName": "AnimePlayerMpv",
        "LegalCopyright": "© 2025 666s.dev",
        "OriginalFilename": "AnimePlayerMpv.exe",
        "ProductName": "AnimePlayerMpv",
    }

    BROWSER = {
        "FileVersion": "0.3.8.37",
        "ProductVersion": "0.3.8",
        "CompanyName": "666s.dev",
        "FileDescription": "MiniBrowser",
        "InternalName": "MiniBrowser",
        "LegalCopyright": "© 2025 666s.dev",
        "OriginalFilename": "MiniBrowser.exe",
        "ProductName": "MiniBrowser",
    }

    LITE = {
        "FileVersion": "0.1.10.0",
        "ProductVersion": "0.1.10",
        "CompanyName": "666s.dev",
        "FileDescription": "AnimePlayerLite",
        "InternalName": "AnimePlayerLite",
        "LegalCopyright": "© 2025 666s.dev",
        "OriginalFilename": "AnimePlayerLite.exe",
        "ProductName": "AnimePlayerLite",
    }

    SYNC = {
        "FileVersion": "0.0.0.1",
        "ProductVersion": "0.0.0.1",
        "CompanyName": "666s.dev",
        "FileDescription": "AnimePlayerDBSyncUtilityApp",
        "InternalName": "AnimePlayerDBSyncUtilityApp",
        "LegalCopyright": "© 2025 666s.dev",
        "OriginalFilename": "PlayerDBSync.exe",
        "ProductName": "AnimePlayerDBSyncUtilityApp",
    }

    SYNC_LAN = {
        "FileVersion": "0.0.0.1",
        "ProductVersion": "0.0.0.1",
        "CompanyName": "666s.dev",
        "FileDescription": "AnimePlayerDBSyncLANUtilityApp",
        "InternalName": "AnimePlayerDBSyncLANUtilityApp",
        "LegalCopyright": "© 2025 666s.dev",
        "OriginalFilename": "PlayerDBSyncLAN.exe",
        "ProductName": "AnimePlayerDBSyncLANUtilityApp",
    }


# === Иконка (АБСОЛЮТНЫЙ путь!) ===
ICON_FILE = os.path.join(PROJECT_DIR, 'favicon.ico')

print(f"📂 Platform: {get_platform_name()}")
print(f"📂 Project dir: {PROJECT_DIR}")
print(f"📂 Site-packages: {PACKAGES_FOLDER}")