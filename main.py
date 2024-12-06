import logging.config
import os
import re
import subprocess
import sys
import argparse
import threading

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from PyQt5.uic.Compiler.qobjectcreator import logger

# Импортируем классы версий приложения
from core.database_manager import DatabaseManager  # База данных
from app.qt.app import AnimePlayerAppVer3  # PyQt версия 3

APP_MINOR_VERSION = '0.3.8'
APP_MAJOR_VERSION = '0.3'

# TODO: Remove from build version command injection
def fetch_version():
    global version
    try:
        commit_message = subprocess.check_output(['git', 'log', '-1', '--pretty=%B'], text=True).strip()
        version_pattern = r"^\d+\.\d+\.\d+\.\d+$"
        match = re.match(version_pattern, commit_message)

        if match:
            version = match.group()
        else:
            version = APP_MINOR_VERSION
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while getting commit message: {e}")
        version = APP_MAJOR_VERSION

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
    # Ensure the database directory exists
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    db_path = os.path.join(db_dir, 'anime_player.db')

    # Создаем и инициализируем таблицы базы данных
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_tables()
    db_manager.save_template(template_name='default')
    db_manager.save_placeholders()

    # Запускаем поток для получения версии
    version_thread = threading.Thread(target=fetch_version)
    version_thread.start()
    # Ждем, пока поток завершится, прежде чем показывать интерфейс
    version_thread.join()
    # Пока версия загружается, можем начать работу интерфейса
    app_pyqt = QApplication(sys.argv)

    icon_path = os.path.join(icon_dir, 'icon.png')  # Путь к файлу с иконкой
    app_pyqt.setWindowIcon(QIcon(icon_path))
    window_pyqt = AnimePlayerAppVer3(db_manager, version)
    window_pyqt.show()
    sys.exit(app_pyqt.exec_())
