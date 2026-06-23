# -*- mode: python ; coding: utf-8 -*-
# make_bin_new/specs/launcher.spec
"""
Build the AnimePlayer Launcher as a standalone single-file executable.

Usage (from project root):
    pyinstaller make_bin_new/specs/launcher.spec

Result:
    dist/AnimePlayerNew.exe   (one-file, no _internal/ directory)

ONE-FILE BUILD
--------------
Pass a.binaries / a.zipfiles / a.datas directly into EXE with no COLLECT.
That is the spec-file equivalent of `--onefile`.
(`onefile=True` is a CLI flag only — NOT a valid EXE() keyword.)

WHY SO MANY hiddenimports?
---------------------------
PyInstaller injects the `pyi_rth_pkgres` runtime hook whenever its default
hook for `pkg_resources` fires.  That hook runs at process start — before any
application code — and walks this import chain:

  pkg_resources
    → setuptools._vendor.jaraco.text
      → setuptools._vendor.jaraco.context
        → urllib.request          (line 88)
          → http.client           ← MISSING → crash

Hidden imports in a spec are added verbatim; their own transitive imports are
NOT followed by PyInstaller's analyser.  So listing "urllib.request" is not
enough — we must also list every stdlib module it imports.

We use collect_submodules() for http / urllib / email / html so that if Python
or setuptools' vendored copy of jaraco adds a new import we don't have to
manually track it.
"""

import os
import sys

spec_dir     = os.path.abspath(SPECPATH)          # make_bin_new/specs/
make_new_dir = os.path.dirname(spec_dir)          # make_bin_new/
project_dir  = os.path.dirname(make_new_dir)      # project root

sys.path.insert(0, project_dir)
os.chdir(project_dir)

from PyInstaller.building.api import PYZ, EXE
from PyInstaller.building.build_main import Analysis

icon_file = os.path.join(project_dir, "favicon.ico")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [
        os.path.join(make_new_dir, "launcher.py"),
        # Statically analysed so PyInstaller walks the full http/urllib/email
        # import graph — the only reliable way to get http.client into the bundle.
        os.path.join(project_dir, "make_bin", "stubs", "preimport_stdlib.py"),
    ],
    pathex=[project_dir, make_new_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        "socket",
        "signal",
        "subprocess",
        "argparse",
        "logging",
        "logging.handlers",
    ],
    hookspath=[os.path.join(project_dir, "make_bin", "hooks")],
    hooksconfig={},
    runtime_hooks=[
        # Must be listed FIRST — runs before pyi_rth_pkgres and pre-loads the
        # http / urllib / email chain so pyi_rth_pkgres never hits a missing
        # http.client (Python 3.13 frozen-module issue).
        os.path.join(project_dir, "make_bin", "rthooks", "rthook_fix_http_client.py"),
    ],
    excludes=[
        # setuptools / pkg_resources — not needed by this tiny launcher.
        # Excluding them prevents PyInstaller from injecting pyi_rth_pkgres,
        # eliminating the http.client import chain entirely.
        "setuptools",
        "pkg_resources",
        # Heavy third-party stacks not needed in this tiny launcher
        "PyQt5", "PyQt6", "PySide6",
        "sqlalchemy", "fastapi", "uvicorn",
        "PIL", "scipy", "matplotlib", "pandas",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# ---------------------------------------------------------------------------
# One-file EXE — no COLLECT call.
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AnimePlayerNew",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    icon=icon_file if os.path.isfile(icon_file) else None,
)
