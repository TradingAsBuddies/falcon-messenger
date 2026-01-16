"""CLI entry point for falcon-messenger."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from falcon_messenger import __version__
from falcon_messenger.config import Settings


@click.group()
@click.version_option(version=__version__)
def main():
    """falcon-messenger - Publish messages to Bluesky and Discord."""
    pass


@main.command()
@click.option("--host", default=None, help="Host to bind to (default: from config or 0.0.0.0)")
@click.option("--port", "-p", default=None, type=int, help="Port to bind to (default: from config or 8080)")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--env-file", type=click.Path(exists=True), help="Path to .env file")
def serve(host: Optional[str], port: Optional[int], reload: bool, env_file: Optional[str]):
    """Start the falcon-messenger API server."""
    import uvicorn

    # Load settings to get defaults
    env_path = Path(env_file) if env_file else None
    settings = Settings.from_env(env_path)

    # CLI options override config
    final_host = host or settings.host
    final_port = port or settings.port

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    click.echo(f"Starting falcon-messenger v{__version__}")
    click.echo(f"Listening on http://{final_host}:{final_port}")
    click.echo(f"Configured targets: {settings.get_configured_targets()}")

    uvicorn.run(
        "falcon_messenger.server:app",
        host=final_host,
        port=final_port,
        reload=reload,
        log_level="debug" if settings.debug else "info",
    )


@main.command()
@click.argument("message")
@click.option("--target", "-t", multiple=True, help="Target platform (bluesky, discord)")
@click.option("--image", "-i", type=click.Path(exists=True), help="Path to image file")
@click.option("--env-file", type=click.Path(exists=True), help="Path to .env file")
def publish(message: str, target: tuple, image: Optional[str], env_file: Optional[str]):
    """Publish a message directly (for testing).

    Example: falcon-messenger publish "Hello world!" --target bluesky
    """
    from falcon_messenger.publishers import BlueskyPublisher, DiscordPublisher

    env_path = Path(env_file) if env_file else None
    settings = Settings.from_env(env_path)

    targets = list(target) if target else settings.get_configured_targets()

    if not targets:
        click.echo("Error: No targets specified and no publishers configured.", err=True)
        sys.exit(1)

    # Load image if provided
    image_data: Optional[bytes] = None
    image_mime_type: Optional[str] = None
    if image:
        image_path = Path(image)
        image_data = image_path.read_bytes()
        suffix = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        image_mime_type = mime_types.get(suffix, "image/png")

    async def do_publish():
        results = {}

        if "bluesky" in targets and settings.bluesky.is_configured:
            publisher = BlueskyPublisher(settings.bluesky)
            result = await publisher.publish(message, image_data, image_mime_type)
            results["bluesky"] = result
            await publisher.close()

        if "discord" in targets and settings.discord.is_configured:
            publisher = DiscordPublisher(settings.discord)
            result = await publisher.publish(message, image_data, image_mime_type)
            results["discord"] = result
            await publisher.close()

        return results

    results = asyncio.run(do_publish())

    for name, result in results.items():
        if result.success:
            click.echo(f"{name}: Published successfully")
            if result.post_uri:
                click.echo(f"  URI: {result.post_uri}")
            if result.message_id:
                click.echo(f"  Message ID: {result.message_id}")
        else:
            click.echo(f"{name}: Failed - {result.error}", err=True)

    if not results:
        click.echo("No publishers were available for the specified targets.", err=True)
        sys.exit(1)

    if not all(r.success for r in results.values()):
        sys.exit(1)


@main.command("config")
@click.option("--check", is_flag=True, help="Check configuration status")
@click.option("--env-file", type=click.Path(exists=True), help="Path to .env file")
def config_cmd(check: bool, env_file: Optional[str]):
    """Check or display configuration.

    Example: falcon-messenger config --check
    """
    env_path = Path(env_file) if env_file else None
    settings = Settings.from_env(env_path)

    if check:
        config_status = settings.check_configuration()
        click.echo("Configuration Status:")
        click.echo(f"  Bluesky: {'Configured' if config_status['bluesky'] else 'Not configured'}")
        click.echo(f"  Discord: {'Configured' if config_status['discord'] else 'Not configured'}")
        click.echo(f"\nConfigured targets: {settings.get_configured_targets()}")

        if not any(config_status.values()):
            click.echo("\nNo publishers configured. Set environment variables:")
            click.echo("  FALCON_BLUESKY_HANDLE and FALCON_BLUESKY_APP_PASSWORD")
            click.echo("  FALCON_DISCORD_WEBHOOK_URL")
            sys.exit(1)
    else:
        click.echo("Server Configuration:")
        click.echo(f"  Host: {settings.host}")
        click.echo(f"  Port: {settings.port}")
        click.echo(f"  Debug: {settings.debug}")
        click.echo(f"\nConfigured targets: {settings.get_configured_targets()}")


if __name__ == "__main__":
    main()
