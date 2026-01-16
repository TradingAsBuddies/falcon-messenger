"""Bluesky publisher using AT Protocol."""

import logging
from typing import Optional

from atproto import AsyncClient
from atproto_client.models.app.bsky.embed.images import Main as ImagesEmbed
from atproto_client.models.app.bsky.embed.images import Image

from falcon_messenger.config import BlueskyConfig
from falcon_messenger.publishers.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)


class BlueskyPublisher(BasePublisher):
    """Publisher for Bluesky social network using AT Protocol."""

    def __init__(self, config: BlueskyConfig):
        """Initialize Bluesky publisher.

        Args:
            config: Bluesky configuration with handle and app password.
        """
        self.config = config
        self._client: Optional[AsyncClient] = None
        self._authenticated = False

    @property
    def name(self) -> str:
        return "bluesky"

    async def _ensure_authenticated(self) -> AsyncClient:
        """Ensure client is authenticated, creating new session if needed."""
        if self._client is None or not self._authenticated:
            self._client = AsyncClient()
            await self._client.login(self.config.handle, self.config.app_password)
            self._authenticated = True
            logger.info(f"Authenticated with Bluesky as {self.config.handle}")
        return self._client

    async def publish(
        self, message: str, image: Optional[bytes] = None, image_mime_type: Optional[str] = None
    ) -> PublishResult:
        """Publish a post to Bluesky.

        Args:
            message: The text content of the post.
            image: Optional image data as bytes.
            image_mime_type: MIME type of the image.

        Returns:
            PublishResult with success status and post URI.
        """
        try:
            client = await self._ensure_authenticated()

            embed = None
            if image:
                mime_type = image_mime_type or "image/png"
                blob = await client.upload_blob(image, mime_type)
                embed = ImagesEmbed(images=[Image(alt="", image=blob.blob)])

            response = await client.send_post(text=message, embed=embed)
            logger.info(f"Published to Bluesky: {response.uri}")

            return PublishResult(success=True, post_uri=response.uri)

        except Exception as e:
            logger.error(f"Failed to publish to Bluesky: {e}")
            return PublishResult(success=False, error=str(e))

    async def health_check(self) -> bool:
        """Check if Bluesky connection is healthy.

        Returns:
            True if authenticated and can reach Bluesky.
        """
        try:
            client = await self._ensure_authenticated()
            profile = await client.get_profile(self.config.handle)
            return profile is not None
        except Exception as e:
            logger.warning(f"Bluesky health check failed: {e}")
            return False

    async def close(self) -> None:
        """Clean up Bluesky client resources."""
        self._client = None
        self._authenticated = False
