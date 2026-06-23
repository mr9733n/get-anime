# Anime Player — Backend HTTP Server: Build & Deploy Guide

Python 3.11+ · FastAPI · SQLAlchemy · SQLite

> ⚠️ **Do NOT touch the `make_bin/` folder** — that is the legacy Qt desktop app build.
> The HTTP server described here is a separate, standalone component.

---

## Overview

The backend exposes a single JSON-RPC-style endpoint used by the Kotlin Multiplatform UI
(Desktop and Android TV).

```
POST /api
Body:  {"op": "titles.search", "params": {"query": "naruto", "limit": 20}}
Reply: {"ok": true, "result": {...}, "error": null}

GET  /health           → {"ok": true, "version": "1.0"}
GET  /status           → {"ok": true, "ops": 17, "ops_list": [...]}
GET  /poster/{title_id} → JPEG/PNG bytes (from local poster DB table)
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ (3.12 / 3.13 work) |
| pip | latest |
| SQLite | bundled with Python |

---

## Quick Start (development)

```bash
# From repo root — create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Run the HTTP server
python -m backend.transport.http.server \
    --db db/anime_player.db \
    --port 8765

# Windows:
python -m backend.transport.http.server --db db\anime_player.db --port 8765
```

The server binds to `0.0.0.0:8765` by default — accessible from LAN (Android TV, etc.).

### Minimal install (server only, no Qt / VLC / MPV)

```bash
pip install fastapi "uvicorn[standard]" sqlalchemy
```

---

## CLI Arguments

```
python -m backend.transport.http.server [OPTIONS]

Required:
  --db PATH           Path to anime_player.db (SQLite database)

Optional:
  --port INT          Bind port              (default: 8765)
  --host STR          Bind address           (default: 0.0.0.0)
  --playlists-dir STR Directory for playlist files (default: playlists)
```

---

## Deploy as a Service

### Linux (systemd)

```bash
# Install as systemd service (runs at boot, auto-restarts on failure)
# Defaults: install to /opt/anime-player, port 8765
sudo bash deploy/install_linux.sh

# Custom paths:
sudo bash deploy/install_linux.sh /srv/anime /data/anime.db 8765
```

What the script does:
- Creates `/opt/anime-player/` directory layout
- Creates a `venv`, installs `fastapi` + `uvicorn`
- Writes `/etc/systemd/system/anime-player.service`
- Enables and starts the service

```bash
# After install:
systemctl status anime-player
journalctl -u anime-player -f        # live logs
systemctl restart anime-player
systemctl stop anime-player
```

#### Manual service file (minimal)

```ini
[Unit]
Description=Anime Player Backend
After=network-online.target

[Service]
Type=simple
User=anime
WorkingDirectory=/opt/anime-player
ExecStart=/opt/anime-player/venv/bin/python -m backend.transport.http.server \
    --db /opt/anime-player/db/anime_player.db \
    --port 8765 \
    --host 0.0.0.0
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### Windows (Task Scheduler)

```bat
REM Run as Administrator — installs as a scheduled task (runs at startup)
REM Defaults: install to C:\AnimePlayer, port 8765
deploy\install_windows.bat

REM Custom paths:
deploy\install_windows.bat C:\AnimePlayer C:\AnimePlayer\db\anime.db 8765
```

```bat
REM Manual control:
schtasks /run  /tn AnimePlayerBackend
schtasks /end  /tn AnimePlayerBackend
schtasks /query /tn AnimePlayerBackend
```

### macOS

```bash
sudo bash deploy/install_macos.sh
# Uses launchd — see the script for the plist path
```

---

## JSON-tool Binary (embedded / offline mode)

For Desktop: the UI can also run the backend as a **subprocess** (stdin/stdout JSON-RPC)
instead of connecting over HTTP. In this mode, no server port is needed.

```bash
# Build the standalone binary (from repo root):
pyinstaller backend_tool.spec

# Output: dist/backend_tool   (Linux/macOS)
#         dist\backend_tool.exe  (Windows)
```

The binary reads one JSON line from stdin and writes one JSON line to stdout, then exits.

