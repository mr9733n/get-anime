# TrueNAS SCALE — Anime Player Backend Install

TrueNAS SCALE runs Debian-based Linux. The service runs as a systemd unit.

## 1. Create a Dataset

In TrueNAS UI: Storage → Datasets → Add  
Name: `anime-player`  
Mount point: `/mnt/pool/anime-player`

## 2. Open Shell (System → Shell)

```bash
# Install prerequisites
apt-get update && apt-get install -y python3-venv python3-pip

# Clone / copy project files
cd /mnt/pool/anime-player
# (copy your project files here via SMB share or git clone)

# Create venv and install deps
python3 -m venv venv
venv/bin/pip install fastapi "uvicorn[standard]"
# Install project requirements
venv/bin/pip install -r requirements.txt
```

## 3. Install service

```bash
bash deploy/install_linux.sh \
    /mnt/pool/anime-player \
    /mnt/pool/anime-player/db/anime_player.db \
    8765
```

## 4. Open firewall port

TrueNAS UI: Network → Interfaces → edit  
Or via shell:
```bash
# If using nftables
nft add rule inet filter input tcp dport 8765 accept
```

## 5. Verify

```bash
curl http://localhost:8765/health
# → {"ok": true, "version": "1.0"}
```

## 6. Configure apps

- **Desktop** (same machine): `http://localhost:8765`
- **Android TV**: `http://<truenas-ip>:8765`
  - Open app → ⚙️ Settings → type the TrueNAS IP

## Notes

- DB is at `/mnt/pool/anime-player/db/anime_player.db` — survives TrueNAS updates
- Playlists at `/mnt/pool/anime-player/playlists`
- Logs: `journalctl -u anime-player -f`
- The backend fetches provider data (needs internet), stores in local DB
