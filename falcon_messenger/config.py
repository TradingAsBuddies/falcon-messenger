"""Configuration management for Falcon Messenger."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class BlueskyConfig:
    """Bluesky configuration."""

    handle: Optional[str] = None
    app_password: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        """Check if Bluesky is configured."""
        return bool(self.handle and self.app_password)


@dataclass
class DiscordConfig:
    """Discord configuration."""

    webhook_url: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        """Check if Discord is configured."""
        return bool(self.webhook_url)


@dataclass
class FalconEndpointConfig:
    """Falcon recommendations endpoint configuration."""

    endpoint_url: Optional[str] = None
    poll_interval: int = 300  # seconds (default 5 minutes)
    verify_ssl: bool = False  # Support self-signed certificates

    @property
    def is_configured(self) -> bool:
        """Check if Falcon endpoint is configured."""
        return bool(self.endpoint_url)


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    bluesky: BlueskyConfig = field(default_factory=BlueskyConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    falcon_endpoint: FalconEndpointConfig = field(default_factory=FalconEndpointConfig)

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Settings":
        """Load settings from environment variables.

        Args:
            env_file: Optional path to .env file to load.

        Returns:
            Settings instance with values from environment.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        bluesky = BlueskyConfig(
            handle=os.getenv("FALCON_BLUESKY_HANDLE"),
            app_password=os.getenv("FALCON_BLUESKY_APP_PASSWORD"),
        )

        discord = DiscordConfig(
            webhook_url=os.getenv("FALCON_DISCORD_WEBHOOK_URL"),
        )

        falcon_endpoint = FalconEndpointConfig(
            endpoint_url=os.getenv("FALCON_ENDPOINT_URL"),
            poll_interval=int(os.getenv("FALCON_POLL_INTERVAL", "300")),
            verify_ssl=os.getenv("FALCON_VERIFY_SSL", "").lower() in ("true", "1", "yes"),
        )

        return cls(
            host=os.getenv("FALCON_HOST", "0.0.0.0"),
            port=int(os.getenv("FALCON_PORT", "8080")),
            debug=os.getenv("FALCON_DEBUG", "").lower() in ("true", "1", "yes"),
            bluesky=bluesky,
            discord=discord,
            falcon_endpoint=falcon_endpoint,
        )

    def get_configured_targets(self) -> list[str]:
        """Get list of configured publishing targets."""
        targets = []
        if self.bluesky.is_configured:
            targets.append("bluesky")
        if self.discord.is_configured:
            targets.append("discord")
        return targets

    def check_configuration(self) -> dict[str, bool]:
        """Check which services are configured.

        Returns:
            Dictionary mapping service names to configuration status.
        """
        return {
            "bluesky": self.bluesky.is_configured,
            "discord": self.discord.is_configured,
            "falcon_endpoint": self.falcon_endpoint.is_configured,
        }
