import logging
import subprocess
from typing import List, Union

import dearpygui.dearpygui as dpg
from managers.data_manager import Poster, Torrent, Episode, Title, ScheduleParser, DaySchedule


class DisplayController:
    def __init__(self, app):
        self.video_player_path = None
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing DisplayController")
        self.playlist_manager = None
        self.title = None
        self.app = app

        self.title_data = None
        self.selected_quality = 'fhd'
        self.pre = "https://"

    def display_days(self, poster=None):
        dpg.delete_item("title_grid", children_only=True)
        self.days_of_week = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday"
        }

        # Wrapper function to explicitly pass the day number to the callback
        def create_button(day_number, day_label):
            def on_button_click():
                print(f"Button clicked for day: {day_number}")
                self.app.get_schedule(day_number)

            dpg.add_button(label=day_label, callback=on_button_click, parent="title_grid")

        # Loop over the days of the week and add buttons
        for i in range(7):
            dow = self.days_of_week[i]
            create_button(i, dow)

    def on_link_click(self, link_index, title_name=None, torrent_id=None):
        try:
            # Ensure the link index is valid
            if link_index < 0 or link_index >= len(self.app.discovered_links):
                self.logger.error(f"Link index {link_index} out of range.")
                return

            # Retrieve the link from discovered links
            link = self.app.discovered_links[link_index]

            # Handle video stream links (.m3u8)
            if link.endswith('.m3u8'):
                video_player_path = self.app.video_player_path
                open_link = self.pre + self.app.stream_video_url + link
                media_player_command = [video_player_path, open_link]
                subprocess.Popen(media_player_command)
                self.logger.info(f"Playing video link: {open_link}")

            # Handle torrent download links
            elif '/torrent/download.php' in link:
                self.app.save_torrent_wrapper(link, title_name, torrent_id)

            else:
                self.logger.error(f"Unknown link type: {link}")

        except Exception as e:
            error_message = f"An error occurred while processing the link: {str(e)}"
            self.logger.error(error_message)

    def on_title_click(self, title_name):
        try:
            # Directly trigger search with the title name without manipulating text entry
            self.app.get_search_by_title(title_name)
        except Exception as e:
            error_message = f"An error occurred while clicking on title: {str(e)}"
            self.logger.error(error_message)

    def display_poster(self, poster_image):
        try:
            texture_id = dpg.generate_uuid()
            width, height = poster_image.size
            image_data = poster_image.tobytes("raw", "RGBA", 0, -1)
            dpg.add_static_texture(width, height, image_data, tag=texture_id)
            dpg.add_image(texture_id, width=width, height=height, parent="title_grid")
        except Exception as e:
            self.logger.error(f"Error displaying poster: {str(e)}")

    def display_schedule(self, schedule_data: List[DaySchedule]):
        try:
            dpg.delete_item("title_grid", children_only=True)
            if schedule_data is not None:
                for day_schedule in schedule_data:
                    day_name = self.days_of_week.get(day_schedule.day, "Unknown Day")
                    dpg.add_text(f"Day: {day_name}", parent="title_grid")

                    for title in day_schedule.titles:
                        self.display_title_info(title)

        except Exception as e:
            error_message = f"An error occurred while displaying the schedule: {str(e)}"
            self.app.logger.error(error_message)
            dpg.delete_item("title_grid", children_only=True)
            dpg.add_text(error_message, parent="title_grid")

    def display_info(self, title_data: Union[Title, List[Title]]):
        try:
            dpg.delete_item("title_grid", children_only=True)

            # Check if we're dealing with a single title or a list of titles
            if isinstance(title_data, Title):
                self.display_title_info(title_data)  # Handle single title
            elif isinstance(title_data, list):
                for i, title in enumerate(title_data):
                    self.display_title_info(title, i)  # Iterate over list of titles
            else:
                self.logger.error("Invalid title_data format passed to display_info")

        except Exception as e:
            error_message = f"An error occurred while displaying information: {str(e)}"
            self.app.logger.error(error_message)
            # Clear the grid on error
            dpg.delete_item("title_grid", children_only=True)
            dpg.add_text(error_message, parent="title_grid")

    def display_title_info(self, title_data: Title, is_full_display=False):
        dpg.delete_item("title_grid", children_only=True)
        poster_url = title_data.poster.large or title_data.poster.medium or title_data.poster.small
        if poster_url:
            poster_image = self.app.load_image(poster_url)
            self.display_poster(poster_image)

        # Display general title information
        dpg.add_text(f"Title: {title_data.name_en}", parent="title_grid")
        dpg.add_text(f"Status: {title_data.status}", parent="title_grid")

        # Display the poster image
        if title_data.poster.large:
            dpg.add_image(title_data.poster.large, parent="title_grid")  # Ensure you handle image loading

        # Display torrents
        dpg.add_text("Torrents:", parent="title_grid")
        for torrent in title_data.torrents:
            dpg.add_button(label=f"Download ({torrent.quality})",
                           callback=lambda: self.app.save_torrent_wrapper(torrent.url, title_data.name_en, None),
                           parent="title_grid")

        # Display episodes with links
        if hasattr(title_data, 'episodes') and title_data.episodes:
            dpg.add_text("Episodes:", parent="title_grid")
            for episode in title_data.episodes:
                dpg.add_text(f"Episode {episode['number']}: {episode['name']}", parent="title_grid")
                for quality, url in episode['hls'].items():
                    dpg.add_button(label=f"Watch ({quality})",
                                   callback=lambda s, a, u=url: self.app.play_video(u),
                                   parent="title_grid")

        # Provide link to view more detailed title information if not already in full display mode
        if not is_full_display:
            dpg.add_button(label="View Full Title",
                           callback=lambda: self.on_title_click(title_data.name_en),
                           parent="title_grid")

        # Optionally, handle showing a poster
        if title_data.poster.large:
            self.app.get_poster(title_data.poster.large)

    def get_search_input(self):
        return dpg.get_value("title_search")  # Assuming 'title_search' is the tag of the search input box

    def update_quality_and_refresh(self, event=None):
        selected_quality = self.quality_var.get()
        data = self.app.current_data

        if not data:
            error_message = "No data available. Please fetch data first."
            self.logger.error(error_message)
            return

        # Handling multiple potential data structures
        if isinstance(data, dict):
            # Check if it's a schedule data structure
            if "day" in data and "list" in data and isinstance(data["list"], list):
                self.logger.debug("Detected schedule data structure.")
                self.display_schedule([data])  # Wrap in a list to match expected input

            # Check if it's the general information structure
            elif "list" in data and isinstance(data["list"], list):
                self.logger.debug("Using cached general information data.")
                self.display_info(data)

            else:
                error_message = "No valid data format detected. Please fetch data again."
                self.logger.error(error_message)
        elif isinstance(data, list):
            # Assume list structure corresponds to schedule data
            self.logger.debug("Detected list-based schedule data structure.")
            self.display_schedule(data)
        else:
            error_message = "Unsupported data format. Please fetch data first."
            self.logger.error(error_message)

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
        if self.app.discovered_links:
            self.sanitized_titles = [self.sanitize_filename(name) for name in self.title_names]
            self.playlist_manager.save_playlist(self.sanitized_titles, self.app.discovered_links, self.stream_video_url)
            dpg.add_text("Playlist saved successfully!", parent="status_area")  # UI feedback
        else:
            dpg.add_text("No links found for saving the playlist.", parent="status_area", color=[255, 0, 0])

    def play_playlist(self):
        if not self.sanitized_titles:
            dpg.add_text("No playlist found. Please save a playlist first.", parent="status_area", color=[255, 0, 0])
            return

        file_name = "_".join(self.sanitized_titles)[:100] + ".m3u"
        self.playlist_manager.play_playlist(file_name, self.video_player_path)
        dpg.add_text(f"Playing playlist: {file_name}", parent="status_area")

