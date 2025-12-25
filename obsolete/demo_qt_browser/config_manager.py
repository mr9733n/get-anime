# config_manager.py
from dataclasses import dataclass
import configparser


@dataclass
class NetworkConfig:
    proxy_enabled: bool
    proxy_url: str | None = None


class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self._network_config = None

    @property
    def network(self) -> NetworkConfig:
        """Конфигурация сети (ленивая загрузка)"""
        if self._network_config is None:
            self._network_config = self._load_network_config()
        return self._network_config

    def _load_network_config(self) -> NetworkConfig:
        try:
            section = self.config["Network"]
            enabled = section.getboolean("proxy_enabled", fallback=False)
            url = section.get("proxy_url", fallback=None)
            return NetworkConfig(proxy_enabled=enabled, proxy_url=url)
        except KeyError:
            return NetworkConfig(proxy_enabled=False, proxy_url=None)

    def get_setting(self, section, setting, default=None):
        try:
            return self.config[section].get(setting, default)
        except KeyError as e:
            raise KeyError(f"Missing section '{section}' or setting '{setting}' in config: {e}")

