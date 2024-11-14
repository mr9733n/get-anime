import logging.config
import os
import sys
import argparse
import threading
from PyQt5.QtWidgets import QApplication

# Импортируем классы версий приложения
from core.database_manager import DatabaseManager  # База данных
from app.qt.app import AnimePlayerAppVer3  # PyQt версия 3

if __name__ == "__main__":
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging.config.fileConfig('config/logging.conf', disable_existing_loggers=False)

    # Construct the path to the database in the main directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(base_dir, 'db')

    # Ensure the database directory exists
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    db_path = os.path.join(db_dir, 'anime_player.db')

    # Создаем и инициализируем таблицы базы данных
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_tables()



    # Ожидание завершения всех потоков

    app_pyqt = QApplication(sys.argv)
    window_pyqt = AnimePlayerAppVer3(db_manager)
    window_pyqt.show()
    sys.exit(app_pyqt.exec_())

