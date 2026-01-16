"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from falcon_messenger.config import BlueskyConfig, DiscordConfig, Settings
from falcon_messenger.server import create_app


@pytest.fixture
def bluesky_config():
    """Create a test Bluesky configuration."""
    return BlueskyConfig(
        handle="test.bsky.social",
        app_password="test-app-password",
    )


@pytest.fixture
def discord_config():
    """Create a test Discord configuration."""
    return DiscordConfig(
        webhook_url="https://discord.com/api/webhooks/123456/test-token",
    )


@pytest.fixture
def settings(bluesky_config, discord_config):
    """Create test settings with both publishers configured."""
    return Settings(
        host="127.0.0.1",
        port=8080,
        debug=True,
        bluesky=bluesky_config,
        discord=discord_config,
    )


@pytest.fixture
def settings_bluesky_only(bluesky_config):
    """Create test settings with only Bluesky configured."""
    return Settings(
        host="127.0.0.1",
        port=8080,
        bluesky=bluesky_config,
        discord=DiscordConfig(),
    )


@pytest.fixture
def settings_discord_only(discord_config):
    """Create test settings with only Discord configured."""
    return Settings(
        host="127.0.0.1",
        port=8080,
        bluesky=BlueskyConfig(),
        discord=discord_config,
    )


@pytest.fixture
def settings_none():
    """Create test settings with no publishers configured."""
    return Settings(
        host="127.0.0.1",
        port=8080,
        bluesky=BlueskyConfig(),
        discord=DiscordConfig(),
    )


@pytest.fixture
def app(settings):
    """Create a test FastAPI application."""
    return create_app(settings)


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI application."""
    with TestClient(app) as client:
        yield client
