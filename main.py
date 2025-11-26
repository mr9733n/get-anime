# main.py
import ctypes
import logging.config
import os
import re
import subprocess
import sys
import threading
import faulthandler

from PyQt6 import QtCore
from PyQt6.QtCore import QSharedMemory
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from core.database_manager import DatabaseManager
from app.qt.app import AnimePlayerAppVer3
from dotenv import load_dotenv
from utils.library_loader import verify_library, load_library
from app.qt.app_state_manager import AppStateManager
from utils.runtime_manager import test_exception
from utils.config_manager import ConfigManager

APP_MINOR_VERSION = '0.3.8'
APP_MAJOR_VERSION = '0.3'
UUID_REGEX = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'

if getattr(sys, 'frozen', False):
    # В фризе всегда считаем рабочей директорией папку с exe
    os.chdir(os.path.dirname(sys.executable))

def resource_path(*parts: str) -> str:
    """
    Универсальный поиск ресурсов:
      - dev: рядом с main.py
      - frozen/onedir: сперва рядом с .exe, потом в _internal
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)

        # 1) сначала пробуем рядом с exe
        candidate1 = os.path.join(exe_dir, *parts)
        if parts and os.path.exists(candidate1):
            return candidate1
        if not parts:
            # resource_path() без аргументов -> корень рядом с exe
            return exe_dir

        # 2) пробуем sys._MEIPASS (PyInstaller может его ставить)
        internal = getattr(sys, "_MEIPASS", None)
        if internal:
            candidate2 = os.path.join(internal, *parts)
            if os.path.exists(candidate2):
                return candidate2

        # 3) пробуем dist/APP/_internal/...
        internal2 = os.path.join(exe_dir, "_internal")
        candidate3 = os.path.join(internal2, *parts)
        if os.path.exists(candidate3):
            return candidate3

        # 4) fallback — считаем, что ресурсов нет, но хотим создать (логи, БД и т.п.)
        return candidate1
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, *parts)

# --- пути ---
base_dir = resource_path()  # корень приложения (для dev — рядом с main.py, для frozen — рядом с exe)
log_dir = os.path.join(base_dir, 'logs')
db_dir = os.path.join(base_dir, 'db')

# Статические ресурсы ищем либо рядом с exe, либо в _internal:
icon_dir = resource_path('static')
lib_dir = resource_path('libs')
config_path = resource_path('config', 'config.ini')
logging_config_path = resource_path('config', 'logging.conf')
config_manager = ConfigManager(config_path)
prod_key = config_manager.get_setting('System', 'PROD_KEY')
fetch_ver = config_manager.get_setting('System', 'USE_GIT_VERSION')

if prod_key and re.match(UUID_REGEX, prod_key):
    DEVELOPMENT_MODE = False
else:
    DEVELOPMENT_MODE = True

def fetch_version():
    global version
    if DEVELOPMENT_MODE and fetch_ver == '1':
        try:
            commit_message = subprocess.check_output(['git', 'log', '-1', '--pretty=%B'], text=True).strip()
            version_pattern = r"^\d+\.\d+\.\d+\.\d+$"
            match = re.match(version_pattern, commit_message)
            if match:
                version = match.group()
            else:
                version = APP_MINOR_VERSION
            logger.info(f"Development version: {version}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error occurred while getting commit message: {e}")
            version = APP_MAJOR_VERSION
    else:
        version = APP_MINOR_VERSION
        logger.info(f"Production version: {version}")

def log_exception(exc_type, exc_value, exc_traceback):
    """Logging unexpected exceptions.
       Enable faulthandler when it needed."""

    fault_log_path = os.path.join(log_dir, 'fault.log')

    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Unexpected exception", exc_info=(exc_type, exc_value, exc_traceback))

    with open(fault_log_path, 'a') as fault_log:
        faulthandler.enable(file=fault_log)
        faulthandler.dump_traceback(file=fault_log)

def qt_message_handler(mode, context, message):
    if mode == QtCore.QtMsgType.QtInfoMsg:
        logger.info(f"Qt: {message}")
    elif mode == QtCore.QtMsgType.QtWarningMsg:
        logger.warning(f"Qt: {message}")
    elif mode == QtCore.QtMsgType.QtCriticalMsg:
        logger.critical(f"Qt: {message}")
    elif mode == QtCore.QtMsgType.QtFatalMsg:
        logger.critical(f"Qt FATAL: {message}")
    else:
        logger.debug(f"Qt: {message}")

def on_app_quit():
    # Save app current state
    app_state = window_pyqt.get_current_state()
    state_manager.save_state(app_state)
    logger.info(f"AnimePlayerApp Version {version} is closed.")

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging.config.fileConfig(logging_config_path,
                              disable_existing_loggers=False)

    sys.excepthook = log_exception

    # Check vlc library
    try:
        expected_hash = "a2625d21b2cbca52ae5a9799e375529c715dba797a5646adf62f1c0289dbfb68"
        lib_file_path = load_library(lib_dir, 'libvlc.dll')
        status = verify_library(lib_file_path, expected_hash)
        if not status:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to initialize library: {e}", exc_info=True)

    # Ensure the database directory exists
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    db_path = os.path.join(db_dir, 'anime_player.db')

    # Create database on first start
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_tables()
    db_manager.initialize_templates()
    db_manager.save_placeholders()

    # Check version
    version_thread = threading.Thread(target=fetch_version)
    version_thread.start()
    # finishing version check
    version_thread.join()
    # Starting application window
    app_pyqt = QApplication(sys.argv)

    QtCore.qInstallMessageHandler(qt_message_handler)

    state_manager = AppStateManager(db_manager)

    app_state = state_manager.load_state()
    template_name = app_state.get("template_name", "default")

    icon_path = os.path.join(icon_dir, 'icon.png')
    app_pyqt.setWindowIcon(QIcon(icon_path))

    if not DEVELOPMENT_MODE:
        window_pyqt = AnimePlayerAppVer3(db_manager, version, template_name, prod_key)
    else:
        logging.getLogger(__name__).info("Development mode: single instance check disabled.")
        window_pyqt = AnimePlayerAppVer3(db_manager, version, template_name)

    if app_state:
        window_pyqt.restore_state(app_state)
        state_manager.clear_state_in_db()
    else:
        # Load 2 titles on start from DB
        window_pyqt.display_titles(start=True)

    window_pyqt.show()

    app_pyqt.aboutToQuit.connect(on_app_quit)
    # Test handling critical & fatal error
    if DEVELOPMENT_MODE:
        app_pyqt.aboutToQuit.connect(test_exception)

    sys.exit(app_pyqt.exec())
