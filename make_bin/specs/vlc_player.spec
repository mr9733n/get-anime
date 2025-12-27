# -*- mode: python ; coding: utf-8 -*-
# make_bin/specs/vlc_player.spec
"""
Spec файл для сборки VLC Player.
Использование: pyinstaller make_bin/specs/vlc_player.spec
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
from make_bin.hiddenimports import get_vlc_hiddenimports
from make_bin.utils import calculate_sha256, update_hash_in_file

block_cipher = None

print("\n--- Building VLC Player ---")

v = Analysis(
    [SourceFiles.VLC],
    pathex=[PROJECT_DIR, PACKAGES_FOLDER],
    binaries=[],
    datas=get_player_datas(),
    hiddenimports=get_vlc_hiddenimports(),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_vlc = PYZ(v.pure, v.zipped_data, cipher=block_cipher)

exe_vlc = EXE(
    pyz_vlc,
    v.scripts,
    [],
    exclude_binaries=True,
    name=AppNames.VLC,
    icon=ICON_FILE,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,
    version=version_from_dict(Versions.VLC) if IS_WINDOWS else None,
    onefile=False,
)

coll_vlc = COLLECT(
    exe_vlc,
    v.binaries,
    v.zipfiles,
    v.datas,
    strip=False,
    name=AppNames.VLC
)

# Обновляем хэш
exe_ext = '.exe' if IS_WINDOWS else ''
vlc_exe_path = os.path.join(DIST_DIR, AppNames.VLC, AppNames.VLC + exe_ext)
if os.path.exists(vlc_exe_path):
    vlc_hash = calculate_sha256(vlc_exe_path)
    app_py_path = os.path.join(PROJECT_DIR, 'app', 'qt', 'app.py')
    update_hash_in_file(app_py_path, 'VLC_PLAYER_HASH', vlc_hash)

print(f"✅ VLC Player built: {DIST_DIR}/{AppNames.VLC}")