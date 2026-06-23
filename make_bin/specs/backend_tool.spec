# -*- mode: python ; coding: utf-8 -*-
# make_bin/specs/backend_tool.spec
"""
Build the JSON-tool CLI backend as a standalone binary.

Used by the Desktop UI: the UI spawns this process, writes a JSON request to
stdin, and reads the JSON response from stdout.

Usage (from project root):
    pyinstaller make_bin/specs/backend_tool.spec

Result:
    dist/backend_tool/backend_tool(.exe)

Integrate with Desktop UI (DesktopApp.kt):
    val proc = ProcessBuilder("dist/backend_tool/backend_tool", "--db", dbPath)
        .redirectErrorStream(true)
        .start()

IMPORTANT: WorkingDirectory must be the project root when running from source.
"""

import os
import sys

spec_dir = os.path.abspath(SPECPATH)
project_dir = os.path.dirname(os.path.dirname(spec_dir))

sys.path.insert(0, project_dir)
os.chdir(project_dir)

from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.building.build_main import Analysis

IS_WINDOWS = sys.platform == "win32"

datas = [
    (os.path.join(project_dir, "storage"),     "storage"),
    (os.path.join(project_dir, "utils"),       "utils"),
    (os.path.join(project_dir, "providers"),   "providers"),
    (os.path.join(project_dir, "backend"),     "backend"),
    (os.path.join(project_dir, "config", "config.ini"),   "config"),
    (os.path.join(project_dir, "config", "logging.conf"), "config"),
]

hidden_imports = [
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.orm",
    "requests",
    "urllib3",
    "PIL",
    "PIL.Image",
    "storage",
    "storage.database_manager",
    "storage.tables",
    "utils.config.config_manager",
    "utils.net.net_client",
    "utils.playlists.playlist_manager",
    "utils.downloads.poster_manager",
    "providers.aniliberty",
    "providers.aniliberty.v1",
    "providers.aniliberty.v1.api",
    "providers.aniliberty.v1.adapter",
    "providers.animedia",
    "providers.animedia.v0",
    "backend.bootstrap.standalone",
    "backend.core.standalone_backend",
    "backend.transport.json_tool.backend_tool",
    "backend.transport.json_tool.handlers",
]

a = Analysis(
    [os.path.join(project_dir, "backend", "transport", "json_tool", "backend_tool.py")],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[os.path.join(project_dir, "make_bin", "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5", "PyQt6", "PySide6", "PySide2",
        "fastapi", "uvicorn", "kivy", "tkinter",
        "scipy", "matplotlib", "pandas",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend_tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="backend_tool",
)
