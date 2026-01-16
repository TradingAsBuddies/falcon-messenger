"""FastAPI server for falcon-messenger."""

import asyncio
import base64
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException

from falcon_messenger import __version__
from falcon_messenger.config import Settings
from falcon_messenger.formatters import SuperSignalFormatter
from falcon_messenger.models import (
    ConfigCheckResponse,
    HealthResponse,
    PublishRequest,
    PublishResponse,
    PublishResultItem,
)
from falcon_messenger.publishers import BlueskyPublisher, DiscordPublisher
from falcon_messenger.publishers.base import BasePublisher

logger = logging.getLogger(__name__)


class PublisherManager:
    """Manages publisher instances and dispatches messages."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.publishers: dict[str, BasePublisher] = {}
        self.formatters = [SuperSignalFormatter()]

    async def initialize(self) -> None:
        """Initialize configured publishers."""
        if self.settings.bluesky.is_configured:
            self.publishers["bluesky"] = BlueskyPublisher(self.settings.bluesky)
            logger.info("Bluesky publisher initialized")

        if self.settings.discord.is_configured:
            self.publishers["discord"] = DiscordPublisher(self.settings.discord)
            logger.info("Discord publisher initialized")

    async def close(self) -> None:
        """Close all publishers."""
        for publisher in self.publishers.values():
            await publisher.close()
        self.publishers.clear()

    def format_message(self, message: str, metadata: Optional[dict[str, Any]]) -> str:
        """Apply appropriate formatter to message."""
        for formatter in self.formatters:
            if formatter.can_handle(metadata):
                return formatter.format(message, metadata)
        return message

    async def publish(
        self,
        message: str,
        image: Optional[bytes] = None,
        image_mime_type: Optional[str] = None,
        targets: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, PublishResultItem]:
        """Publish message to specified targets.

        Args:
            message: The message to publish.
            image: Optional image data.
            image_mime_type: MIME type of image.
            targets: List of target publishers. If None, uses all configured.
            metadata: Optional metadata for formatting.

        Returns:
            Dictionary mapping target names to publish results.
        """
        # Format message if needed
        formatted_message = self.format_message(message, metadata)

        # Determine targets
        if targets:
            target_list = [t for t in targets if t in self.publishers]
        else:
            target_list = list(self.publishers.keys())

        if not target_list:
            return {}

        # Publish to all targets concurrently
        async def publish_to_target(name: str) -> tuple[str, PublishResultItem]:
            publisher = self.publishers[name]
            result = await publisher.publish(formatted_message, image, image_mime_type)
            return name, PublishResultItem(
                success=result.success,
                post_uri=result.post_uri,
                message_id=result.message_id,
                error=result.error,
            )

        tasks = [publish_to_target(name) for name in target_list]
        results = await asyncio.gather(*tasks)
        return dict(results)

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all publishers."""
        results = {}
        for name, publisher in self.publishers.items():
            results[name] = await publisher.health_check()
        return results


# Global manager instance
_manager: Optional[PublisherManager] = None


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings. If None, loads from environment.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _manager
        _manager = PublisherManager(settings)
        await _manager.initialize()
        logger.info(
            f"falcon-messenger v{__version__} started with targets: "
            f"{list(_manager.publishers.keys())}"
        )
        yield
        await _manager.close()
        _manager = None
        logger.info("falcon-messenger shutdown")

    app = FastAPI(
        title="falcon-messenger",
        description="Webhook/API server for publishing messages to Bluesky and Discord",
        version=__version__,
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health():
        """Health check endpoint."""
        if _manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        target_status = await _manager.health_check_all()
        return HealthResponse(
            status="ok",
            version=__version__,
            configured_targets=list(_manager.publishers.keys()),
            target_status=target_status,
        )

    @app.get("/config", response_model=ConfigCheckResponse)
    async def config_check():
        """Check current configuration status."""
        config_status = settings.check_configuration()
        return ConfigCheckResponse(
            bluesky_configured=config_status["bluesky"],
            discord_configured=config_status["discord"],
            configured_targets=settings.get_configured_targets(),
        )

    @app.post("/publish", response_model=PublishResponse)
    async def publish(request: PublishRequest):
        """Publish a message to configured platforms.

        The message will be published to all configured targets unless
        specific targets are specified in the request.
        """
        if _manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        # Process image if provided
        image_data: Optional[bytes] = None
        image_mime_type: Optional[str] = None

        if request.image_data:
            try:
                image_data = base64.b64decode(request.image_data)
                image_mime_type = "image/png"
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")

        elif request.image_url:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(request.image_url)
                    response.raise_for_status()
                    image_data = response.content
                    content_type = response.headers.get("content-type", "image/png")
                    image_mime_type = content_type.split(";")[0]
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to fetch image: {e}")

        # Publish to targets
        results = await _manager.publish(
            message=request.message,
            image=image_data,
            image_mime_type=image_mime_type,
            targets=request.targets,
            metadata=request.metadata,
        )

        if not results:
            raise HTTPException(
                status_code=400,
                detail="No valid targets specified or no publishers configured",
            )

        success = all(r.success for r in results.values())
        return PublishResponse(success=success, results=results)

    return app


# Default app instance for uvicorn
app = create_app()
