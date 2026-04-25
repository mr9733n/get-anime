# -*- mode: python ; coding: utf-8 -*-
# make_bin/specs/backend_http.spec
"""
Build the HTTP backend server as a standalone binary.

Usage (from project root):
    pyinstaller make_bin/specs/backend_http.spec

Result:
    dist/backend_http/backend_http(.exe)

Run the binary:
    dist/backend_http/backend_http --db db/anime_player.db --port 8765
    dist/backend_http/backend_http --db db/anime_player.db --port 8765 --host 0.0.0.0

The binary bundles storage/, utils/, providers/ and backend/ so it can be
deployed without a Python environment.  Copy the whole dist/backend_http/
folder to the target machine.

IMPORTANT: WorkingDirectory (systemd) / Start-in (Task Scheduler) must be the
project root — NOT the backend/ subdirectory.  The binary expects to find
config/config.ini relative to cwd.
"""

import os
import sys

spec_dir = os.path.abspath(SPECPATH)           # make_bin/specs/
project_dir = os.path.dirname(os.path.dirname(spec_dir))  # project root

sys.path.insert(0, project_dir)
os.chdir(project_dir)

from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.building.build_main import Analysis

IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Data files bundled into the binary
# ---------------------------------------------------------------------------
datas = [
    # Runtime packages — included as plain source trees so Python can import them
    (os.path.join(project_dir, "storage"),         "storage"),
    (os.path.join(project_dir, "utils"),           "utils"),
    (os.path.join(project_dir, "providers"),       "providers"),
    (os.path.join(project_dir, "backend"),         "backend"),

    # Default config (user can override at runtime)
    (os.path.join(project_dir, "config", "config.ini"),       "config"),
    (os.path.join(project_dir, "config", "logging.conf"),     "config"),
]

# ---------------------------------------------------------------------------
# Hidden imports — packages auto-discovery misses
# ---------------------------------------------------------------------------
hidden_imports = [
    # FastAPI / Uvicorn
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # Pydantic
    "pydantic",
    "pydantic.deprecated",
    "pydantic.v1",
    # SQLAlchemy
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.orm",
    # HTTP / networking
    "requests",
    "urllib3",
    # PIL (poster image validation)
    "PIL",
    "PIL.Image",
    # Storage / utils
    "storage",
    "storage.database_manager",
    "storage.tables",
    "utils.config.config_manager",
    "utils.net.net_client",
    "utils.playlists.playlist_manager",
    "utils.downloads.poster_manager",
    # Providers
    "providers.aniliberty",
    "providers.aniliberty.v1",
    "providers.aniliberty.v1.api",
    "providers.aniliberty.v1.adapter",
    "providers.animedia",
    "providers.animedia.v0",
    # Backend
    "backend.bootstrap.standalone",
    "backend.core.standalone_backend",
    "backend.transport.http.server",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(project_dir, "backend", "transport", "http", "server.py")],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[os.path.join(project_dir, "make_bin", "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Qt / UI — not needed in backend binary
        "PyQt5", "PyQt6", "PySide6", "PySide2",
        "kivy", "tkinter",
        # Large numeric stacks not required
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
    name="backend_http",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,      # HTTP server always runs as a console app
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="backend_http",
)
