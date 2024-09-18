# main.py

import logging.config
import tkinter as tk
from app import AnimePlayerApp

if __name__ == "__main__":
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    window = tk.Tk()
    app = AnimePlayerApp(window)
    window.mainloop()
