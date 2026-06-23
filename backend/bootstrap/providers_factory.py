from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.ports.provider_payload_source import IProviderPayloadSource
from backend.core.ports.schedule_port import IProviderScheduleSource
from utils.config.config_manager import ConfigManager


@dataclass
class ProvidersBuildResult:
    """Aggregates all provider sources built from the same adapter instances."""
    payload_sources: dict[str, IProviderPayloadSource] = field(default_factory=dict)
    schedule_sources: dict[str, IProviderScheduleSource] = field(default_factory=dict)
    boot_errors: list[str] = field(default_factory=list)


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
        """Legacy entry-point: returns only payload sources.

        Prefer build_all() when schedule sources are also needed.
        """
        return self.build_all(cfg=cfg, cache_dir=cache_dir).payload_sources

    def build_all(
        self,
        *,
        cfg: ConfigManager,
        cache_dir: Path,
    ) -> ProvidersBuildResult:
        """Build all provider sources (payload + schedule) from shared adapters."""
        result = ProvidersBuildResult()

        try:
            network_cfg = getattr(cfg, "network", None)
            if network_cfg is None:
                raise RuntimeError("ConfigManager.network is missing (cannot build NetClient)")

            from utils.net.net_client import NetClient
            net_client = NetClient(network_cfg)
        except Exception as e:
            result.boot_errors.append(f"net: {type(e).__name__}: {e}")
            return result

        # ── AniLiberty ───────────────────────────────────────────────────────
        try:
            base_al_url = cfg.get_setting("Settings", "base_al_url")
            al_api_version = cfg.get_setting("Settings", "al_api_version")

            from providers.aniliberty.v1.api import APIClient
            from providers.aniliberty.v1.adapter import APIAdapter
            from backend.infra.providers.aniliberty_payload_source import AniLibertyPayloadSource
            from backend.infra.providers.aniliberty_schedule_source import AniLibertyScheduleSource

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

            result.payload_sources["aniliberty"] = AniLibertyPayloadSource(api=api_adapter)
            result.schedule_sources["aniliberty"] = AniLibertyScheduleSource(
                api=api_adapter, logger=self._logger
            )
        except Exception as e:
            result.boot_errors.append(f"aniliberty: {type(e).__name__}: {e}")

        # ── AniMedia ─────────────────────────────────────────────────────────
        try:
            base_am_url = cfg.get_setting("Settings", "base_am_url")
            try:
                animedia_timeout = float(cfg.get_setting("Settings", "animedia_http_timeout_s", "90"))
            except (TypeError, ValueError):
                animedia_timeout = 90.0

            from providers.animedia.v0 import create_adapter
            from backend.infra.providers.animedia_payload_source import AniMediaPayloadSource
            from backend.infra.providers.animedia_schedule_source import AniMediaScheduleSource

            animedia_adapter = create_adapter(
                base_url=base_am_url,
                net_client=net_client,
                cache_dir=cache_dir,
                timeout=animedia_timeout,
                logger=self._logger,
            )

            result.payload_sources["animedia"] = AniMediaPayloadSource(api=animedia_adapter)
            result.schedule_sources["animedia"] = AniMediaScheduleSource(
                api=animedia_adapter, logger=self._logger
            )
        except Exception as e:
            result.boot_errors.append(f"animedia: {type(e).__name__}: {e}")

        return result
