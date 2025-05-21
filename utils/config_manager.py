# config_manager.py
import configparser


class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
    
    def get_setting(self, section, setting, default=None):
        try:
            return self.config[section].get(setting, default)
        except KeyError as e:
            raise KeyError(f"Missing section '{section}' or setting '{setting}' in config: {e}")

    @staticmethod
    def get_vlc_player_executable_name(platform_name):
        vlc_player_executable_name = "AnimePlayerVlc"
        if platform_name == "Windows":
            vlc_player_executable_name = vlc_player_executable_name + ".exe"
        return vlc_player_executable_name

    def get_video_player_path(self, platform_name):
        if platform_name == "Windows":
            return self.get_setting('Settings', 'win_video_player_path')
        elif platform_name == "Darwin":  # macOS
            return self.get_setting('Settings', 'mac_video_player_path')
        else:
            return None  # Handle other platforms if needed

    def get_torrent_client_path(self, platform_name):
        if platform_name == "Windows":
            return self.get_setting('Settings', 'win_torrent_client_path')
        elif platform_name == "Darwin":  # macOS
            return self.get_setting('Settings', 'mac_torrent_client_path')
        else:
            return None