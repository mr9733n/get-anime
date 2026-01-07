# make_bin/hiddenimports.py
"""
Конфигурация hiddenimports для PyInstaller Analysis.
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# === PyQt5 импорты (общие для всех Qt приложений) ===
PYQT5_HIDDENIMPORTS = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    'PyQt6.QtNetwork',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtSvg',
    'PyQt6.QtOpenGL',
]

# === PyQtWebEngine импорты (для браузера) ===
PYQT_WEBENGINE_HIDDENIMPORTS = [
    'PyQt6.QtWebEngine',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebChannel',
]

# === Стандартные модули Python которые могут не подхватиться ===
STDLIB_HIDDENIMPORTS = [
    'cgitb',  # ВАЖНО: используется в core/process.py
    'html',
    'html.parser',
    'http.client',
    'http.cookies',
    'email.mime.text',
    'email.mime.multipart',
    'logging.config',
    'logging.handlers',
    'multiprocessing',
    'multiprocessing.pool',
    'concurrent.futures',
    'asyncio',
    'json',
    'uuid',
    'base64',
    'hashlib',
    'configparser',
    'traceback',
    'threading',
    'urllib.parse',
]

# PIL - добавьте ВСЕ плагины явно
PIL_HIDDENIMPORTS = [
    'PIL',
    'PIL.Image',
    'PIL._imaging',
    'PIL.ImageFile',
    'PIL.ImageOps',
    'PIL.ImageEnhance',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageFilter',

    # Плагины форматов - КРИТИЧНО для работы
    'PIL.JpegImagePlugin',
    'PIL.PngImagePlugin',
    'PIL.WebPImagePlugin',  # ← Основной для WebP
    'PIL.GifImagePlugin',
    'PIL.BmpImagePlugin',
    'PIL.IcoImagePlugin',
    'PIL.TiffImagePlugin',

    # Вспомогательные модули
    'PIL._tkinter_finder',
    'PIL._util',
    'PIL._binary',
]
# === Базовые импорты для основного приложения ===
BASE_HIDDENIMPORTS = [
    # PyQt5
    *PYQT5_HIDDENIMPORTS,

    # Stdlib
    *STDLIB_HIDDENIMPORTS,

    # Основные библиотеки
    'pkg_resources',
    'pkg_resources.extern',
    'vlc',
    'mpv',  # MPV библиотека
    'requests',
    'requests.compat',
    'urllib3',
    'urllib3.contrib.socks',
    'cryptography',

    # PIL
    *PIL_HIDDENIMPORTS,

    # Numpy (если используется)
    'numpy',

    # SQLAlchemy
    'sqlalchemy',
    'sqlalchemy.orm',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.engine',
    'sqlalchemy.sql',
    'sqlalchemy.dialects.sqlite',

    # HTTP клиенты
    'httpx',
    'httpx._transports.default',
    'aiohttp',

    # Шаблоны и парсинг
    'jinja2',
    'beautifulsoup4',
    'bs4',

    # Pydantic
    'pydantic',
    'pydantic.deprecated.decorator',
    'pydantic_core',

    # setproctitle
    'setproctitle',
]

# === Импорты для VLC Player ===
VLC_HIDDENIMPORTS = [
    *PYQT5_HIDDENIMPORTS,
    *STDLIB_HIDDENIMPORTS,
    'vlc',
    'ctypes',
    'argparse',
    'setproctitle',
    # Utils модули
    'utils',
    'utils.runtime',
    'utils.runtime.runtime_manager',
    'utils.logging',
    'utils.logging.logging_handlers',
]

# === Импорты для MPV Player ===
MPV_HIDDENIMPORTS = [
    *PYQT5_HIDDENIMPORTS,
    *STDLIB_HIDDENIMPORTS,
    'mpv',  # python-mpv библиотека
    'ctypes',
    'argparse',
    'math',
    'setproctitle',
    'traceback',
    'threading',
    'urllib.parse',
    # Utils модули - явно
    'utils',
    'utils.runtime',
    'utils.runtime.runtime_manager',
    'utils.security',
    'utils.security.library_loader',
    'utils.logging',
    'utils.logging.logging_handlers',
    # App MPV модули
    'app.mpv',
    'app.mpv.base_engine',
    'app.mpv.mpv_engine',
    'app.mpv.main',
    'app.mpv.playback_request',
    'app.mpv.player_window',
    'app.mpv.runner',
    'app.mpv.timing_config',
]

# === Импорты для Mini Browser (нужен WebEngine!) ===
BROWSER_HIDDENIMPORTS = [
    *PYQT5_HIDDENIMPORTS,
    *PYQT_WEBENGINE_HIDDENIMPORTS,
    *STDLIB_HIDDENIMPORTS,
]

# === Импорты для Lite версии (Tkinter) ===
LITE_HIDDENIMPORTS = [
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'requests',
    'configparser',
]

# === Исключения для Lite версии ===
LITE_EXCLUDES = [
    "cryptography",
    "numpy",
    "PyQt6",
    "PyQtWebEngine",
]


def get_collected_submodules() -> list[str]:
    """
    Собирает все подмодули проекта через collect_submodules.
    Аналог того что делает hook-main.py

    Returns:
        Плоский список всех модулей
    """
    modules = []

    # Список модулей для сбора (как в hook-main.py)
    modules_to_collect = [
        # App - активные модули для основного приложения
        'app.qt',
        'app.vlc',
        'app.mpv',
        'app.qt_browser',
        # app._animedia - obsolete
        # app.sync - отдельная сборка (playerDBsync.spec)
        # app.tinker_v1 - для Lite версии (не нужен в main)

        # Static
        'static',

        # Storage
        'storage',

        # Providers
        'providers.animedia.v0',
        'providers.aniliberty.v1',

        # Utils - ВСЕ подмодули
        'utils.config',
        'utils.security',
        'utils.logging',
        'utils.playlists',
        'utils.downloads',
        'utils.runtime',
        'utils.integrations',
        'utils.net',
        'utils.parsing',
        'utils.media',
    ]

    for module in modules_to_collect:
        try:
            collected = collect_submodules(module)
            modules.extend(collected)
            print(f"  ✓ Collected {len(collected)} submodules from {module}")
        except Exception as e:
            print(f"  ⚠️ Warning: Could not collect submodules for {module}: {e}")

    return modules


def get_collected_datas() -> list[tuple]:
    """
    Собирает data files для проекта.
    Аналог того что делает hook-main.py

    Returns:
        Список кортежей (source, dest)
    """
    datas = []

    modules_to_collect = ['app', 'storage', 'utils', 'providers']

    for module in modules_to_collect:
        try:
            collected = collect_data_files(module)
            datas.extend(collected)
        except Exception as e:
            print(f"  ⚠️ Warning: Could not collect data files for {module}: {e}")

    return datas


def get_main_hiddenimports() -> list[str]:
    """
    Возвращает полный список hiddenimports для основного приложения.

    Returns:
        Плоский список всех импортов
    """
    print("\n📦 Collecting submodules...")
    collected = get_collected_submodules()
    print(f"📦 Total collected: {len(collected)} modules\n")

    # Основное приложение использует и Qt, и WebEngine
    return BASE_HIDDENIMPORTS + PYQT_WEBENGINE_HIDDENIMPORTS + collected


def get_vlc_hiddenimports() -> list[str]:
    """Возвращает hiddenimports для VLC Player."""
    # Добавляем collect_submodules для utils
    utils_modules = []
    for module in ['utils.runtime', 'utils.logging']:
        try:
            utils_modules.extend(collect_submodules(module))
        except:
            pass
    return VLC_HIDDENIMPORTS + utils_modules


def get_mpv_hiddenimports() -> list[str]:
    """Возвращает hiddenimports для MPV Player."""
    # Добавляем collect_submodules для utils и app.mpv
    extra_modules = []
    for module in ['utils.runtime', 'utils.logging', 'utils.security', 'app.mpv']:
        try:
            extra_modules.extend(collect_submodules(module))
        except:
            pass
    return MPV_HIDDENIMPORTS + extra_modules


def get_browser_hiddenimports() -> list[str]:
    """Возвращает hiddenimports для Mini Browser."""
    return BROWSER_HIDDENIMPORTS.copy()


def get_lite_hiddenimports() -> list[str]:
    """Возвращает hiddenimports для Lite версии."""
    return LITE_HIDDENIMPORTS.copy()


def get_lite_excludes() -> list[str]:
    """Возвращает excludes для Lite версии."""
    return LITE_EXCLUDES.copy()