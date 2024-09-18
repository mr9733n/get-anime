
import dearpygui.dearpygui as dpg
from docutils.nodes import label


class DisplayController:
    def __init__(self, app):
        self.title = None
        self.app = app
        self.logger = app.logger
        self.title_data = None
        self.selected_quality = 'fhd'

    def display_days(self):
        dpg.delete_item("title_grid", children_only=True)
        self.days_of_week = {
            0: "Понедельник",
            1: "Вторник",
            2: "Среда",
            3: "Четверг",
            4: "Пятница",
            5: "Суббота",
            6: "Воскресенье"
        }
        for i in range(7):
            dow = self.days_of_week[i]
            dpg.add_image_button(texture_tag=texture_id, width=200, height=200, callback=lambda s, d, day=dow: self.app.get_schedule(day))
            dpg.add_image_button(label=dow, callback=lambda s, d, day=dow: self.app.get_schedule(day), parent="title_grid")
    # Example ui
    # import dearpygui.dearpygui as dpg
    #
    # # Function to handle button clicks
    # def button_callback():
    #     print("Button clicked!")
    #
    # Load texture (image)
    # with dpg.texture_registry(show=False):
    #     width, height, channels, data = dpg.load_image("path_to_image.png")
    #     dpg.add_static_texture(width, height, data, tag="image_texture")
    #
    # Create a window
    # with dpg.window(label="Image Button with Text"):
    #
    # Create a child window to hold the image button and overlay text
    #     with dpg.child_window(width=300, height=300, autosize_y=False):
    #         dpg.add_image_button(texture_tag="image_texture", width=300, height=300, callback=button_callback)
    #
    #
    # Layering the text over the button
    #         with dpg.group():
    #             dpg.add_text("Title Text on Top")
    #             dpg.add_text("[Click here](https://example.com)")
    #
    #

    def display_title(self, title_data):
        self.title_data = title_data
        dpg.delete_item("title_grid", children_only=True)

        # Display title details (name, description, etc.)
        for title in title_data['list']:
            title_name = title.get("names", {}).get("en", "Unknown Title")
            dpg.add_button(label=title_name, callback=lambda s, d, title=self.title: self.show_title_info(title), parent="title_grid")

    def show_title_info(self, title):
        dpg.delete_item("title_grid", children_only=True)
        title_info = f"Title: {title.get('names', {}).get('en', 'Unknown')}\nDescription: {title.get('description', 'No description')}"

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
        self.display_poster = None
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

