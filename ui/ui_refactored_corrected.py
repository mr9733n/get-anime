
import dearpygui.dearpygui as dpg
from app import AnimePlayerApp


class DisplayController:
    def __init__(self, app):
        self.app = app
        self.logger = app.logger
        self.poster_manager = app.poster_manager
        self.title_data = None
        self.selected_quality = 'fhd'

    def display_days(self):
        dpg.delete_item("title_grid", children_only=True)
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days_of_week:
            dpg.add_button(label=day, callback=lambda s, d, day=day: self.app.get_schedule(day), parent="title_grid")

    def display_title(self, title_data):
        self.title_data = title_data
        dpg.delete_item("title_grid", children_only=True)

        # Display title details (name, description, etc.)
        for title in title_data['list']:
            title_name = title.get("names", {}).get("en", "Unknown Title")
            dpg.add_button(label=title_name, callback=lambda s, d, title=title: self.show_title_info(title), parent="title_grid")

    def show_title_info(self, title):
        dpg.delete_item("title_grid", children_only=True)
        title_info = f"Title: {title.get('names', {}).get('en', 'Unknown')}
Description: {title.get('description', 'No description')}"
        dpg.add_text(title_info, parent="title_grid")

        # Get and display the poster for the title
        self.app.get_poster(title)

    def display_poster(self, poster_image):
        # Displays the poster image in the UI
        try:
            texture_id = dpg.generate_uuid()
            width, height = poster_image.size
            image_data = poster_image.tobytes("raw", "RGBA", 0, -1)
            dpg.add_static_texture(width, height, image_data, tag=texture_id)
            dpg.add_image(texture_id, width=width, height=height, parent="title_grid")
        except Exception as e:
            self.logger.error(f"Error displaying poster: {str(e)}")

    def save_playlist(self):
        self.app.save_playlist_wrapper()

    def play_playlist(self):
        self.app.play_playlist_wrapper()


class FrontManager:
    def __init__(self, app):
        self.app = app
        self.display_controller = DisplayController(app)

    def build(self):
        with dpg.window(label="Anime App", width=800, height=600):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Back", callback=self.display_controller.display_days)
                dpg.add_button(label="Random", callback=self.app.get_random_title)
                dpg.add_input_text(label="Search Title", tag="title_search")
                dpg.add_button(label="Show", callback=self.app.get_search_by_title)

            with dpg.group(tag="title_grid"):
                self.display_controller.display_days()

            with dpg.group(horizontal=True):
                dpg.add_button(label="Save Playlist", callback=self.display_controller.save_playlist)
                dpg.add_button(label="Play Playlist", callback=self.display_controller.play_playlist)
                dpg.add_combo(label="Select Quality", items=['fhd', 'hd', 'sd'], default_value="fhd", callback=self.set_quality)
                dpg.add_button(label="Refresh", callback=self.display_controller.display_days)

    def set_quality(self, sender, app_data):
        self.display_controller.selected_quality = app_data

    def refresh_page(self):
        self.display_controller.display_days()


if __name__ == '__main__':
    app = AnimePlayerApp()
    dpg.create_context()
    ui_manager = FrontManager(app)
    ui_manager.build()
    dpg.create_viewport(title='Anime App', width=800, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
