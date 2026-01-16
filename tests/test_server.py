"""Tests for the FastAPI server."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from falcon_messenger.publishers.base import PublishResult
from falcon_messenger.server import create_app


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_ok(self, client):
        """Test that health endpoint returns OK status."""
        with patch(
            "falcon_messenger.publishers.bluesky.BlueskyPublisher.health_check",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "falcon_messenger.publishers.discord.DiscordPublisher.health_check",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "version" in data
            assert "configured_targets" in data


class TestConfigEndpoint:
    """Tests for the /config endpoint."""

    def test_config_shows_configured_targets(self, client):
        """Test that config endpoint shows configured targets."""
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert data["bluesky_configured"] is True
        assert data["discord_configured"] is True
        assert "bluesky" in data["configured_targets"]
        assert "discord" in data["configured_targets"]

    def test_config_no_targets(self, settings_none):
        """Test config endpoint with no configured targets."""
        app = create_app(settings_none)
        with TestClient(app) as client:
            response = client.get("/config")
            assert response.status_code == 200
            data = response.json()
            assert data["bluesky_configured"] is False
            assert data["discord_configured"] is False
            assert data["configured_targets"] == []


class TestPublishEndpoint:
    """Tests for the /publish endpoint."""

    def test_publish_requires_message(self, client):
        """Test that publish endpoint requires a message."""
        response = client.post("/publish", json={})
        assert response.status_code == 422

    def test_publish_success(self, client):
        """Test successful publish to all targets."""
        with patch(
            "falcon_messenger.publishers.bluesky.BlueskyPublisher.publish",
            new_callable=AsyncMock,
            return_value=PublishResult(success=True, post_uri="at://test/post/123"),
        ), patch(
            "falcon_messenger.publishers.discord.DiscordPublisher.publish",
            new_callable=AsyncMock,
            return_value=PublishResult(success=True, message_id="456"),
        ):
            response = client.post("/publish", json={"message": "Test message"})
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "bluesky" in data["results"]
            assert "discord" in data["results"]
            assert data["results"]["bluesky"]["success"] is True
            assert data["results"]["discord"]["success"] is True

    def test_publish_to_specific_target(self, client):
        """Test publishing to a specific target."""
        with patch(
            "falcon_messenger.publishers.bluesky.BlueskyPublisher.publish",
            new_callable=AsyncMock,
            return_value=PublishResult(success=True, post_uri="at://test/post/123"),
        ):
            response = client.post(
                "/publish", json={"message": "Test message", "targets": ["bluesky"]}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "bluesky" in data["results"]
            assert "discord" not in data["results"]

    def test_publish_handles_failure(self, client):
        """Test that publish handles failures gracefully."""
        with patch(
            "falcon_messenger.publishers.bluesky.BlueskyPublisher.publish",
            new_callable=AsyncMock,
            return_value=PublishResult(success=False, error="Auth failed"),
        ), patch(
            "falcon_messenger.publishers.discord.DiscordPublisher.publish",
            new_callable=AsyncMock,
            return_value=PublishResult(success=True, message_id="456"),
        ):
            response = client.post("/publish", json={"message": "Test message"})
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["results"]["bluesky"]["success"] is False
            assert data["results"]["bluesky"]["error"] == "Auth failed"
            assert data["results"]["discord"]["success"] is True

    def test_publish_with_metadata(self, client):
        """Test publishing with super-signal metadata for formatting."""
        with patch(
            "falcon_messenger.publishers.bluesky.BlueskyPublisher.publish",
            new_callable=AsyncMock,
            return_value=PublishResult(success=True, post_uri="at://test/post/123"),
        ) as mock_bluesky, patch(
            "falcon_messenger.publishers.discord.DiscordPublisher.publish",
            new_callable=AsyncMock,
            return_value=PublishResult(success=True, message_id="456"),
        ):
            response = client.post(
                "/publish",
                json={
                    "message": "Stock alert",
                    "metadata": {
                        "source": "super-signal",
                        "ticker": "AAPL",
                        "risk_count": 3,
                    },
                },
            )
            assert response.status_code == 200

            # Check that the formatter was applied
            call_args = mock_bluesky.call_args
            formatted_message = call_args[0][0]
            assert "AAPL" in formatted_message
            assert "Risk flags: 3" in formatted_message

    def test_publish_invalid_targets(self, client):
        """Test publishing with invalid targets."""
        response = client.post(
            "/publish", json={"message": "Test", "targets": ["invalid_target"]}
        )
        assert response.status_code == 400
