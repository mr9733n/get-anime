Note: This application is for personal use only and should not be used to infringe copyright or other laws.

[Rus lang](https://github.com/mr9733n/get-anime/tree/main/static/rus/README.md)

# AnimePlayerApp

[Screenshots](https://github.com/mr9733n/get-anime/tree/main/static/Readme.md)

AnimePlayerApp is a Qt-based application for viewing and managing anime content. It creates a local database for storing links and posters, allows users to view the anime schedule, search for anime by title, view detailed information about a selected anime, save playlists, and play them using the built-in player or VLC Media Player.
    
    - api v3 obsolete and deprecated
    - tested with api v1


AnimePlayerAppLite is a Tkinter-based application for viewing and managing anime content. It allows users to view the anime schedule, search for anime by title, view detailed information about a selected anime, save playlists, and play them using VLC Media Player.
    
    - supported api v1
    - tested with api v1

## Features
- View the anime schedule for different days of the week.
- Update the schedule.
- Search for anime by title.
- Display detailed information about a selected anime, including description, status, genres, and release year.
- Ability to specify viewing history.
- Ability to mark a rating.
- Ability to mark a title as "watch later."
- Display a list of titles, franchises, and a "watch later" list.
- Display a list of anime by status, year, genre, and cast members.
- Saving playlists with anime episodes.
- Playing playlists with VLC Media Player.
- Selecting viewing quality (FHD, HD, SD).
- Downloading torrent files and transferring them to a torrent client.

## Setup and Usage
Installing Dependencies:
Before running the application, make sure you have Python 3 and VLC Player installed. You will also need to install the necessary dependencies:
Install the necessary libraries using pip:

```bash
pip install -r requirements.txt
```
## Configuration:
Configure the config.ini file with the appropriate parameters, including the API URL, the path to VLC Media Player, and other settings.

## Launch the application:
Run the application by running the Python script:

```bash
python main.py
```

## Build the application
```bash
pyinstaller build.spec --noconfirm
```

## Utilities 
[Full utilities list](https://github.com/mr9733n/get-anime/tree/main/midnight)

## Get the current list of titles from the website:
```bash
cd midnight
python scrapper.py
```

## Compare the retrieved list of titles with the local database:
```bash
cd midnight
python compare_titles.py
```

## Create an archive of compiled production versions
```bash
cd midnight
python create_archive.py
```

## Using the app:

Use the day of the week buttons to view the schedule.
Press RS⮂ to refresh the data for the currently displayed day of the week.

Click "Random" to select a random anime.

Use the input field and the "Find" button to search by title or ID (multiple IDs can be entered separated by commas).
Press UT⮂ to update the title_id in the input field or the current title.

The playlist for an open anime is saved automatically.

Create complex playlists from multiple titles using the corresponding buttons.

When the application closes, the current state is saved and restored the next time it is launched.

## Logging:

The application maintains a log of its operation, saving the logs in the logs folder.

## Other:

[Sql commands](https://github.com/mr9733n/get-anime/blob/main/sql_commands.md)

[Todo](https://github.com/mr9733n/get-anime/blob/main/anime_player_app_roadmap.md)
