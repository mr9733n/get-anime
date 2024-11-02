import logging.config
import sys
import argparse
import threading
from PyQt5.QtWidgets import QApplication

# Импортируем классы версий приложения
from core.app import AnimePlayerApp  # Tkinter версия
from core.database_manager import DatabaseManager  # База данных
from core.app_ver2 import AnimePlayerAppVer2  # PyQt версия

def run_tkinter_app(db_manager):
    import tkinter as tk
    window = tk.Tk()
    app_tk = AnimePlayerApp(window, db_manager)
    window.mainloop()

def run_pyqt_app(db_manager):
    app_pyqt = QApplication(sys.argv)
    window_pyqt = AnimePlayerAppVer2(db_manager)
    window_pyqt.show()
    sys.exit(app_pyqt.exec_())

if __name__ == "__main__":
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    # Создаем и инициализируем таблицы базы данных
    db_manager = DatabaseManager()
    db_manager.initialize_tables()

    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(description="Запуск версий Anime Player")
    parser.add_argument('--tkinter', action='store_true', help="Запустить версию с Tkinter")
    parser.add_argument('--pyqt', action='store_true', help="Запустить версию с PyQt")
    args = parser.parse_args()

    # Запуск выбранных версий в разных потоках
    threads = []

    if args.tkinter:
        thread_tk = threading.Thread(target=run_tkinter_app, args=(db_manager,))
        threads.append(thread_tk)

    if args.pyqt:
        thread_pyqt = threading.Thread(target=run_pyqt_app, args=(db_manager,))
        threads.append(thread_pyqt)

    # Запуск всех потоков
    for thread in threads:
        thread.start()

    # Ожидание завершения всех потоков
    for thread in threads:
        thread.join()
