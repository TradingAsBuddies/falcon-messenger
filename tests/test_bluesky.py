"""Tests for the Bluesky publisher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from falcon_messenger.config import BlueskyConfig
from falcon_messenger.publishers.bluesky import BlueskyPublisher


@pytest.fixture
def publisher(bluesky_config):
    """Create a Bluesky publisher instance."""
    return BlueskyPublisher(bluesky_config)


class TestBlueskyPublisher:
    """Tests for BlueskyPublisher."""

    def test_name(self, publisher):
        """Test that publisher name is correct."""
        assert publisher.name == "bluesky"

    @pytest.mark.asyncio
    async def test_publish_text_only(self, publisher):
        """Test publishing a text-only post."""
        mock_response = MagicMock()
        mock_response.uri = "at://did:plc:test/app.bsky.feed.post/123"

        with patch.object(publisher, "_client", new_callable=MagicMock) as mock_client:
            mock_client.login = AsyncMock()
            mock_client.send_post = AsyncMock(return_value=mock_response)
            publisher._authenticated = True

            result = await publisher.publish("Hello, Bluesky!")

            assert result.success is True
            assert result.post_uri == "at://did:plc:test/app.bsky.feed.post/123"
            mock_client.send_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_with_image(self, publisher):
        """Test publishing a post with an image."""
        mock_response = MagicMock()
        mock_response.uri = "at://did:plc:test/app.bsky.feed.post/123"

        mock_blob_response = MagicMock()
        mock_blob_response.blob = MagicMock()

        with patch.object(publisher, "_client", new_callable=MagicMock) as mock_client:
            mock_client.login = AsyncMock()
            mock_client.upload_blob = AsyncMock(return_value=mock_blob_response)
            mock_client.send_post = AsyncMock(return_value=mock_response)
            publisher._authenticated = True

            image_data = b"fake image data"
            result = await publisher.publish("Post with image", image_data, "image/png")

            assert result.success is True
            mock_client.upload_blob.assert_called_once_with(image_data, "image/png")
            mock_client.send_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_failure(self, publisher):
        """Test handling of publish failure."""
        with patch.object(publisher, "_ensure_authenticated", new_callable=AsyncMock) as mock_auth:
            mock_client = MagicMock()
            mock_client.send_post = AsyncMock(side_effect=Exception("Network error"))
            mock_auth.return_value = mock_client

            result = await publisher.publish("Test message")

            assert result.success is False
            assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_health_check_success(self, publisher):
        """Test successful health check."""
        mock_profile = MagicMock()

        with patch.object(publisher, "_ensure_authenticated", new_callable=AsyncMock) as mock_auth:
            mock_client = MagicMock()
            mock_client.get_profile = AsyncMock(return_value=mock_profile)
            mock_auth.return_value = mock_client

            result = await publisher.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, publisher):
        """Test failed health check."""
        with patch.object(publisher, "_ensure_authenticated", new_callable=AsyncMock) as mock_auth:
            mock_auth.side_effect = Exception("Connection failed")

            result = await publisher.health_check()
            assert result is False
