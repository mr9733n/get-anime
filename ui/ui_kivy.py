
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner

class DynamicTitleGrid(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 4  # Always 4 columns
        self.days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', '']

    def display_days(self):
        """Initial display with days of the week."""
        self.clear_widgets()
        for day in self.days_of_week:
            day_button = Button(text=day)
            day_button.bind(on_press=self.show_titles_for_day)
            self.add_widget(day_button)

    def show_titles_for_day(self, instance):
        """Display the titles when a day is clicked."""
        # Simulate titles for now; this will be replaced with actual data
        titles = [{"name": f"Title {i+1}"} for i in range(5)]  # Example: 5 titles for the selected day
        self.display_titles(titles)

    def display_titles(self, titles):
        """Update the grid to display titles based on the selected day."""
        self.clear_widgets()
        num_titles = len(titles)
        max_titles = 16  # For the 4x4 grid

        for i in range(min(num_titles, max_titles)):
            title_button = Button(text=titles[i]["name"])
            title_button.bind(on_press=self.show_title_info)
            self.add_widget(title_button)

        # Fill the remaining cells with empty labels if needed
        for _ in range(max_titles - num_titles):
            self.add_widget(Label(text=""))

    def show_title_info(self, instance):
        """Display the full info for a selected title."""
        self.clear_widgets()
        title_info = f"Full Info for {instance.text}"  # Placeholder text for the full title information
        self.add_widget(Label(text=title_info, size_hint=(4, 4)))  # Use the full grid for one title

class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'

        # Top controls (Back, Random, Search, Show)
        top_controls = GridLayout(cols=4, size_hint_y=0.1)
        back_button = Button(text='Back', on_press=self.go_back)
        random_button = Button(text='Random', on_press=self.show_random_title)
        title_search = TextInput(hint_text='Search by Title', size_hint=(2, 1))
        show_button = Button(text='Show Title', on_press=self.show_searched_title)
        top_controls.add_widget(back_button)
        top_controls.add_widget(random_button)
        top_controls.add_widget(title_search)
        top_controls.add_widget(show_button)
        self.add_widget(top_controls)

        # Dynamic Title Grid (Initial display with days of the week)
        self.title_grid = DynamicTitleGrid(size_hint_y=0.7)
        self.title_grid.display_days()
        self.add_widget(self.title_grid)

        # Bottom controls
        bottom_controls = GridLayout(cols=4, size_hint_y=0.1)
        save_playlist_button = Button(text='Save Playlist', on_press=self.save_playlist)
        play_playlist_button = Button(text='Play Playlist', on_press=self.play_playlist)
        quality_spinner = Spinner(text='Select Quality', values=['fhd', 'hd', 'sd'])
        refresh_button = Button(text='Refresh', on_press=self.refresh_page)
        bottom_controls.add_widget(save_playlist_button)
        bottom_controls.add_widget(play_playlist_button)
        bottom_controls.add_widget(quality_spinner)
        bottom_controls.add_widget(refresh_button)
        self.add_widget(bottom_controls)

    def go_back(self, instance):
        """Logic for the 'Back' button."""
        self.title_grid.display_days()

    def show_random_title(self, instance):
        # Logic to display a random title
        titles = [{"name": "Random Title"}]  # Example random title data
        self.title_grid.display_titles(titles)

    def show_searched_title(self, instance):
        # Logic to display title based on the search input
        titles = [{"name": "Searched Title"}]  # Example searched title data
        self.title_grid.display_titles(titles)

    def save_playlist(self, instance):
        # Logic to save the playlist
        pass

    def play_playlist(self, instance):
        # Logic to play the playlist
        pass

    def refresh_page(self, instance):
        # Logic to refresh the page
        pass

class AnimeApp(App):
    def build(self):
        return MainScreen()

if __name__ == '__main__':
    AnimeApp().run()
