"""Pydantic models for API requests and responses."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class PublishRequest(BaseModel):
    """Request model for publishing a message."""

    message: str = Field(..., description="The message text to publish")
    image_url: Optional[str] = Field(None, description="URL of image to attach")
    image_data: Optional[str] = Field(None, description="Base64-encoded image data")
    targets: Optional[list[str]] = Field(
        None, description="Target platforms (bluesky, discord). Defaults to all configured."
    )
    metadata: Optional[dict[str, Any]] = Field(
        None, description="Optional metadata (e.g., for super-signal integration)"
    )


class PublishResultItem(BaseModel):
    """Result of publishing to a single target."""

    success: bool
    post_uri: Optional[str] = Field(None, description="URI/ID of the created post")
    message_id: Optional[str] = Field(None, description="Discord message ID")
    error: Optional[str] = Field(None, description="Error message if failed")


class PublishResponse(BaseModel):
    """Response model for publish endpoint."""

    success: bool
    results: dict[str, PublishResultItem]


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = "ok"
    version: str
    configured_targets: list[str]
    target_status: dict[str, bool]


class ConfigCheckResponse(BaseModel):
    """Response model for configuration check."""

    bluesky_configured: bool
    discord_configured: bool
    configured_targets: list[str]
