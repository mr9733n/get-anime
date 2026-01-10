from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

from backend.core.ports.provider_payload_source import IProviderPayloadSource
from utils.config.config_manager import ConfigManager


class ProvidersFactory:
    def __init__(self, *, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger("backend")

    def build(
        self,
        *,
        cfg: ConfigManager,
        cache_dir: Path,
        boot_errors: list[str],
    ) -> dict[str, IProviderPayloadSource]:
        providers: dict[str, Any] = {}

        try:
            network_cfg = getattr(cfg, "network", None)
            if network_cfg is None:
                raise RuntimeError("ConfigManager.network is missing (cannot build NetClient)")

            from utils.net.net_client import NetClient
            net_client = NetClient(network_cfg)
        except Exception as e:
            boot_errors.append(f"net: {type(e).__name__}: {e}")
            return providers

        try:
            base_al_url = cfg.get_setting("Settings", "base_al_url")
            al_api_version = cfg.get_setting("Settings", "al_api_version")

            from providers.aniliberty.v1.api import APIClient
            from providers.aniliberty.v1.adapter import APIAdapter
            from backend.infra.providers.aniliberty_payload_source import AniLibertyPayloadSource

            api_client = APIClient(
                base_url=base_al_url,
                api_version=al_api_version,
                net_client=net_client,
                logger=self._logger,
                utils_folder=cache_dir,
                sleep_fn=None,
                max_cache_items=256,
                enable_dumps=False,
            )
            api_adapter = APIAdapter(api_client, self._logger)
            providers["aniliberty"] = AniLibertyPayloadSource(api=api_adapter)
        except Exception as e:
            boot_errors.append(f"aniliberty: {type(e).__name__}: {e}")

        try:
            base_am_url = cfg.get_setting("Settings", "base_am_url")

            from providers.animedia.v0 import create_adapter
            from backend.infra.providers.animedia_payload_source import AniMediaPayloadSource

            animedia_adapter = create_adapter(
                base_url=base_am_url,
                net_client=net_client,
                cache_dir=cache_dir,
                logger=self._logger,
            )
            providers["animedia"] = AniMediaPayloadSource(api=animedia_adapter)
        except Exception as e:
            boot_errors.append(f"animedia: {type(e).__name__}: {e}")

        return providers
