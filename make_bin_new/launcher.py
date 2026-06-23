"""
AnimePlayer Launcher
====================
Starts the HTTP backend server, waits until it is ready, then launches the
Compose Desktop UI.  Keeps running until the UI exits and shuts down the
backend cleanly.

Expected directory layout next to this executable (or next to launcher.py):

  AnimePlayerNew.exe   <- this launcher
  backend_http/
    backend_http.exe
  ui/
    AnimePlayer.exe
  db/
    anime_player.db    <- created automatically by backend on first run

Usage:
  AnimePlayerNew.exe [--port PORT] [--host HOST] [--db PATH]

The defaults (port 8765, host 127.0.0.1, db ./db/anime_player.db) match the
Compose Desktop UI's default connection settings and can usually be left
unchanged.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import signal
import logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [launcher] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("launcher")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _base_dir() -> str:
    """Directory containing this launcher (frozen or source)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _wait_for_backend(host: str, port: int, timeout: float = 60.0, interval: float = 0.5) -> bool:
    """
    Poll the backend via a raw socket HTTP/1.0 GET /health until a 200 response
    arrives or the timeout expires.

    Uses the standard-library `socket` module only — no urllib / http.client —
    so the frozen PyInstaller bundle stays small and avoids the setuptools /
    pkg_resources startup-hook chain that requires http.client.
    """
    deadline = time.monotonic() + timeout
    attempt  = 0
    request  = (
        f"GET /health HTTP/1.0\r\n"
        f"Host: {host}:{port}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")

    while time.monotonic() < deadline:
        attempt += 1
        sock = None
        try:
            sock = socket.create_connection((host, port), timeout=2)
            sock.sendall(request)
            # Read the status line (first 64 bytes is plenty)
            response = b""
            while len(response) < 64:
                chunk = sock.recv(64)
                if not chunk:
                    break
                response += chunk
            # HTTP/1.x 200 OK
            if b" 200 " in response or response.startswith(b"HTTP/") and b"\n200 " in response:
                elapsed = time.monotonic() - (deadline - timeout)
                log.info("Backend is ready (attempt %d, %.1fs)", attempt, elapsed)
                return True
        except (OSError, ConnectionRefusedError):
            pass
        except Exception as exc:
            log.debug("Health probe error: %s", exc)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        time.sleep(interval)

    log.error("Backend did not become ready within %.0fs", timeout)
    return False


def _terminate(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    log.info("Stopping %s (pid %d)…", name, proc.pid)
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        log.warning("%s did not stop cleanly, killing…", name)
        proc.kill()
        proc.wait()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="AnimePlayer Launcher")
    parser.add_argument("--port", type=int, default=8765, help="Backend HTTP port (default: 8765)")
    parser.add_argument("--host", default="127.0.0.1",   help="Backend bind host (default: 127.0.0.1)")
    parser.add_argument("--db",   default=None,           help="Path to SQLite DB (default: <base>/db/anime_player.db)")
    args = parser.parse_args()

    base = _base_dir()

    # ── Backend ──────────────────────────────────────────────────────────────
    is_windows = sys.platform == "win32"
    exe_ext    = ".exe" if is_windows else ""

    backend_exe = os.path.join(base, "backend_http", f"backend_http{exe_ext}")
    if not os.path.isfile(backend_exe):
        log.error("backend_http not found: %s", backend_exe)
        return 1

    db_path = args.db or os.path.join(base, "db", "anime_player.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    backend_cmd = [
        backend_exe,
        "--db",   db_path,
        "--port", str(args.port),
        "--host", args.host,
    ]
    log.info("Starting backend: %s", " ".join(backend_cmd))
    backend_proc = subprocess.Popen(backend_cmd, cwd=base)

    # ── Wait for backend to be ready ─────────────────────────────────────────
    if not _wait_for_backend(args.host, args.port, timeout=60):
        _terminate(backend_proc, "backend_http")
        return 2

    # ── UI ───────────────────────────────────────────────────────────────────
    ui_exe = os.path.join(base, "ui", f"AnimePlayer{exe_ext}")
    if not os.path.isfile(ui_exe):
        log.error("UI executable not found: %s", ui_exe)
        _terminate(backend_proc, "backend_http")
        return 3

    log.info("Launching UI: %s", ui_exe)
    ui_proc = subprocess.Popen([ui_exe], cwd=os.path.join(base, "ui"))

    # ── Forward Ctrl-C / SIGTERM to children ─────────────────────────────────
    def _on_signal(signum, _frame):
        log.info("Signal %s received — shutting down…", signum)
        _terminate(ui_proc, "AnimePlayer UI")
        _terminate(backend_proc, "backend_http")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _on_signal)
    if hasattr(signal, "SIGBREAK"):      # Windows Ctrl+Break
        signal.signal(signal.SIGBREAK, _on_signal)

    # ── Wait for UI to exit ──────────────────────────────────────────────────
    try:
        ui_exit_code = ui_proc.wait()
        log.info("UI exited with code %d", ui_exit_code)
    except KeyboardInterrupt:
        log.info("Ctrl-C — shutting down…")

    _terminate(backend_proc, "backend_http")
    return 0


if __name__ == "__main__":
    sys.exit(main())
