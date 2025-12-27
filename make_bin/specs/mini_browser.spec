# -*- mode: python ; coding: utf-8 -*-
# make_bin/specs/mini_browser.spec
"""
Spec файл для сборки Mini Browser.
Использование: pyinstaller make_bin/specs/mini_browser.spec
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
from make_bin.datas import get_player_datas
from make_bin.hiddenimports import get_browser_hiddenimports
from make_bin.utils import calculate_sha256, update_hash_in_file

block_cipher = None

print("\n--- Building Mini Browser ---")

mb = Analysis(
    [SourceFiles.BROWSER],
    pathex=[PROJECT_DIR, PACKAGES_FOLDER],
    binaries=[],
    datas=get_player_datas(),
    hiddenimports=get_browser_hiddenimports(),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_mb = PYZ(mb.pure, mb.zipped_data, cipher=block_cipher)

exe_mb = EXE(
    pyz_mb,
    mb.scripts,
    [],
    exclude_binaries=True,
    name=AppNames.BROWSER,
    icon=ICON_FILE,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,
    version=version_from_dict(Versions.BROWSER) if IS_WINDOWS else None,
    onefile=False,
)

coll_mb = COLLECT(
    exe_mb,
    mb.binaries,
    mb.zipfiles,
    mb.datas,
    strip=False,
    name=AppNames.BROWSER
)

# Обновляем хэш
exe_ext = '.exe' if IS_WINDOWS else ''
mb_exe_path = os.path.join(DIST_DIR, AppNames.BROWSER, AppNames.BROWSER + exe_ext)
if os.path.exists(mb_exe_path):
    mb_hash = calculate_sha256(mb_exe_path)
    app_py_path = os.path.join(PROJECT_DIR, 'app', 'qt', 'app.py')
    update_hash_in_file(app_py_path, 'MINI_BROWSER_HASH', mb_hash)

print(f"✅ Mini Browser built: {DIST_DIR}/{AppNames.BROWSER}")