> ⚠️ The `backend_tool.spec` is in the repo root, NOT inside `make_bin/`.
> `make_bin/` contains specs for the legacy Qt desktop app — do not use those.

---

## Available Operations (21)

| Group | Operations |
|-------|-----------|
| titles | `titles.search`, `titles.get`, `titles.list_episodes`, `titles_ids.search` |
| streams | `streams.get` |
| playlists | `playlist.compose`, `playlist.compose_multi` |
| sync | `sync.fetch_and_process`, `sync.search_and_process`, `sync.search_external_ids`, `sync.fetch_payload`, `sync.random_and_process` |
| update/jobs | `titles.update`, `titles.update.start`, `jobs.get` |
| schedule | `schedule.get`, `schedule.sync` |
| provider | `provider.catalog` |
| history | `history.mark_watched`, `history.mark_all_watched`, `history.set_need_to_see` |

All operations follow the same envelope:

```json
// Request
{"op": "titles.search", "params": {"query": "...", "limit": 20, "offset": 0, "view": "card"}}

// Success
{"ok": true, "result": { ... }, "error": null}

// Error
{"ok": false, "result": null, "error": "message"}
```

---

## Project Layout

```
backend/
├── bootstrap/           ← wires all components together
├── core/
│   ├── controllers/     ← business logic (no DB access)
│   ├── dto/             ← data transfer objects
│   └── ports/           ← interfaces (Protocols)
├── infra/
│   ├── db/              ← SQLAlchemy port implementations
│   └── providers/       ← AniMedia, AniLiberty adapters
└── transport/
    ├── http/
    │   └── server.py    ← FastAPI app (this server)
    └── json_tool/
        ├── handlers.py  ← JSON-RPC dispatch table
        └── protocol.py  ← ok() / fail() helpers

storage/                 ← ⚠️ REQUIRED AT RUNTIME (DB access, poster blobs, process/write-path)
utils/                   ← ⚠️ REQUIRED AT RUNTIME (image helpers, general utilities)
providers/               ← ⚠️ REQUIRED AT RUNTIME (AniMedia / AniLiberty adapters, local cache)

config/                  ← mutable runtime config
db/                      ← mutable runtime database files
playlists/               ← generated playlist files
torrents/                ← downloaded/saved .torrent metadata
temp/                    ← provider caches and temporary runtime files
logs/                    ← runtime logs

deploy/
├── install_linux.sh
├── install_windows.bat
└── install_macos.sh

requirements.txt         ← all Python dependencies
```

> **Important**: the server is not a self-contained package inside `backend/`.
> At runtime it also imports from `storage/`, `utils/`, and `providers/` at the
> runtime root. When deploying or building a PyInstaller binary, all code/runtime
> directories (`backend/`, `storage/`, `utils/`, `providers/`) must be present in
> the working directory (or included in the spec via `datas`/`hiddenimports`).
>
> Mutable runtime directories (`config/`, `db/`, `playlists/`, `torrents/`,
> `temp/`, `logs/`) should exist or be creatable by the backend process. AniMedia
> cache files are stored in `temp/` (`am_schedule_cache.json`,
> `am_all_titles_cache.json`, `am_vlink_cache.json`).
>
> Systemd / Task Scheduler `WorkingDirectory` must point to the repo root, not
> to the `backend/` subdirectory.

---

## Running Tests

```bash
# All tests
pytest

# Specific module
pytest tests/backend/ -v

# With output
pytest -s tests/backend/test_json_handlers.py
```

---

## Environment / Configuration

No `.env` file required for basic operation. All configuration is passed via CLI args.

The database path (`--db`) must point to an existing SQLite database file.
If the file does not exist, the server will fail to start.

Preferred standalone runtime database location:
- `db/anime_player.db` under the backend runtime root

Legacy/default database locations (if you initialized via the legacy app):
- Windows: `%APPDATA%\AnimePlayer\anime_player.db` or `C:\AnimePlayer\db\anime_player.db`
- Linux: `/opt/anime-player/db/anime_player.db` or `~/.local/share/anime_player/anime_player.db`
