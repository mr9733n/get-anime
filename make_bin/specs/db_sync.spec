# -*- mode: python ; coding: utf-8 -*-
# make_bin/specs/db_sync.spec
"""
Spec файл для сборки PlayerDBSync (утилита синхронизации БД).
Использование: pyinstaller make_bin/specs/db_sync.spec
"""
import glob
import os
import shutil
import site
import sys
import uuid
import tempfile

from pathlib import Path
from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files
from PyInstaller.building.build_main import Analysis

# === ВАЖНО: Настройка путей ДО импортов ===
spec_dir = os.path.abspath(SPECPATH)         # make_bin/specs/
make_bin_dir = os.path.dirname(spec_dir)      # make_bin/
project_dir = os.path.dirname(make_bin_dir)   # корень проекта

sys.path.insert(0, project_dir)
os.chdir(project_dir)

from make_bin.config import IS_WINDOWS, PACKAGES_FOLDER, DIST_DIR
from make_bin.version import version_from_dict

# === Конфигурация ===
APP_DIR = "app"
APP_DIR_NAME = "sync"
BUILD_FILE = "db_sync_gui.py"
BUILD_ONEFILE = True
BUILD_USE_ENV = False
EXCLUDE_DIRS = {"incoming"}
EXCLUDE_FILE_NAMES = {"todo.md", "requirements.txt"}
EXCLUDE_PREFIXES = ("db_snapshot",)

# Абсолютный путь к исходнику
SOURCE_FILE = os.path.join(project_dir, APP_DIR, APP_DIR_NAME, BUILD_FILE)

# === Импорт специфичных зависимостей ===
try:
    import av
    import pylibsrtp
    HAS_AV = True
except ImportError:
    HAS_AV = False
    print("⚠️ av/pylibsrtp not installed - WebRTC features disabled")

print(f"📂 Project dir: {project_dir}")
print(f"📂 Site-packages: {PACKAGES_FOLDER}")

# === Функции ===
def collect_app_datas(dir: str):
    """Собирает файлы из app/sync, исключая ненужные."""
    proj_dir = Path(dir)
    sync_root = proj_dir / APP_DIR / APP_DIR_NAME

    result = []
    for path in sync_root.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.is_dir():
            continue
        name = path.name
        if name in EXCLUDE_FILE_NAMES:
            continue
        if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            continue
        rel_inside_sync = path.relative_to(sync_root)
        rel_parent = rel_inside_sync.parent
        if rel_parent == Path("."):
            dest = APP_DIR
        else:
            dest = os.path.join(APP_DIR, str(rel_parent))
        result.append((str(path), dest))
    return result

# === Pre-build ===
env_path = Path(project_dir) / '.env'
temp_env_dir = Path(tempfile.mkdtemp(prefix="build_env_"))
build_env_path = temp_env_dir / '.env'

