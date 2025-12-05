# -*- mode: python ; coding: utf-8 -*-
# For python version 3.12.x

import os
import platform
import re
import site
import sys
import uuid
import glob
import shutil
import hashlib
import tempfile
import compileall

from datetime import datetime
from pathlib import Path

import playwright
from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct

APP_DIR = "app"
APP_DIR_NAME = "_animedia"
BUILD_FILE = "demo.py"
EXCLUDE_DIRS = {"playlists"}
EXCLUDE_FILE_NAMES = {"requirements.txt",}
EXCLUDE_PREFIXES = ("",)

# Compatibility shim: PyInstaller 6.x removed 'Version'. Build VSVersionInfo from simple kwargs.
def Version(*, file_version, product_version, company_name, file_description, internal_name, legal_copyright, original_filename, product_name):
    def _tuple4(v):
        parts = [int(p) for p in str(v).split('.') if p.isdigit()]
        parts = (parts + [0,0,0,0])[:4]
        return tuple(parts)
    filevers = _tuple4(file_version)
    prodvers = _tuple4(product_version)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=filevers,
            prodvers=prodvers,
            mask=0x3f,
            flags=0x0,
            OS=0x4,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                StringTable('040904B0', [
                    StringStruct('CompanyName', company_name),
                    StringStruct('FileDescription', file_description),
                    StringStruct('FileVersion', str(file_version)),
                    StringStruct('InternalName', internal_name),
                    StringStruct('LegalCopyright', legal_copyright),
                    StringStruct('OriginalFilename', original_filename),
                    StringStruct('ProductName', product_name),
                    StringStruct('ProductVersion', str(product_version)),
                ])
            ]),
            VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
        ]
    )

def collect_app_datas(dir: str):
    project_dir = Path(dir)
    sync_root = project_dir / APP_DIR / APP_DIR_NAME

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

# ---
# animedia_player_demo.spec

def calculate_sha256(file_path):
    hash_function = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_function.update(chunk)
    return hash_function.hexdigest()

def current_platform():
    cur_pl = platform.system()
    return cur_pl

if sys.platform == "win32":
    # Windows: using site.getsitepackages()
    python_root = site.getsitepackages()[0]
    PACKAGES_FOLDER = os.path.join(python_root, "Lib", "site-packages")
else:
    # macOS/Linux: at first using site.getsitepackages(), else sysconfig
    try:
        PACKAGES_FOLDER = site.getsitepackages()[0]
    except AttributeError:
        import sysconfig
        PACKAGES_FOLDER = sysconfig.get_paths()["purelib"]

print(f"📂 Site-packages folder: {PACKAGES_FOLDER}")

project_dir = os.getcwd()

# Compile the files in the 'app' directory
compileall.compile_dir(APP_DIR, force=True)

block_cipher = None

block = {
    "FileVersion": "0.0.0.1",
    "ProductVersion": "0.0.1",
    "CompanyName": "666s.dev",
    "FileDescription": "AniMediaPlayerDemo",
    "InternalName": "AniMediaPlayerDemo",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "AniMediaPlayerDemo.exe",
    "ProductName": "AniMediaPlayerDemo",
}

version_resource = Version(
    file_version=block["FileVersion"],
    product_version=block["ProductVersion"],
    company_name=block["CompanyName"],
    file_description=block["FileDescription"],
    internal_name=block["InternalName"],
    legal_copyright=block["LegalCopyright"],
    original_filename=block["OriginalFilename"],
    product_name=block["ProductName"],
)
datas = []
playwright_dir = Path(playwright.__file__).parent
browsers_dir = playwright_dir / "driver" / "package" / ".local-browsers"

if browsers_dir.exists():
    datas.append((
        str(browsers_dir),
        "playwright/driver/package/.local-browsers"
    ))
datas += collect_app_datas(project_dir)
datas += [(os.path.join(project_dir, 'app/_animedia/__pycache__'), 'app/__pycache__')]  # Add compiled .pyc files
datas += [(os.path.join(project_dir, 'favicon.ico'), '.')]

d = Analysis([f"{APP_DIR}/{APP_DIR_NAME}/{BUILD_FILE}"],
    pathex=[
        project_dir,
        PACKAGES_FOLDER,
        ],
    binaries=[],
    datas=datas,
    hiddenimports=['beautifulsoup4', 'playwright', 'httpx', 'qasync'],
    hookspath=[],
    runtime_hooks=[],
    excludes=["cryptography", "numpy", "PyQt5"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(d.pure, d.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
	d.scripts,
	[],
	exclude_binaries=True,
    name='AniMediaPlayerDemo',
	icon='favicon.ico',
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	console=True,
    version=version_resource,
	onefile=False,  # Important for imports to set to False to keep everything in the same folder
)

coll = COLLECT(
    exe,
	d.binaries,
	d.zipfiles,
	d.datas,
	strip=False,
	name='AniMediaPlayerDemo'
)

dist_dir = os.path.join(project_dir, 'dist')
compiled_dir2 = os.path.join(dist_dir, 'AniMediaPlayerDemo', '_internal')

def delete_folders(target_dir, folder_patterns):
    for pattern in folder_patterns:
        full_pattern = os.path.join(target_dir, pattern)
        for folder_path in glob.glob(full_pattern):
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)
                print(f"✅ Deleted: {folder_path}")

folders_to_delete = {
    compiled_dir2: [
        "importlib_metadata-*.dist-info",
        "MarkupSafe-*.dist-info",
        "numpy-*.dist-info",
        "h2-*.dist-info",
        "cryptography-*.dist-info",
        "attrs-*.dist-info",
        "cryptography",  # security vendor flagged this file as malicious by VirusTotal
        "charset_normalizer",  # security vendor flagged this file as malicious by VirusTotal
        "markupsafe",  # security vendor flagged this file as malicious by VirusTotal
    ],
}

for target_dir, patterns in folders_to_delete.items():
    delete_folders(target_dir, patterns)

def delete_files(target_dir, file_patterns):
    for pattern in file_patterns:
        full_pattern = os.path.join(target_dir, pattern)
        for file_path in glob.glob(full_pattern):
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    print(f"✅ Deleted file: {file_path}")
                except Exception as e:
                    print(f"❌ Error deleting {file_path}: {e}")
            else:
                print(f"⚠️ Skipping non-file: {file_path}")

target_folders = []
files_to_delete = []
files_to_delete += [
    "_imagingtk.cp312-win_amd64.pyd", # security vendor flagged this file as malicious by VirusTotal
    "_webp.cp312-win_amd64.pyd", # security vendor flagged this file as malicious by VirusTotal
]

target_folders += os.path.join(compiled_dir2, "app")
files_to_delete += [
    "requirements.txt",
]

for target_folder in target_folders:
    delete_files(target_folder, files_to_delete)

dest_dir1 = os.path.join(dist_dir, 'AniMediaPlayerDemo')

folders_mapping = {
    compiled_dir2: (
        dest_dir1,
        [
            "app",
        ],
    ),
}

folders_to_move = {
    compiled_dir2: [

    ],
}

def move_folders(mapping):
    for src_root, (dest_root, patterns) in mapping.items():
        for pattern in patterns:
            full_pattern = os.path.join(src_root, pattern)
            for src_path in glob.glob(full_pattern):
                if not os.path.isdir(src_path):
                    continue
                name = os.path.basename(src_path.rstrip(r"\/"))
                dst_path = os.path.join(dest_root, name)

                if not os.path.exists(src_path):
                    continue

                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                print(f"➡️ move {src_path} → {dst_path}")
                shutil.move(src_path, dst_path)

move_folders(folders_mapping)