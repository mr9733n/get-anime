# -*- mode: python ; coding: utf-8 -*-
# make_bin/specs/lite_app.spec
"""
Spec файл для сборки AnimePlayer Lite.
Использование: pyinstaller make_bin/specs/lite_app.spec
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
    PROJECT_DIR, DIST_DIR,
    AppNames, SourceFiles, Versions, ICON_FILE, IS_WINDOWS
)
from make_bin.version import version_from_dict
from make_bin.datas import get_lite_app_datas
from make_bin.hiddenimports import get_lite_hiddenimports, get_lite_excludes

block_cipher = None

print("\n--- Building AnimePlayer Lite ---")

lite = Analysis(
    [SourceFiles.LITE],
    pathex=['.'],
    binaries=[],
    datas=get_lite_app_datas(),
    hiddenimports=get_lite_hiddenimports(),
    hookspath=[],
    runtime_hooks=[],
    excludes=get_lite_excludes(),
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz_lite = PYZ(lite.pure, lite.zipped_data, cipher=block_cipher)

exe_lite = EXE(
    pyz_lite,
    lite.scripts,
    [],
    exclude_binaries=True,
    name=AppNames.LITE,
    icon=ICON_FILE,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=True,  # Lite версия с консолью
    version=version_from_dict(Versions.LITE) if IS_WINDOWS else None,
    onefile=False,
)

coll_lite = COLLECT(
    exe_lite,
    lite.binaries,
    lite.zipfiles,
    lite.datas,
    strip=False,
    name=AppNames.LITE
)

print(f"✅ AnimePlayer Lite built: {DIST_DIR}/{AppNames.LITE}")