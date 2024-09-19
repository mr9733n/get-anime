import dearpygui.dearpygui as dpg
from dearpygui.dearpygui import window

from app import AnimePlayerApp
from ui.ui import FrontManager

if __name__ == "__main__":
    app = AnimePlayerApp(window())  # No 'window' argument
    ui_manager = FrontManager(app)

    dpg.create_context()
    ui_manager.build()
    dpg.create_viewport(title='Anime App', width=800, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


