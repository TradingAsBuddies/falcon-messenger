#!/usr/bin/env python3
"""Example Python client for falcon-messenger API."""

import asyncio
import base64
from pathlib import Path
from typing import Any, Optional

import httpx


class FalconMessengerClient:
    """Async client for falcon-messenger API."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        """Check server health."""
        response = await self._client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def config(self) -> dict[str, Any]:
        """Get configuration status."""
        response = await self._client.get(f"{self.base_url}/config")
        response.raise_for_status()
        return response.json()

    async def publish(
        self,
        message: str,
        targets: Optional[list[str]] = None,
        image_path: Optional[Path] = None,
        image_url: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Publish a message to configured platforms.

        Args:
            message: The message text to publish.
            targets: Optional list of targets (bluesky, discord).
            image_path: Optional path to local image file.
            image_url: Optional URL of image to attach.
            metadata: Optional metadata for formatting.

        Returns:
            API response with results for each target.
        """
        payload: dict[str, Any] = {"message": message}

        if targets:
            payload["targets"] = targets

        if image_path:
            image_data = image_path.read_bytes()
            payload["image_data"] = base64.b64encode(image_data).decode()
        elif image_url:
            payload["image_url"] = image_url

        if metadata:
            payload["metadata"] = metadata

        response = await self._client.post(f"{self.base_url}/publish", json=payload)
        response.raise_for_status()
        return response.json()

    async def publish_stock_alert(
        self,
        ticker: str,
        risk_flags: list[str],
        price: Optional[float] = None,
        message: Optional[str] = None,
        targets: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Publish a super-signal formatted stock alert.

        Args:
            ticker: Stock ticker symbol.
            risk_flags: List of risk flag descriptions.
            price: Optional current stock price.
            message: Optional additional message.
            targets: Optional list of targets.

        Returns:
            API response with results for each target.
        """
        metadata = {
            "source": "super-signal",
            "ticker": ticker,
            "risk_flags": risk_flags,
            "risk_count": len(risk_flags),
            "signal_type": "alert",
        }
        if price is not None:
            metadata["price"] = price

        return await self.publish(
            message=message or f"${ticker} alert",
            targets=targets,
            metadata=metadata,
        )


async def main():
    """Example usage of the FalconMessengerClient."""
    async with FalconMessengerClient() as client:
        # Check health
        print("=== Health Check ===")
        health = await client.health()
        print(f"Status: {health['status']}")
        print(f"Version: {health['version']}")
        print(f"Targets: {health['configured_targets']}")
        print()

        # Check configuration
        print("=== Configuration ===")
        config = await client.config()
        print(f"Bluesky configured: {config['bluesky_configured']}")
        print(f"Discord configured: {config['discord_configured']}")
        print()

        # Publish a simple message
        print("=== Simple Message ===")
        result = await client.publish("Hello from Python client!")
        print(f"Success: {result['success']}")
        for target, target_result in result["results"].items():
            print(f"  {target}: {target_result}")
        print()

        # Publish a stock alert
        print("=== Stock Alert ===")
        result = await client.publish_stock_alert(
            ticker="AAPL",
            risk_flags=["High volatility", "Insider selling", "Volume spike"],
            price=178.50,
        )
        print(f"Success: {result['success']}")
        for target, target_result in result["results"].items():
            print(f"  {target}: {target_result}")


if __name__ == "__main__":
    asyncio.run(main())
