"""Base publisher interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PublishResult:
    """Result of a publish operation."""

    success: bool
    post_uri: Optional[str] = None
    message_id: Optional[str] = None
    error: Optional[str] = None


class BasePublisher(ABC):
    """Abstract base class for all publishers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this publisher."""
        pass

    @abstractmethod
    async def publish(
        self, message: str, image: Optional[bytes] = None, image_mime_type: Optional[str] = None
    ) -> PublishResult:
        """Publish a message with optional image.

        Args:
            message: The text message to publish.
            image: Optional image data as bytes.
            image_mime_type: MIME type of the image (e.g., 'image/png').

        Returns:
            PublishResult indicating success or failure.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the publisher is healthy and can accept messages.

        Returns:
            True if healthy, False otherwise.
        """
        pass

    async def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
