"""Tests for the Discord publisher."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from falcon_messenger.config import DiscordConfig
from falcon_messenger.publishers.discord import DiscordPublisher


@pytest.fixture
def publisher(discord_config):
    """Create a Discord publisher instance."""
    return DiscordPublisher(discord_config)


class TestDiscordPublisher:
    """Tests for DiscordPublisher."""

    def test_name(self, publisher):
        """Test that publisher name is correct."""
        assert publisher.name == "discord"

    @pytest.mark.asyncio
    async def test_publish_text_only(self, publisher):
        """Test publishing a text-only message."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123456789"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(publisher, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await publisher.publish("Hello, Discord!")

            assert result.success is True
            assert result.message_id == "123456789"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_with_image(self, publisher):
        """Test publishing a message with an image."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123456789"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(publisher, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            image_data = b"fake image data"
            result = await publisher.publish("Post with image", image_data, "image/png")

            assert result.success is True
            call_args = mock_client.post.call_args
            assert "files" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_publish_failure_http_error(self, publisher):
        """Test handling of HTTP error during publish."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(publisher, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await publisher.publish("Test message")

            assert result.success is False
            assert "401" in result.error

    @pytest.mark.asyncio
    async def test_health_check_success(self, publisher):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(publisher, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await publisher.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, publisher):
        """Test failed health check."""
        with patch.object(publisher, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_get_client.return_value = mock_client

            result = await publisher.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_close(self, publisher):
        """Test closing the publisher cleans up resources."""
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        publisher._client = mock_client

        await publisher.close()

        mock_client.aclose.assert_called_once()
        assert publisher._client is None
