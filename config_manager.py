# config_manager.py

import configparser

class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

    def get_setting(self, section, setting, default=None):
        return self.config[section].get(setting, default)