class FrontManager:
    def __init__(self, app):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing FrontManager")
        self.display_poster = None
        self.app = app
        self.display_controller = DisplayController(app)

    def build(self):
        try:
            self.app.logger.debug("Starting UI build...")
            with dpg.window(label="Anime App", width=1200, height=600, tag="main_window"):
                # Adding buttons and input for navigation
                self.app.logger.debug("Adding buttons and input for navigation")
                with dpg.group(horizontal=True, parent="main_window"):
                    dpg.add_button(label="Back", callback=self.display_controller.display_days)
                    dpg.add_button(label="Random", callback=self.app.get_random_title)
                    dpg.add_input_text(label="Search Title", tag="title_search")
                    dpg.add_button(label="Show", callback=self.app.get_search_by_title)

                # Creating the title grid for displaying anime titles
                self.app.logger.debug("Setting up title grid")
                with dpg.group(tag="title_grid", parent="main_window"):
                    self.display_controller.display_days()

                # Adding playlist control buttons
                self.app.logger.debug("Adding playlist control buttons")
                with dpg.group(horizontal=True, parent="main_window"):
                    dpg.add_button(label="Save Playlist", callback=self.display_controller.save_playlist)
                    dpg.add_button(label="Play Playlist", callback=self.display_controller.play_playlist)
                    dpg.add_combo(label="Select Quality", items=['fhd', 'hd', 'sd'], default_value="fhd",
                                  callback=self.set_quality)
                    dpg.add_button(label="Refresh", callback=self.display_controller.display_days)

            self.app.logger.debug("UI build complete")

        except Exception as e:
            self.app.logger.error(f"Error in UI build: {str(e)}")

    def set_quality(self, sender, app_data):
        self.display_controller.selected_quality = app_data

    def refresh_page(self):
        self.display_controller.display_days()

    def get_search_input(self):
        pass


