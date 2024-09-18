# config_manager.py
import configparser
import os
import logging

class ConfigManager:
    def __init__(self, config_file):
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file
        self.config = configparser.ConfigParser()

        if not os.path.exists(self.config_file):
            self.logger.debug(f"Config file not found at path: {self.config_file}")
        else:
            self.logger.debug(f"Reading config file from: {self.config_file}")

        self.config.read(self.config_file)
        self.logger.debug(f"Loaded sections: {self.config.sections()}")

    def get_setting(self, section, setting, default=None):
        try:
            return self.config[section].get(setting, default)
        except KeyError as e:
            raise KeyError(f"Missing section '{section}' or setting '{setting}' in config: {e}")
