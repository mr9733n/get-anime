# -*- mode: python ; coding: utf-8 -*-


# main.spec

# Импортируем необходимый модуль Analysis, EXE, COLLECT
from PyInstaller.utils.hooks import collect_data_files
import os

block_cipher = None

# Указываем путь к директории проекта
project_dir = os.getcwd()

# Сбор данных для ресурсы, например из папок `static` и `db`
datas = [
    (os.path.join(project_dir, 'static/*'), 'static'),
    (os.path.join(project_dir, 'config/*'), 'config'),
]

# Сбор всех файлов `.py` для добавления в бинарник
hidden_imports = [
    'app.qt.app',
    'app.qt.__init__',
    'app.tinker_v1.app',
    'app.tinker_v1.__init__',
    'app.tinker_v2.app',
    'app.tinker_v2.__init__',
    'core.__init__',
    'core.database_manager',
    'utils.__init__',
    'utils.api_client',
    'utils.config_manager',
    'utils.logging_handlers',
    'utils.playlist_manager',
    'utils.poster_manager',
    'utils.torrent_manager',
]

a = Analysis(
    ['main.py'],  # Основной файл для запуска приложения
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'SQLAlchemy~=2.0.36',
        'requests>=2.25.1',
        'Pillow>=8.1.0',
        'PyQt5~=5.15.11 ',
        'pydantic',
        'aiohttp'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AnimePlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Использовать False, чтобы окно консоли не открывалось (для GUI)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AnimePlayer'
)
