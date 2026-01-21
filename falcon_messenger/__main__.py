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
        click.echo(f"  Falcon Endpoint: {'Configured' if config_status['falcon_endpoint'] else 'Not configured'}")
        click.echo(f"\nConfigured targets: {settings.get_configured_targets()}")

        if not any(config_status.values()):
            click.echo("\nNo publishers configured. Set environment variables:")
            click.echo("  FALCON_BLUESKY_HANDLE and FALCON_BLUESKY_APP_PASSWORD")
            click.echo("  FALCON_DISCORD_WEBHOOK_URL")
            click.echo("  FALCON_ENDPOINT_URL (for recommendations)")
            sys.exit(1)
    else:
        click.echo("Server Configuration:")
        click.echo(f"  Host: {settings.host}")
        click.echo(f"  Port: {settings.port}")
        click.echo(f"  Debug: {settings.debug}")
        click.echo(f"\nConfigured targets: {settings.get_configured_targets()}")
        if settings.falcon_endpoint.is_configured:
            click.echo(f"\nFalcon Endpoint:")
            click.echo(f"  URL: {settings.falcon_endpoint.endpoint_url}")
            click.echo(f"  Poll Interval: {settings.falcon_endpoint.poll_interval}s")
            click.echo(f"  Verify SSL: {settings.falcon_endpoint.verify_ssl}")


@main.command("recommendations")
@click.option("--once", is_flag=True, help="Fetch once and exit (don't run scheduler)")
@click.option("--dry-run", is_flag=True, help="Fetch and display, don't post to Discord")
@click.option("--interval", "-i", type=int, help="Poll interval in seconds (overrides config)")
@click.option("--endpoint", "-e", help="Falcon endpoint URL (overrides config)")
@click.option("--min-rvol", type=float, default=2.0, help="Minimum RVOL to post (default: 2.0)")
@click.option("--no-rvol-check", is_flag=True, help="Skip RVOL filtering")
@click.option("--no-tracking", is_flag=True, help="Don't track posted tickers (allow duplicates)")
@click.option("--clear-history", is_flag=True, help="Clear posted tickers history and exit")
@click.option("--show-history", is_flag=True, help="Show posted tickers history and exit")
@click.option("--env-file", type=click.Path(exists=True), help="Path to .env file")
def recommendations_cmd(
    once: bool,
    dry_run: bool,
    interval: Optional[int],
    endpoint: Optional[str],
    min_rvol: float,
    no_rvol_check: bool,
    no_tracking: bool,
    clear_history: bool,
    show_history: bool,
    env_file: Optional[str],
):
    """Fetch recommendations from Falcon and post to Discord as a table.

    Examples:
        falcon-messenger recommendations --once --dry-run
        falcon-messenger recommendations --interval 60
        falcon-messenger recommendations --endpoint https://192.168.1.162/api/recommendations
        falcon-messenger recommendations --min-rvol 2.5
        falcon-messenger recommendations --show-history
        falcon-messenger recommendations --clear-history
    """
    from falcon_messenger.recommendations import (
        RecommendationsFetcher,
        RecommendationsScheduler,
        PostedTickersTracker,
        FinvizChecker,
        format_recommendations_table,
        format_single_recommendation,
        get_recommendations_list,
    )

    env_path = Path(env_file) if env_file else None
    settings = Settings.from_env(env_path)

    # Override with CLI options
    if endpoint:
        settings.falcon_endpoint.endpoint_url = endpoint
    if interval:
        settings.falcon_endpoint.poll_interval = interval

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Handle history commands first
    if show_history or clear_history:
        tracker = PostedTickersTracker()
        if show_history:
            posted = tracker.get_posted_tickers()
            if posted:
                click.echo(f"Posted tickers ({len(posted)}):\n")
                for item in posted:
                    click.echo(f"  {item['ticker']:6} | RVOL: {item['rvol'] or 'N/A':>5} | {item['theme'] or '':<10} | {item['posted_at']}")
            else:
                click.echo("No posted tickers in history.")
        if clear_history:
            count = tracker.clear()
            click.echo(f"Cleared {count} tickers from history.")
        tracker.close()
        return

    if not settings.falcon_endpoint.is_configured:
        click.echo("Error: Falcon endpoint not configured.", err=True)
        click.echo("Set FALCON_ENDPOINT_URL or use --endpoint option.", err=True)
        sys.exit(1)

    if not dry_run and not settings.discord.is_configured:
        click.echo("Error: Discord not configured.", err=True)
        click.echo("Set FALCON_DISCORD_WEBHOOK_URL or use --dry-run option.", err=True)
        sys.exit(1)

    fetcher = RecommendationsFetcher(settings.falcon_endpoint)

    async def run():
        try:
            if once or dry_run:
                # Single fetch
                data = await fetcher.fetch()
                items = get_recommendations_list(data)

                if dry_run:
                    # Show all recommendations with RVOL check if enabled
                    finviz = FinvizChecker() if not no_rvol_check else None
                    click.echo(f"Found {len(items)} recommendations (min RVOL: {min_rvol}):\n")
                    for i, item in enumerate(items, 1):
                        ticker = item.get("ticker", "")
                        rvol = None
                        if finviz:
                            rvol = await finviz.get_rvol(ticker)
                            would_post = rvol is not None and rvol >= min_rvol
                            status = "PASS" if would_post else "SKIP"
                        else:
                            status = "N/A"

                        message = format_single_recommendation(item, rvol)
                        click.echo(f"--- {i}/{len(items)} [{status}] ---")
                        click.echo(message)
                        click.echo("")
                    if finviz:
                        await finviz.close()
                else:
                    # Post each to Discord with filtering
                    scheduler = RecommendationsScheduler(
                        fetcher,
                        settings.discord.webhook_url,
                        settings.falcon_endpoint.poll_interval,
                        min_rvol=min_rvol,
                        check_rvol=not no_rvol_check,
                        track_posted=not no_tracking,
                    )
                    posted, total = await scheduler.fetch_and_post_once()
                    click.echo(f"Posted {posted}/{total} recommendations to Discord (RVOL >= {min_rvol})")
                    await scheduler.stop()
            else:
                # Run scheduler
                scheduler = RecommendationsScheduler(
                    fetcher,
                    settings.discord.webhook_url,
                    settings.falcon_endpoint.poll_interval,
                    min_rvol=min_rvol,
                    check_rvol=not no_rvol_check,
                    track_posted=not no_tracking,
                )
                click.echo(f"Starting recommendations scheduler")
                click.echo(f"  Interval: {settings.falcon_endpoint.poll_interval}s")
                click.echo(f"  Min RVOL: {min_rvol}")
                click.echo(f"  RVOL check: {'enabled' if not no_rvol_check else 'disabled'}")
                click.echo(f"  Tracking: {'enabled' if not no_tracking else 'disabled'}")
                click.echo("Press Ctrl+C to stop")

                await scheduler.start()

                # Keep running until interrupted
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    click.echo("\nStopping scheduler...")
                    await scheduler.stop()
        finally:
            await fetcher.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
