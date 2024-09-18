import logging
import re
import subprocess

import dearpygui.dearpygui as dpg
from docutils.nodes import label


class DisplayController:
    def __init__(self, app):
        self.logger = logging.getLogger(__name__)
        self.title = None
        self.app = app
        self.logger = app.logger
        self.title_data = None
        self.selected_quality = 'fhd'
        self.pre = "https://"
        self.init_ui()

    def init_ui(self):
        self.app.window.title("Anime Player")
        self.app.window.geometry("1200x700")
        self.app.window.grid_rowconfigure(2, weight=1)
        self.app.window.grid_columnconfigure(0, weight=1)
        self.display_days()

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

    def on_link_click(self, event, title_name=None, torrent_id=None):
        try:
            tag_names = event.widget.tag_names(tk.CURRENT)
            match = re.search(r'(\d+)', tag_names[0])
            if not match:
                self.logger.error(f"Could not extract index from tag: {tag_names[0]}")
                return

            link_index = int(match.group(1))
            if link_index < 0 or link_index >= len(self.app.discovered_links):
                self.logger.error(f"Link index {link_index} out of range.")
                return

            link = self.app.discovered_links[link_index]
            if link.endswith('.m3u8'):
                video_plyer_path = self.app.video_player_path
                open_link = self.pre + self.app.stream_video_url + link
                media_player_command = [video_plyer_path, open_link]
                subprocess.Popen(media_player_command)
                self.logger.info(f"Playing video link: {open_link}")
            elif '/torrent/download.php' in link:
                self.app.save_torrent_wrapper(link, title_name, torrent_id)
            else:
                self.logger.error(f"Unknown link type: {link}")

        except Exception as e:
            error_message = f"An error occurred while processing the link: {str(e)}"
            self.logger.error(error_message)

    def on_title_click(self, event, en_name):
        try:
            self.title_search_entry.delete(0, tk.END)
            self.title_search_entry.insert(0, en_name)
            self.app.get_search_by_title()
        except Exception as e:
            error_message = f"An error occurred while clicking on title: {str(e)}"
            self.logger.error(error_message)

    def display_poster(self, poster_image):
        try:
            poster_photo = ImageTk.PhotoImage(poster_image)
            self.poster_label.configure(image=poster_photo)
            self.poster_label.image = poster_photo  # Сохраняем ссылку на изображение
        except Exception as e:
            error_message = f"An error occurred while displaying the poster: {str(e)}"
            self.logger.error(error_message)

    def change_poster(self):
        poster_image = self.app.poster_manager.get_next_poster()
        if poster_image:
            self.display_poster(poster_image)
        else:
            self.logger.warning("No poster to display.")

    def clear_poster(self):
        self.poster_label.configure(image='')
        self.poster_label.image = None

    def display_schedule(self, data):
        try:
            self.text.delete("1.0", tk.END)
            if data is not None:
                for day_info in data:
                    day = day_info.get("day")
                    title_list = day_info.get("list")
                    day_word = self.days_of_week[day]
                    self.text.insert(tk.END, f"День недели: {day_word}\n\n")
                    for i, title in enumerate(title_list):
                        self.display_title_info(title, i, show_description=False)
        except Exception as e:
            error_message = f"An error occurred while displaying the schedule: {str(e)}"
            self.logger.error(error_message)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, error_message)



    def display_info(self, data):
        dpg.delete_item("title_grid", children_only=True)
        if data is not None:
            self.app.discovered_links = []
            if "list" in data and isinstance(data["list"], list):
                titles = data["list"]
            else:
                titles = [data] if isinstance(data, dict) else []
            for i, item in enumerate(titles):
                self.display_title_info(item, i)
        except Exception as e:
            error_message = f"An error occurred while displaying information: {str(e)}"
            self.logger.error(error_message)



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

