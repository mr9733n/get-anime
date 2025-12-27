# app/mpv/main.py
import os
import sys
import logging
import argparse
from pathlib import Path

from PyQt5.QtCore import QSharedMemory, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QStyle

from app.mpv.mpv_engine import MpvEngine
from app.mpv.player_window import PlayerWindow
from midnight.check_dll import load_library
from utils.security.library_loader import verify_library

LIB_HASH = "fdb7a0b1f700b9eb9056e9ddc0a890c33f55fbb7ccbd9ff1d554ea088762ee0d"
LIB_NAME = "libmpv-2.dll"


if getattr(sys, 'frozen', False):
    # Frozen app - dll в корне рядом с exe
    lib_dir = os.path.dirname(sys.executable)
else:
    # Dev mode - dll в libs/
    lib_dir = str(Path(__file__).resolve().parents[2] / "libs")

try:
    expected_hash = LIB_HASH
    lib_file_path = load_library(lib_dir, LIB_NAME)
    status = verify_library(lib_file_path, expected_hash)
    if not status:
        sys.exit(1)
except Exception as e:
    logging.error(f"Failed to initialize library: {e}", exc_info=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", type=str, default=None, help="URL or path to playlist file")
    p.add_argument("--title_id", type=int, default=None)
    p.add_argument("--skip_data", type=str, default=None, help="base64 urlsafe json with skip ranges")
    p.add_argument("--proxy", type=str, default=None, help="proxy string (ip:port or scheme://ip:port)")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--log", type=str, default=None, help="write mpv log to this file (optional)")
    p.add_argument("--no-autoplay", action="store_true")
    p.add_argument('--template', default="default", help='UI template name')
    p.add_argument("--prod_key", type=str, default=None, help="single instance key")
    return p


def main():
    args = build_parser().parse_args()
    icon_path = os.path.join('static', 'icon.png')
    icon_path = os.path.normpath(icon_path)
    app = QApplication(sys.argv)
    app.setApplicationName("Anime Player MPV")
    app.setWindowIcon(QIcon(icon_path))

    if args.prod_key:
        unique_key = str(args.prod_key) + '-APM'
        shared_memory = QSharedMemory(unique_key)
        if not shared_memory.create(1):
            logging.getLogger().error("Anime Player MPV player is already running!")
            sys.exit(1)

        loglevel = "info" if args.verbose else "warn"
        engine = MpvEngine(proxy=args.proxy, loglevel=loglevel, log_file=args.log)

        w = PlayerWindow(
            engine,
            playlist=args.playlist,
            title_id=args.title_id,
            skip_data=args.skip_data,
            proxy=args.proxy,
            autoplay=not args.no_autoplay,
            template=args.template,
        )
        w.show()

    else:
        message = "MPV player cannot be run without AnimePlayer application!"
        logging.getLogger().error(message)
        tray_icon = QSystemTrayIcon()
        tray_icon.setIcon(app.style().standardIcon(QStyle.SP_MessageBoxWarning))
        tray_icon.show()
        tray_icon.showMessage("Error", message, QSystemTrayIcon.Warning, 5000)
        QTimer.singleShot(500, lambda: sys.exit(1))

    sys.exit(app.exec())

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    main()