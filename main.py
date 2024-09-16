# main.py

import logging
import logging.config
import tkinter as tk
from gui.app import AnimePlayerApp

if __name__ == "__main__":
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    window = tk.Tk()
    app = AnimePlayerApp(window)
    window.mainloop()
