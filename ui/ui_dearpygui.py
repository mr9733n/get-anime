
import dearpygui.dearpygui as dpg

class DisplayController:
    def __init__(self):
        self.days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', '']
    
    def display_days(self):
        dpg.delete_item("title_grid", children_only=True)
        for day in self.days_of_week:
            dpg.add_button(label=day, callback=self.show_titles_for_day, parent="title_grid")
    
    def show_titles_for_day(self, sender, app_data):
        titles = [{"name": f"Title {i+1}"} for i in range(5)]  # Simulate titles for now
        self.display_title(titles)

    def display_title(self, items):
        dpg.delete_item("title_grid", children_only=True)
        num_items = len(items)
        
        if num_items == 1:
            # Merged 1*4 grid
            self.display_merged_grid(items, 1)
        elif num_items == 2:
            # Split into 2*4 grids
            self.display_merged_grid(items, 2)
        elif num_items == 3:
            # Handle 3*4-like
            self.display_merged_grid(items, 3)
        else:
            # Full 4x4 grid
            self.display_full_grid(items)

    def display_merged_grid(self, items, num_groups):
        # Create merged grids for title display depending on number of groups
        max_titles = 16  # Max grid size
        group_size = len(items) // num_groups
        for i in range(num_groups):
            title_data = items[i*group_size:(i+1)*group_size]
            for title in title_data:
                dpg.add_button(label=title["name"], callback=self.show_title_info, parent="title_grid")

    def display_full_grid(self, items):
        # Display the full 4x4 grid
        max_titles = 16
        for i in range(min(len(items), max_titles)):
            dpg.add_button(label=items[i]["name"], callback=self.show_title_info, parent="title_grid")
        
        for _ in range(max_titles - len(items)):
            dpg.add_text("", parent="title_grid")
    
    def show_title_info(self, sender, app_data):
        dpg.delete_item("title_grid", children_only=True)
        title_info = f"Full Info for {dpg.get_item_label(sender)}"
        dpg.add_text(title_info, parent="title_grid")

    def display_schedule(self):
        # Display a 4x4 grid for the schedule
        dpg.delete_item("title_grid", children_only=True)
        for i in range(16):
            dpg.add_button(label=f"Schedule {i+1}", parent="title_grid")

class MainApp:
    def __init__(self):
        self.display_controller = DisplayController()

    def build(self):
        with dpg.window(label="Anime App", width=800, height=600):
            # Top Controls
            with dpg.group(horizontal=True):
                dpg.add_button(label="Back", callback=self.display_controller.display_days)
                dpg.add_button(label="Random", callback=lambda: self.display_controller.display_title([{"name": "Random Title"}]))
                dpg.add_input_text(label="Search Title", tag="title_search")
                dpg.add_button(label="Show", callback=lambda: self.display_controller.display_title([{"name": dpg.get_value('title_search')}]))
            
            # Title Grid (Days of the Week and Titles)
            with dpg.group(tag="title_grid"):
                self.display_controller.display_days()

            # Bottom Controls
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save Playlist", callback=self.save_playlist)
                dpg.add_button(label="Play Playlist", callback=self.play_playlist)
                dpg.add_combo(label="Select Quality", items=['fhd', 'hd', 'sd'], default_value="fhd")
                dpg.add_button(label="Refresh", callback=self.refresh_page)

    def save_playlist(self, sender, app_data):
        pass

    def play_playlist(self, sender, app_data):
        pass

    def refresh_page(self, sender, app_data):
        self.display_controller.display_days()

if __name__ == '__main__':
    app = MainApp()
    dpg.create_context()
    app.build()
    dpg.create_viewport(title='Anime App', width=800, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
