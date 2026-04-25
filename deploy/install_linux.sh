#!/usr/bin/env bash
# Install Anime Player backend as a systemd service on Linux / TrueNAS SCALE
# Usage:
#   sudo bash install_linux.sh [install_dir] [db_path] [port]
#
# Defaults:
#   install_dir = /opt/anime-player
#   db_path     = /opt/anime-player/db/anime_player.db
#   port        = 8765

set -euo pipefail

INSTALL_DIR="${1:-/opt/anime-player}"
DB_PATH="${2:-$INSTALL_DIR/db/anime_player.db}"
PORT="${3:-8765}"
SERVICE_FILE="/etc/systemd/system/anime-player.service"
SERVICE_USER="anime"

echo "=== Anime Player Backend — Linux Install ==="
echo "Install dir : $INSTALL_DIR"
echo "DB path     : $DB_PATH"
echo "Port        : $PORT"
echo ""

# Create system user (no login shell)
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "[+] Created system user: $SERVICE_USER"
fi

# Create directories
mkdir -p "$INSTALL_DIR/db" "$INSTALL_DIR/playlists" "$INSTALL_DIR/temp" \
         "$INSTALL_DIR/logs" "$INSTALL_DIR/config"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create virtual environment if not present
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
fi

# Install dependencies
"$INSTALL_DIR/venv/bin/pip" install fastapi "uvicorn[standard]"

# Write service file
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Anime Player Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python -m backend.transport.http.server \\
    --db $DB_PATH \\
    --port $PORT \\
    --host 0.0.0.0
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=anime-player
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$INSTALL_DIR/db $INSTALL_DIR/playlists $INSTALL_DIR/temp $INSTALL_DIR/logs
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl daemon-reload
systemctl enable anime-player
systemctl restart anime-player

echo ""
echo "=== Done ==="
echo "Status:  systemctl status anime-player"
echo "Logs  :  journalctl -u anime-player -f"
echo "API   :  http://$(hostname -I | awk '{print $1}'):$PORT/api"
echo "Health:  http://$(hostname -I | awk '{print $1}'):$PORT/health"
