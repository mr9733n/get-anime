# config_manager.py
import configparser
import os

class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
    
    def get_setting(self, section, setting, default=None):
        try:
            return self.config[section].get(setting, default)
        except KeyError as e:
            raise KeyError(f"Missing section '{section}' or setting '{setting}' in config: {e}")

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