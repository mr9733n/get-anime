import logging.config
import os
import re
import subprocess
import sys
import threading

from PyQt5.QtCore import QSharedMemory
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from PyQt5.uic.Compiler.qobjectcreator import logger
from core.database_manager import DatabaseManager
from app.qt.app import AnimePlayerAppVer3
from dotenv import load_dotenv
from utils.library_loader import verify_library, load_library


APP_MINOR_VERSION = '0.3.8'
APP_MAJOR_VERSION = '0.3'

load_dotenv()
prod_key = os.getenv("PROD_KEY")
fetch_ver = os.getenv('USE_GIT_VERSION')

UUID_REGEX = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
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

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging.config.fileConfig('config/logging.conf', disable_existing_loggers=False)

    # Construct the path to the database in the main directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(base_dir, 'db')
    icon_dir = os.path.join(base_dir, 'static')
    lib_dir = os.path.join(base_dir, 'libs')

    # Create object with unique key
    if not DEVELOPMENT_MODE:
        unique_key = prod_key  # use key generated on build
        shared_memory = QSharedMemory(unique_key)
        if not shared_memory.create(1):
            logging.getLogger(__name__).error("App is already running!")
            sys.exit(1)
    else:
        logging.getLogger(__name__).info("Development mode: single instance check disabled.")

    # Check vlc library
    try:
        expected_hash = "a2625d21b2cbca52ae5a9799e375529c715dba797a5646adf62f1c0289dbfb68"
        lib_file_path = load_library(lib_dir, 'libvlc.dll')
        verify_library(lib_file_path, expected_hash)
    except Exception as e:
        logger.error(f"Failed to initialize library: {e}")
        exit(1)

    # Ensure the database directory exists
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    db_path = os.path.join(db_dir, 'anime_player.db')

    # Create database on first start
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_tables()
    db_manager.save_template(template_name='default')
    db_manager.save_placeholders()

    # Check version
    version_thread = threading.Thread(target=fetch_version)
    version_thread.start()
    # finishing version check
    version_thread.join()
    # Starting application window
    app_pyqt = QApplication(sys.argv)

    icon_path = os.path.join(icon_dir, 'icon.png')
    app_pyqt.setWindowIcon(QIcon(icon_path))
    window_pyqt = AnimePlayerAppVer3(db_manager, version)
    window_pyqt.show()
    sys.exit(app_pyqt.exec_())
