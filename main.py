import logging.config
import os
import sys
import argparse
import threading
from PyQt5.QtWidgets import QApplication

# Импортируем классы версий приложения
from app.tinker_v1.app import AnimePlayerAppVer1 # Tinker version 1
from app.tinker_v2.app import AnimePlayerAppVer2  # Tkinter версия 2
from core.database_manager import DatabaseManager  # База данных
from app.qt.app import AnimePlayerAppVer3  # PyQt версия 3

def run_tkinter_app_v1():
    import tkinter as tk
    window = tk.Tk()
    app_tk_v1 = AnimePlayerAppVer1(window)
    window.mainloop()

def run_tkinter_app_v2(db_manager):
    import tkinter as tk
    window = tk.Tk()
    app_tk_v2 = AnimePlayerAppVer2(window, db_manager)
    window.mainloop()

def run_pyqt_app(db_manager):
    app_pyqt = QApplication(sys.argv)
    window_pyqt = AnimePlayerAppVer3(db_manager)
    window_pyqt.show()
    sys.exit(app_pyqt.exec_())

if __name__ == "__main__":
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    # Construct the path to the database in the main directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'db', 'anime_player.db')

    # Создаем и инициализируем таблицы базы данных
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_tables()

    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(description="Запуск версий Anime Player")
    parser.add_argument('--version1', action='store_true', help="Запустить версию с Tkinter version 1.0.0")
    parser.add_argument('--version2', action='store_true', help="Запустить версию с Tkinter version 2.0.0")
    parser.add_argument('--version3', action='store_true', help="Запустить версию с PyQt version 3.0.0")
    args = parser.parse_args()

    # Запуск выбранных версий в разных потоках
    threads = []

    if args.version1:
        thread_tk_v1 = threading.Thread(target=run_tkinter_app_v1)
        threads.append(thread_tk_v1)

    if args.version2:
        thread_tk_v2 = threading.Thread(target=run_tkinter_app_v2, args=(db_manager,))
        threads.append(thread_tk_v2)

    if args.version3:
        thread_pyqt = threading.Thread(target=run_pyqt_app, args=(db_manager,))
        threads.append(thread_pyqt)

    # Запуск всех потоков
    for thread in threads:
        thread.start()

    # Ожидание завершения всех потоков
    for thread in threads:
        thread.join()
