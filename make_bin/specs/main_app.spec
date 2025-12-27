# -*- mode: python ; coding: utf-8 -*-
# make_bin/specs/main_app.spec
"""
Spec файл для сборки основного AnimePlayer.
Использование: pyinstaller make_bin/specs/main_app.spec
"""
import os
import sys

# === ВАЖНО: Настройка путей ДО импортов ===
# SPECPATH - директория где лежит .spec файл (make_bin/specs/)
spec_dir = os.path.abspath(SPECPATH)     # make_bin/specs/
make_bin_dir = os.path.dirname(spec_dir)  # make_bin/
project_dir = os.path.dirname(make_bin_dir)  # корень проекта

sys.path.insert(0, project_dir)
os.chdir(project_dir)

from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.building.build_main import Analysis

from make_bin.config import (
    PROJECT_DIR, PACKAGES_FOLDER, DIST_DIR,
    AppNames, SourceFiles, Versions, ICON_FILE, IS_WINDOWS
)
from make_bin.version import version_from_dict
from make_bin.utils import (
    compile_directories,
    backup_database,
    create_temp_config,
)
from make_bin.datas import get_main_app_datas
from make_bin.hiddenimports import get_main_hiddenimports

block_cipher = None

print("\n--- Building Main AnimePlayer ---")

# Подготовка
backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "db")
source_db = os.path.join(DIST_DIR, "AnimePlayer", "db", "anime_player.db")
backup_database(source_db, backup_folder)

config_path = os.path.join(PROJECT_DIR, "config", "config.ini")
build_config_path = create_temp_config(config_path, {"USE_GIT_VERSION": "0"})

compile_directories(['app', 'core', 'utils', 'templates', 'providers'])

# Analysis
a = Analysis(
    [SourceFiles.MAIN],
    pathex=[PROJECT_DIR, PACKAGES_FOLDER],
    binaries=[],
    datas=get_main_app_datas(build_config_path),
    hiddenimports=get_main_hiddenimports(),
    hookspath=['.'],
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
    name=AppNames.MAIN,
    icon=ICON_FILE,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,
    version=version_from_dict(Versions.MAIN) if IS_WINDOWS else None,
    onefile=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    name=AppNames.MAIN
)

print(f"✅ Main AnimePlayer built: {DIST_DIR}/{AppNames.MAIN}")