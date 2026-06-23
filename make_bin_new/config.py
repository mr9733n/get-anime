# make_bin_new/config.py
"""
Build configuration for the new stack:
  - Kotlin Compose Desktop UI  (ui/)
  - Python HTTP backend server (backend/transport/http/server.py)
  - Python launcher            (make_bin_new/launcher.py)

Final distributable layout (dist/AnimePlayerNew/):
  AnimePlayerNew.exe       <- launcher (starts backend + UI, waits for exit)
  backend_http/            <- PyInstaller onedir of the HTTP backend
    backend_http.exe
    _internal/
    ...
  ui/                      <- Compose Desktop createDistributable output
    AnimePlayer.exe
    app/
    runtime/
    ...
  db/                      <- database lives here at runtime
    anime_player.db        (copied by post_build if found in project db/)
"""
import os
import sys
import platform

# === Platform ================================================================
IS_WINDOWS = sys.platform == "win32"
IS_MAC     = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")
EXE_EXT    = ".exe" if IS_WINDOWS else ""


def get_platform_name() -> str:
    return platform.system()


# === Directories =============================================================
# make_bin_new/config.py  ->  PROJECT_DIR is the parent folder
MAKE_BIN_NEW_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR      = os.path.dirname(MAKE_BIN_NEW_DIR)

# Shared dist/build roots (same as make_bin so intermediate artefacts coexist)
DIST_DIR  = os.path.join(PROJECT_DIR, "dist")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")

# Final assembled product lands here
DIST_NEW_DIR = os.path.join(DIST_DIR, "AnimePlayerNew")

# Kotlin / Gradle project root
UI_DIR = os.path.join(PROJECT_DIR, "ui")

# Where Gradle writes the distributable folder (createDistributable task)
#   composeApp/build/compose/binaries/main/app/AnimePlayer/
GRADLE_DIST_DIR = os.path.join(
    UI_DIR, "composeApp", "build", "compose", "binaries", "main", "app", "AnimePlayer"
)


# === App names ===============================================================
class AppNames:
    LAUNCHER    = "AnimePlayerNew"   # the Python launcher exe
    BACKEND_HTTP = "backend_http"    # reuses make_bin output
    UI          = "AnimePlayer"      # Compose Desktop exe name


# === Source files ============================================================
class SourceFiles:
    LAUNCHER     = os.path.join(MAKE_BIN_NEW_DIR, "launcher.py")
    BACKEND_HTTP = os.path.join(PROJECT_DIR, "backend", "transport", "http", "server.py")


# === PyInstaller specs =======================================================
class Specs:
    BACKEND_HTTP = os.path.join(PROJECT_DIR, "make_bin", "specs", "backend_http.spec")
    LAUNCHER     = os.path.join(MAKE_BIN_NEW_DIR, "specs", "launcher.spec")


# === Version info ============================================================
class Versions:
    LAUNCHER = {
        "FileVersion":       "1.0.0.0",
        "ProductVersion":    "1.0.0",
        "CompanyName":       "666s.dev",
        "FileDescription":   "AnimePlayer Launcher",
        "InternalName":      "AnimePlayerNew",
        "LegalCopyright":    "© 2025 666s.dev",
        "OriginalFilename":  "AnimePlayerNew.exe",
        "ProductName":       "AnimePlayer",
    }

    BACKEND_HTTP = {
        "FileVersion":       "1.0.0.0",
        "ProductVersion":    "1.0.0",
        "CompanyName":       "666s.dev",
        "FileDescription":   "AnimePlayer HTTP Backend",
        "InternalName":      "backend_http",
        "LegalCopyright":    "© 2025 666s.dev",
        "OriginalFilename":  "backend_http.exe",
        "ProductName":       "AnimePlayer Backend",
    }


# === Shared icon =============================================================
ICON_FILE = os.path.join(PROJECT_DIR, "favicon.ico")


# === Info print ==============================================================
if __name__ == "__main__":
    print(f"Platform  : {get_platform_name()}")
    print(f"ProjectDir: {PROJECT_DIR}")
    print(f"DistNew   : {DIST_NEW_DIR}")
    print(f"UIDir     : {UI_DIR}")
    print(f"GradleDist: {GRADLE_DIST_DIR}")
