#!/usr/bin/env bash
# Install Anime Player backend as a macOS launchd service
# Usage:
#   bash install_macos.sh [install_dir] [db_path] [port]

set -euo pipefail

INSTALL_DIR="${1:-$HOME/AnimePlayer}"
DB_PATH="${2:-$INSTALL_DIR/db/anime_player.db}"
PORT="${3:-8765}"
PLIST_PATH="$HOME/Library/LaunchAgents/app.anime.player.plist"

echo "=== Anime Player Backend — macOS Install ==="
echo "Install dir : $INSTALL_DIR"
echo "DB path     : $DB_PATH"
echo "Port        : $PORT"
echo ""

mkdir -p "$INSTALL_DIR/db" "$INSTALL_DIR/playlists" "$INSTALL_DIR/temp" \
         "$INSTALL_DIR/logs" "$INSTALL_DIR/config"

# Create venv if needed
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
fi

"$INSTALL_DIR/venv/bin/pip" install fastapi "uvicorn[standard]"

# Write launchd plist
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>app.anime.player</string>

    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/venv/bin/python</string>
        <string>-m</string>
        <string>backend.transport.http.server</string>
        <string>--db</string>
        <string>$DB_PATH</string>
        <string>--port</string>
        <string>$PORT</string>
        <string>--host</string>
        <string>0.0.0.0</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/stderr.log</string>
</dict>
</plist>
EOF

# Load (unload first if already loaded)
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load -w "$PLIST_PATH"

echo ""
echo "=== Done ==="
echo "Status:  launchctl list | grep anime"
echo "Logs  :  tail -f $INSTALL_DIR/logs/stderr.log"
echo "API   :  http://localhost:$PORT/api"
echo "Health:  http://localhost:$PORT/health"
