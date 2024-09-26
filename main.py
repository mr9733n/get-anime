import dearpygui.dearpygui as dpg
import logging.config
from app import AnimePlayerApp
from ui.ui_dearpygui import FrontManager

if __name__ == "__main__":
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)
    logger = logging.getLogger(__name__)
    logger.info("Starting application")

    try:
        dpg.create_context()

        # Initialize the application and UI manager
        app = AnimePlayerApp()
        ui_manager = FrontManager(app)

        # Build the UI (UI now handles window creation)
        ui_manager.build()

        dpg.create_viewport(title="Anime App", width=1200, height=600)
        dpg.setup_dearpygui()
        logger.debug("Showing viewport")
        dpg.show_viewport()

        logger.debug("Starting DearPyGui event loop")
        dpg.start_dearpygui()

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
    finally:
        dpg.destroy_context()
        logger.info("Destroyed context, exiting application")
