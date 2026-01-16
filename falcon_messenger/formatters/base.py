"""Base formatter interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseFormatter(ABC):
    """Abstract base class for message formatters."""

    @abstractmethod
    def format(self, message: str, metadata: Optional[dict[str, Any]] = None) -> str:
        """Format a message with optional metadata.

        Args:
            message: The original message text.
            metadata: Optional metadata to enhance formatting.

        Returns:
            Formatted message string.
        """
        pass

    @abstractmethod
    def can_handle(self, metadata: Optional[dict[str, Any]]) -> bool:
        """Check if this formatter can handle the given metadata.

        Args:
            metadata: The metadata to check.

        Returns:
            True if this formatter should be used.
        """
        pass