if BUILD_USE_ENV and env_path.exists():
    replacements = {
        "POSTMARK_API_KEY": "your_postmark_api_key_value",
        "FROM_EMAIL": "your_email@example.com",
        "TO_EMAIL": "your_email@example.com",
    }
    shutil.copy(env_path, build_env_path)
    with open(build_env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    with open(build_env_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith("USE_GIT_VERSION="):
                continue
            replaced = False
            for key, new_value in replacements.items():
                if line.startswith(key + "="):
                    f.write(f"{key}={new_value}\n")
                    replaced = True
                    break
            if not replaced:
                f.write(line)
        prod_key = str(uuid.uuid4())
        f.write(f"PROD_KEY={prod_key}\n")
        os.environ["PROD_KEY"] = prod_key
    print(f"✅ Temporary .env file created: {build_env_path}")

block_cipher = None
icon_path = os.path.join(project_dir, "favicon.ico")

print(f"📂 Source file: {SOURCE_FILE}")
print(f"📂 Icon: {icon_path}")

# ============================================
# PlayerDBSync Full (with WebRTC)
# ============================================
print("\n--- Building PlayerDBSync Full ---")

VERSION_FULL = {
    "FileVersion": "0.0.0.1",
    "ProductVersion": "0.0.0.1",
    "CompanyName": "666s.dev",
    "FileDescription": "AnimePlayerDBSyncUtilityApp",
    "InternalName": "AnimePlayerDBSyncUtilityApp",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "PlayerDBSync.exe",
    "ProductName": "AnimePlayerDBSyncUtilityApp",
}

hidden = []
datas = []
binaries = []

# PyNaCl / cffi
hidden += collect_submodules("nacl")
hidden += ["_cffi_backend", "cffi", "cffi.backend_ctypes"]
binaries += collect_dynamic_libs("nacl")
binaries += collect_dynamic_libs("cffi")

# zeroconf
datas += collect_data_files("zeroconf", include_py_files=True)
hidden += collect_submodules("zeroconf")
binaries += collect_dynamic_libs("zeroconf")

# Tkinter: TCL/TK data
tcl_base = os.path.join(sys.base_prefix, "tcl")
tcl86 = os.path.join(tcl_base, "tcl8.6")
tk86 = os.path.join(tcl_base, "tk8.6")
if os.path.isdir(tcl86) and os.path.isdir(tk86):
    datas += [(tcl86, "tcl/tcl8.6")]
    datas += [(tk86, "tcl/tk8.6")]

# av/pylibsrtp (WebRTC)
if HAS_AV:
    datas += [(str(Path(av.__file__).parent), "av")]
    datas += [(str(Path(pylibsrtp.__file__).parent), "pylibsrtp")]

datas += collect_app_datas(project_dir)
datas += [(icon_path, ".")]
if BUILD_USE_ENV:
    datas += [(str(build_env_path), ".")]

a = Analysis(
    [SOURCE_FILE],
    pathex=[project_dir, PACKAGES_FOLDER],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden + [
        "zeroconf", "nacl", "aiortc", "aioice", "aiofiles",
        "av", "pyee", "pylibsrtp", "crc32c",
        "tkinter", "tkinter.ttk"
    ],
    hookspath=[project_dir],
    runtime_hooks=[],
    excludes=['PIL', 'numpy', 'psutils'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if BUILD_ONEFILE:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name='PlayerDBSync',
        icon=icon_path,
        console=False,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        version=version_from_dict(VERSION_FULL) if IS_WINDOWS else None,
        onefile=True
    )
else:
    exe = EXE(
        pyz,
        exclude_binaries=True,
        name='PlayerDBSync',
        icon=icon_path,
        console=False,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        version=version_from_dict(VERSION_FULL) if IS_WINDOWS else None,
        onefile=False
    )
    coll = COLLECT(
        exe, a.scripts, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=True, upx_exclude=[], name='PlayerDBSync'
    )

# ============================================
# PlayerDBSyncLAN (LAN only, no WebRTC)
# ============================================
print("\n--- Building PlayerDBSyncLAN ---")

VERSION_LAN = {
    "FileVersion": "0.0.0.1",
    "ProductVersion": "0.0.0.1",
    "CompanyName": "666s.dev",
    "FileDescription": "AnimePlayerDBSyncLANUtilityApp",
    "InternalName": "AnimePlayerDBSyncLANUtilityApp",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "PlayerDBSyncLAN.exe",
    "ProductName": "AnimePlayerDBSyncLANUtilityApp",
}

hidden2 = []
datas2 = []
binaries2 = []

# PyNaCl / cffi
hidden2 += collect_submodules("nacl")
hidden2 += ["_cffi_backend", "cffi", "cffi.backend_ctypes"]
binaries2 += collect_dynamic_libs("nacl")
binaries2 += collect_dynamic_libs("cffi")

# zeroconf
datas2 += collect_data_files("zeroconf", include_py_files=True)
hidden2 += collect_submodules("zeroconf")
binaries2 += collect_dynamic_libs("zeroconf")

# Tkinter
if os.path.isdir(tcl86) and os.path.isdir(tk86):
    datas2 += [(tcl86, "tcl/tcl8.6")]
    datas2 += [(tk86, "tcl/tk8.6")]

datas2 += collect_app_datas(project_dir)
datas2 += [(icon_path, ".")]

a2 = Analysis(
    [SOURCE_FILE],
    pathex=[project_dir, PACKAGES_FOLDER],
    binaries=binaries2,
    datas=datas2,
    hiddenimports=hidden2 + ['nacl', 'zeroconf', 'aiofiles', 'tkinter', 'tkinter.ttk'],
    hookspath=[project_dir],
    runtime_hooks=[],
    excludes=['PIL', 'numpy', 'psutils', 'av', 'pylibsrtp'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz2 = PYZ(a2.pure, a2.zipped_data, cipher=block_cipher)

if BUILD_ONEFILE:
    exe2 = EXE(
        pyz2, a2.scripts, a2.binaries, a2.zipfiles, a2.datas, [],
        name='PlayerDBSyncLAN',
        icon=icon_path,
        console=False,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        version=version_from_dict(VERSION_LAN) if IS_WINDOWS else None,
        onefile=True
    )
else:
    exe2 = EXE(
        pyz2,
        exclude_binaries=True,
        name='PlayerDBSyncLAN',
        icon=icon_path,
        console=False,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        version=version_from_dict(VERSION_LAN) if IS_WINDOWS else None,
        onefile=False
    )
    coll2 = COLLECT(
        exe2, a2.scripts, a2.binaries, a2.zipfiles, a2.datas,
        strip=False, upx=True, upx_exclude=[], name='PlayerDBSyncLAN'
    )

# ============================================
# Post Build - копируем в AnimePlayer
# ============================================
print("\n--- Post Build: Copy to AnimePlayer ---")

dist_dir = Path(project_dir) / "dist"
anime_player_dir = dist_dir / "AnimePlayer"

def copy_file(src: Path, dst_dir: Path):
    if not src.exists() or not src.is_file():
        print(f"⚠️ Skip copy: {src} not found")
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    print(f"📄 Copied: {src.name} → {dst_dir}")

def copy_tree(src: Path, dst: Path):
    if not src.exists() or not src.is_dir():
        print(f"⚠️ Skip copy: {src} not found")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"📁 Copied folder: {src.name} → {dst}")

# Копируем exe в AnimePlayer
if anime_player_dir.exists():
    copy_file(dist_dir / "PlayerDBSync.exe", anime_player_dir)
    copy_file(dist_dir / "PlayerDBSyncLAN.exe", anime_player_dir)
    copy_tree(Path(project_dir) / "app/sync/scripts", anime_player_dir / "scripts")
else:
    print(f"⚠️ AnimePlayer not found at {anime_player_dir}, skipping copy")

print("\n✅ PlayerDBSync build completed!")