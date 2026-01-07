# -*- mode: python ; coding: utf-8 -*-
# make_bin/main.spec
"""
Главный spec файл для сборки всех приложений.
Использование: pyinstaller make_bin/main.spec
"""
import os
import sys

# === ВАЖНО: Настройка путей ДО импортов ===
# SPECPATH - встроенная переменная PyInstaller (директория где лежит .spec файл)
spec_dir = os.path.abspath(SPECPATH)    # make_bin/ (уже директория!)
project_dir = os.path.dirname(spec_dir)  # корень проекта

# Добавляем корень проекта в sys.path для импорта make_bin
sys.path.insert(0, project_dir)
os.chdir(project_dir)

print(f"📂 Spec dir: {spec_dir}")
print(f"📂 Project dir: {project_dir}")

# === Теперь можно импортировать ===
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
    calculate_sha256,
    update_hash_in_file,
)
from make_bin.datas import get_main_app_datas, get_player_datas, get_lite_app_datas, get_hookspath
from make_bin.hiddenimports import (
    get_main_hiddenimports,
    get_vlc_hiddenimports,
    get_mpv_hiddenimports,
    get_browser_hiddenimports,
    get_lite_hiddenimports,
    get_lite_excludes,
)

# === Подготовка ===
print("\n" + "=" * 50)
print("BUILD PREPARATION")
print("=" * 50)

block_cipher = None

# Путь к хукам (hook-main.py, hook-sqlalchemy.py)
hookspath = get_hookspath()
print(f"📂 Hookspath: {hookspath}")

# Бэкап базы данных
source_db = os.path.join(DIST_DIR, "AnimePlayer", "db", "anime_player.db")
backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "db")
backup_database(source_db, backup_folder)

# Создание временного конфига
config_path = os.path.join(PROJECT_DIR, "config", "config.ini")
build_config_path = create_temp_config(config_path, {"use_git_version": "0"})

# Компиляция Python файлов
compile_directories(['app', 'storage', 'utils', 'templates', 'providers'])

# Путь к app_constants для обновления хэшей
app_py_path = os.path.join(PROJECT_DIR, 'app', 'qt', 'app_constants.py')
exe_ext = '.exe' if IS_WINDOWS else ''

# === 1. VLC Player ===
print("\n--- Building VLC Player ---")

v = Analysis(
    [SourceFiles.VLC],
    pathex=[PROJECT_DIR, PACKAGES_FOLDER],
    binaries=[],
    datas=get_player_datas(),
    hiddenimports=get_vlc_hiddenimports(),
    hookspath=hookspath,
    hooksconfig={},
    runtime_hooks=['make_bin/rthooks/rthook_pil_plugins.py'],
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

# Обновляем хэш VLC плеера
vlc_exe_path = os.path.join(DIST_DIR, AppNames.VLC, AppNames.VLC + exe_ext)
if os.path.exists(vlc_exe_path):
    vlc_hash = calculate_sha256(vlc_exe_path)
    update_hash_in_file(app_py_path, 'VLC_PLAYER_HASH', vlc_hash)

# === 2. MPV Player ===
print("\n--- Building MPV Player ---")

m = Analysis(
    [SourceFiles.MPV],
    pathex=[PROJECT_DIR, PACKAGES_FOLDER],
    binaries=[],  # libmpv-2.dll копируется в post_build
    datas=get_player_datas(),
    hiddenimports=get_mpv_hiddenimports(),
    hookspath=hookspath,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_mpv = PYZ(m.pure, m.zipped_data, cipher=block_cipher)

exe_mpv = EXE(
    pyz_mpv,
    m.scripts,
    [],
    exclude_binaries=True,
    name=AppNames.MPV,
    icon=ICON_FILE,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,
    version=version_from_dict(Versions.MPV) if IS_WINDOWS else None,
    onefile=False,
)

coll_mpv = COLLECT(
    exe_mpv,
    m.binaries,
    m.zipfiles,
    m.datas,
    strip=False,
    name=AppNames.MPV
)

# Обновляем хэш MPV плеера
mpv_exe_path = os.path.join(DIST_DIR, AppNames.MPV, AppNames.MPV + exe_ext)
if os.path.exists(mpv_exe_path):
    mpv_hash = calculate_sha256(mpv_exe_path)
    update_hash_in_file(app_py_path, 'MPV_PLAYER_HASH', mpv_hash)

# === 3. Mini Browser ===
print("\n--- Building Mini Browser ---")

mb = Analysis(
    [SourceFiles.BROWSER],
    pathex=[PROJECT_DIR, PACKAGES_FOLDER],
    binaries=[],
    datas=get_player_datas(),
    hiddenimports=get_browser_hiddenimports(),
    hookspath=hookspath,
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

# Обновляем хэш Mini Browser
mb_exe_path = os.path.join(DIST_DIR, AppNames.BROWSER, AppNames.BROWSER + exe_ext)
if os.path.exists(mb_exe_path):
    mb_hash = calculate_sha256(mb_exe_path)
    update_hash_in_file(app_py_path, 'MINI_BROWSER_HASH', mb_hash)

# === 4. Main AnimePlayer ===
print("\n--- Building Main AnimePlayer ---")

a = Analysis(
    [SourceFiles.MAIN],
    pathex=[PROJECT_DIR, PACKAGES_FOLDER],
    binaries=[],
    datas=get_main_app_datas(build_config_path),
    hiddenimports=get_main_hiddenimports(),  # Уже плоский список!
    hookspath=hookspath,  # Используем hook-main.py, hook-sqlalchemy.py
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

# === 5. AnimePlayer Lite ===
print("\n--- Building AnimePlayer Lite ---")

lite = Analysis(
    [SourceFiles.LITE],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=get_lite_app_datas(),
    hiddenimports=get_lite_hiddenimports(),
    hookspath=hookspath,
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
    console=True,
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

# === Post-build ===
print("\n--- Running Post-Build ---")
from make_bin.post_build import run_post_build
run_post_build()

print("\n" + "=" * 50)
print("BUILD COMPLETED SUCCESSFULLY!")
print("=" * 50)