# make_bin_new/post_build.py
"""
Assembles the final dist/AnimePlayerNew/ distributable from the three
independently-built components:

  1. backend_http  — PyInstaller onedir  (dist/backend_http/)
  2. UI            — Gradle distributable (ui/composeApp/build/compose/...)
  3. launcher      — PyInstaller onefile  (dist/AnimePlayerNew_launcher/)

Final layout:
  dist/AnimePlayerNew/
    AnimePlayerNew.exe       <- launcher
    backend_http/            <- full PyInstaller onedir (exe + _internal)
    ui/                      <- Gradle distributable tree
    db/                      <- empty dir (DB created by backend on first run)
    config/                  <- backend config copied from project config/
      config.ini
      logging.conf

Run:
    python -m make_bin_new.post_build
"""
from __future__ import annotations

import os
import shutil
import stat
import sys

# ---------------------------------------------------------------------------
# Locate project root regardless of cwd
# ---------------------------------------------------------------------------
THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(THIS_DIR)
sys.path.insert(0, PROJECT_DIR)

from make_bin_new.config import (
    DIST_DIR, DIST_NEW_DIR, GRADLE_DIST_DIR, AppNames, EXE_EXT,
)

# ---------------------------------------------------------------------------
# Source paths (produced by individual build steps)
# ---------------------------------------------------------------------------
BACKEND_SRC   = os.path.join(DIST_DIR, "backend_http")
LAUNCHER_SRC  = os.path.join(DIST_DIR, f"AnimePlayerNew{EXE_EXT}")   # onefile
CONFIG_SRC    = os.path.join(PROJECT_DIR, "config")
DB_SRC        = os.path.join(PROJECT_DIR, "db", "anime_player.db")   # optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rmtree_force(path: str) -> None:
    """
    Remove a directory tree on Windows even when files are read-only.

    Gradle's distributable (and some PyInstaller outputs) mark files as
    read-only.  shutil.rmtree raises PermissionError / WinError 5 on those.
    The onexc callback clears the read-only bit and retries the failing op.
    """
    def _on_exc(func, failing_path, exc):
        try:
            os.chmod(failing_path, stat.S_IWRITE)
            func(failing_path)
        except Exception:
            pass  # ignore; rmtree will raise the original error if it matters

    shutil.rmtree(path, onexc=_on_exc)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")


def _err(msg: str) -> None:
    print(f"  ❌ {msg}")


def _require(path: str, label: str) -> bool:
    if os.path.exists(path):
        return True
    _err(f"{label} not found: {path}")
    return False


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def step_prepare() -> None:
    print("\n[1] Prepare output directory")
    if os.path.exists(DIST_NEW_DIR):
        _rmtree_force(DIST_NEW_DIR)
    os.makedirs(DIST_NEW_DIR, exist_ok=True)
    _ok(f"Created: {DIST_NEW_DIR}")


def step_copy_backend() -> bool:
    print("\n[2] Copy backend_http (PyInstaller onedir)")
    if not _require(BACKEND_SRC, "backend_http dist folder"):
        return False
    dst = os.path.join(DIST_NEW_DIR, "backend_http")
    shutil.copytree(BACKEND_SRC, dst)
    _ok(f"Copied → {dst}")
    return True


def step_copy_ui() -> bool:
    print("\n[3] Copy Compose Desktop UI (Gradle distributable)")
    if not _require(GRADLE_DIST_DIR, "Gradle distributable folder"):
        return False
    dst = os.path.join(DIST_NEW_DIR, "ui")
    shutil.copytree(GRADLE_DIST_DIR, dst)
    _ok(f"Copied → {dst}")
    return True


def step_copy_launcher() -> bool:
    print("\n[4] Copy launcher executable")
    if not _require(LAUNCHER_SRC, "launcher exe"):
        return False
    dst = os.path.join(DIST_NEW_DIR, f"AnimePlayerNew{EXE_EXT}")
    shutil.copy2(LAUNCHER_SRC, dst)
    _ok(f"Copied → {dst}")
    return True


def step_copy_config() -> None:
    print("\n[5] Copy backend config")
    dst = os.path.join(DIST_NEW_DIR, "config")
    if os.path.isdir(CONFIG_SRC):
        shutil.copytree(CONFIG_SRC, dst, dirs_exist_ok=True)
        _ok(f"Copied config/ → {dst}")
    else:
        os.makedirs(dst, exist_ok=True)
        _warn("config/ source not found — empty dir created")


def step_copy_db() -> None:
    print("\n[6] Copy database (optional)")
    db_dst_dir = os.path.join(DIST_NEW_DIR, "db")
    os.makedirs(db_dst_dir, exist_ok=True)
    if os.path.isfile(DB_SRC):
        shutil.copy2(DB_SRC, os.path.join(db_dst_dir, "anime_player.db"))
        _ok(f"Copied anime_player.db → {db_dst_dir}")
    else:
        _warn("db/anime_player.db not found in project root — empty db/ dir created")
        _warn("The backend will create a fresh database on first run.")


def step_summary() -> None:
    print("\n" + "=" * 60)
    print("DIST LAYOUT")
    print("=" * 60)
    for root, dirs, files in os.walk(DIST_NEW_DIR):
        depth = root.replace(DIST_NEW_DIR, "").count(os.sep)
        indent = "  " * depth
        folder_name = os.path.basename(root)
        print(f"{indent}{folder_name}/")
        sub_indent = "  " * (depth + 1)
        for f in files:
            size = os.path.getsize(os.path.join(root, f))
            print(f"{sub_indent}{f}  ({size // 1024} KB)")
        # Limit deep nesting noise
        if depth >= 2:
            dirs[:] = []


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_post_build() -> None:
    print("=" * 60)
    print("POST-BUILD  (new stack)")
    print("=" * 60)

    step_prepare()
    ok_backend  = step_copy_backend()
    ok_ui       = step_copy_ui()
    ok_launcher = step_copy_launcher()
    step_copy_config()
    step_copy_db()

    print("\n" + "=" * 60)
    failed = [
        name for name, ok in [
            ("backend_http", ok_backend),
            ("UI",           ok_ui),
            ("launcher",     ok_launcher),
        ] if not ok
    ]
    if failed:
        _err(f"Missing components: {', '.join(failed)}")
        _err("Run the corresponding build steps first (make_new.bat backend / ui / launcher)")
        sys.exit(1)
    else:
        step_summary()
        print("\n✅ AnimePlayerNew assembled successfully")
        print(f"   → {DIST_NEW_DIR}")
        print("=" * 60)


if __name__ == "__main__":
    run_post_build()
