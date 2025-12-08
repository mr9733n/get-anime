# config_manager.py
from dataclasses import dataclass
import configparser
import platform


@dataclass
class NetworkConfig:
    proxy_enabled: bool
    proxy_url: str | None = None


@dataclass
class PathsConfig:
    video_player_path: str | None
    torrent_client_path: str | None


class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self._platform_name = platform.system()

        # Ленивая загрузка конфигов
        self._network_config = None
        self._paths_config = None

    @property
    def network(self) -> NetworkConfig:
        """Конфигурация сети (ленивая загрузка)"""
        if self._network_config is None:
            self._network_config = self._load_network_config()
        return self._network_config

    @property
    def paths(self) -> PathsConfig:
        """Конфигурация путей (ленивая загрузка)"""
        if self._paths_config is None:
            self._paths_config = PathsConfig(
                video_player_path=self.get_video_player_path(),
                torrent_client_path=self.get_torrent_client_path()
            )
        return self._paths_config

    def _load_network_config(self) -> NetworkConfig:
        try:
            section = self.config["network"]
            enabled = section.getboolean("proxy_enabled", fallback=False)
            url = section.get("proxy_url", fallback=None)
            return NetworkConfig(proxy_enabled=enabled, proxy_url=url)
        except KeyError:
            return NetworkConfig(proxy_enabled=False, proxy_url=None)

    def _get_platform_name(self) -> str:
        """Возвращает название платформы (Windows, Darwin, Linux)"""
        return self._platform_name

    # Старые методы для обратной совместимости
    def get_setting(self, section, setting, default=None):
        try:
            return self.config[section].get(setting, default)
        except KeyError as e:
            raise KeyError(f"Missing section '{section}' or setting '{setting}' in config: {e}")

    def get_vlc_player_executable_name(self):
        platform_name = self._platform_name
        vlc_player_executable_name = "AnimePlayerVlc"
        if platform_name == "Windows":
            vlc_player_executable_name = vlc_player_executable_name + ".exe"
        return vlc_player_executable_name

    def get_video_player_path(self):
        platform_name = self._platform_name  # вместо параметра
        if platform_name == "Windows":
            return self.get_setting('Settings', 'win_video_player_path')
        elif platform_name == "Darwin":  # macOS
            return self.get_setting('Settings', 'mac_video_player_path')
        else:
            return None

    def get_torrent_client_path(self):
        platform_name = self._platform_name
        if platform_name == "Windows":
            return self.get_setting('Settings', 'win_torrent_client_path')
        elif platform_name == "Darwin":  # macOS
            return self.get_setting('Settings', 'mac_torrent_client_path')
        else:
            return None