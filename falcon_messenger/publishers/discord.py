"""Discord webhook publisher."""

import logging
from typing import Optional

import httpx

from falcon_messenger.config import DiscordConfig
from falcon_messenger.publishers.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)


class DiscordPublisher(BasePublisher):
    """Publisher for Discord using webhooks."""

    def __init__(self, config: DiscordConfig):
        """Initialize Discord publisher.

        Args:
            config: Discord configuration with webhook URL.
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return "discord"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def publish(
        self, message: str, image: Optional[bytes] = None, image_mime_type: Optional[str] = None
    ) -> PublishResult:
        """Publish a message to Discord via webhook.

        Args:
            message: The text content of the message.
            image: Optional image data as bytes.
            image_mime_type: MIME type of the image.

        Returns:
            PublishResult with success status and message ID.
        """
        try:
            client = await self._get_client()

            if image:
                mime_type = image_mime_type or "image/png"
                extension = mime_type.split("/")[-1]
                files = {"file": (f"image.{extension}", image, mime_type)}
                data = {"content": message}
                response = await client.post(
                    f"{self.config.webhook_url}?wait=true", data=data, files=files
                )
            else:
                json_data = {"content": message}
                response = await client.post(
                    f"{self.config.webhook_url}?wait=true", json=json_data
                )

            response.raise_for_status()
            result = response.json()
            message_id = result.get("id")
            logger.info(f"Published to Discord: message_id={message_id}")

            return PublishResult(success=True, message_id=message_id)

        except httpx.HTTPStatusError as e:
            logger.error(f"Discord webhook returned error: {e.response.status_code}")
            return PublishResult(success=False, error=f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Failed to publish to Discord: {e}")
            return PublishResult(success=False, error=str(e))

    async def health_check(self) -> bool:
        """Check if Discord webhook is accessible.

        Returns:
            True if webhook URL is valid and reachable.
        """
        try:
            client = await self._get_client()
            response = await client.get(self.config.webhook_url)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Discord health check failed: {e}")
            return False

    async def close(self) -> None:
        """Clean up HTTP client resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
