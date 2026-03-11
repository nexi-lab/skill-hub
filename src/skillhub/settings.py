"""Runtime settings for skill-hub."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Environment-backed settings for Phase 1."""

    nexus_base_url: str
    nexus_api_key: str
    nexus_install_root: str
    nexus_timeout_seconds: float

    @property
    def nexus_api_key_configured(self) -> bool:
        """Whether a Nexus API key is configured."""
        return bool(self.nexus_api_key)


def get_settings() -> Settings:
    """Load settings from environment variables."""
    return Settings(
        nexus_base_url=os.getenv("NEXUS_BASE_URL", "http://localhost:2026"),
        nexus_api_key=os.getenv("NEXUS_API_KEY", ""),
        nexus_install_root=os.getenv("SKILLHUB_NEXUS_INSTALL_ROOT", "/skills"),
        nexus_timeout_seconds=float(os.getenv("SKILLHUB_NEXUS_TIMEOUT_SECONDS", "5")),
    )
