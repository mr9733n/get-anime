# main.py
import logging.config
import tkinter as tk
from core.app import AnimePlayerApp
from core.database_manager import DatabaseManager  # Импорт DatabaseManager

if __name__ == "__main__":
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    # Создаем и инициализируем таблицы базы данных
    db_manager = DatabaseManager()
    db_manager.initialize_tables()

    window = tk.Tk()
    app = AnimePlayerApp(window, db_manager)  # Передаем db_manager в приложение
    window.mainloop()
