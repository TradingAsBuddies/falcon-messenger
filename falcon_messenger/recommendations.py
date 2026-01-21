"""Falcon recommendations fetcher and Discord table formatter."""

import asyncio
import logging
import re
import sqlite3
import ssl
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from falcon_messenger.config import FalconEndpointConfig, DiscordConfig

logger = logging.getLogger(__name__)

# Default database file for tracking posted recommendations
DEFAULT_DB_FILE = Path("/tmp/falcon_recommendations.db")


class FinvizChecker:
    """Check stock metrics from Finviz."""

    FINVIZ_URL = "https://finviz.com/quote.ashx"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with browser-like headers."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
        return self._client

    async def get_rvol(self, ticker: str) -> Optional[float]:
        """Get relative volume (RVOL) for a ticker from Finviz.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            RVOL value as float, or None if not found/error.
        """
        try:
            client = await self._get_client()
            url = f"{self.FINVIZ_URL}?t={ticker}"
            response = await client.get(url)
            response.raise_for_status()

            html = response.text

            # Look for Rel Volume in the Finviz page
            # Pattern matches: <td ...>Rel Volume</td><td ...><b>1.23</b></td>
            pattern = r'Rel Volume</td><td[^>]*><b[^>]*>([0-9.]+)</b>'
            match = re.search(pattern, html)

            if match:
                rvol = float(match.group(1))
                logger.debug(f"{ticker} RVOL: {rvol}")
                return rvol
            else:
                logger.warning(f"RVOL not found for {ticker}")
                return None

        except Exception as e:
            logger.error(f"Error fetching RVOL for {ticker}: {e}")
            return None

    async def close(self) -> None:
        """Clean up HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class PostedTickersTracker:
    """Track which tickers have been posted to avoid duplicates using SQLite."""

    def __init__(self, db_file: Path = DEFAULT_DB_FILE):
        self.db_file = db_file
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_file))
        return self._conn

    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_tickers (
                ticker TEXT PRIMARY KEY,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rvol REAL,
                theme TEXT,
                sector TEXT
            )
        """)
        conn.commit()

        # Count existing records
        cursor = conn.execute("SELECT COUNT(*) FROM posted_tickers")
        count = cursor.fetchone()[0]
        if count > 0:
            logger.info(f"Loaded {count} previously posted tickers from database")

    def is_posted(self, ticker: str) -> bool:
        """Check if ticker has already been posted."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM posted_tickers WHERE ticker = ?",
            (ticker.upper(),)
        )
        return cursor.fetchone() is not None

    def mark_posted(
        self,
        ticker: str,
        rvol: Optional[float] = None,
        theme: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> None:
        """Mark a ticker as posted with metadata."""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO posted_tickers (ticker, posted_at, rvol, theme, sector)
            VALUES (?, ?, ?, ?, ?)
        """, (ticker.upper(), datetime.now().isoformat(), rvol, theme, sector))
        conn.commit()

    def get_posted_tickers(self) -> list[dict]:
        """Get all posted tickers with metadata."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT ticker, posted_at, rvol, theme, sector FROM posted_tickers ORDER BY posted_at DESC"
        )
        return [
            {"ticker": row[0], "posted_at": row[1], "rvol": row[2], "theme": row[3], "sector": row[4]}
            for row in cursor.fetchall()
        ]

    def clear(self, before_date: Optional[str] = None) -> int:
        """Clear posted tickers, optionally only those before a date.

        Args:
            before_date: Optional ISO date string. If provided, only clear records before this date.

        Returns:
            Number of records cleared.
        """
        conn = self._get_conn()
        if before_date:
            cursor = conn.execute(
                "DELETE FROM posted_tickers WHERE posted_at < ?",
                (before_date,)
            )
        else:
            cursor = conn.execute("DELETE FROM posted_tickers")
        conn.commit()
        count = cursor.rowcount
        logger.info(f"Cleared {count} posted tickers")
        return count

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


class RecommendationsFetcher:
    """Fetches recommendations from a Falcon endpoint."""

    def __init__(self, config: FalconEndpointConfig):
        """Initialize the recommendations fetcher.

        Args:
            config: Falcon endpoint configuration.
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with SSL verification disabled if configured."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                verify=self.config.verify_ssl,  # False allows self-signed certs
            )
        return self._client

    async def fetch(self) -> dict[str, Any]:
        """Fetch recommendations from the Falcon endpoint.

        Returns:
            JSON response from the endpoint.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        if not self.config.endpoint_url:
            raise ValueError("Falcon endpoint URL not configured")

        client = await self._get_client()
        logger.info(f"Fetching recommendations from {self.config.endpoint_url}")

        response = await client.get(self.config.endpoint_url)
        response.raise_for_status()

        data = response.json()
        logger.info(f"Fetched {len(data) if isinstance(data, list) else 1} recommendations")
        return data

    async def close(self) -> None:
        """Clean up HTTP client resources."""
        if self._client:
            await self._client.aclose()
            self._client = None


def format_single_recommendation(item: dict[str, Any], rvol: Optional[float] = None) -> str:
    """Format a single recommendation as a Discord message.

    Args:
        item: Single recommendation dictionary.
        rvol: Optional relative volume from Finviz.

    Returns:
        Formatted Discord message for one symbol.
    """
    ticker = item.get("ticker", "???")
    company = item.get("company", "Unknown")
    sector = item.get("sector", "")
    theme = item.get("theme", "")
    risk = item.get("risk_level", "")

    entry = item.get("entry_price_range", "")
    target = item.get("target_price", "")
    stop = item.get("stop_loss", "")
    earnings = item.get("earnings_date", "")
    reasoning = item.get("reasoning", "")

    # Build message
    lines = [
        f"**${ticker}** - {company}",
        f"Sector: {sector} | Theme: {theme} | Risk: {risk}",
    ]

    # Add RVOL if available
    if rvol is not None:
        rvol_emoji = "🔥" if rvol >= 2 else "📊"
        lines.append(f"{rvol_emoji} RVOL: {rvol:.2f}")

    lines.extend([
        "",
        f"Entry: {entry}",
        f"Target: {target} | Stop: {stop}",
    ])

    if earnings:
        lines.append(f"Earnings: {earnings}")

    if reasoning:
        lines.append(f"\n_{reasoning}_")

    return "\n".join(lines)


def format_recommendations_table(data: Any, max_length: int = 1900) -> str:
    """Format recommendations data as a Discord-compatible table.

    Args:
        data: JSON data from the recommendations endpoint.
        max_length: Maximum message length (Discord limit is 2000).

    Returns:
        Formatted string for Discord (using code blocks for table alignment).
    """
    if not data:
        return "No recommendations available."

    # Handle both list and dict responses
    if isinstance(data, dict):
        if "recommendations" in data:
            items = data["recommendations"]
        else:
            items = [data]
    else:
        items = data

    if not items:
        return "No recommendations available."

    # Determine columns from first item
    if isinstance(items[0], dict):
        all_columns = list(items[0].keys())
    else:
        return "**Recommendations**\n" + "\n".join(f"• {item}" for item in items)

    # Priority columns for Discord (most important first)
    priority_columns = [
        "ticker", "company", "sector", "theme", "risk_level",
        "entry_price_range", "target_price", "stop_loss",
        "confidence_score", "earnings_date", "reasoning"
    ]

    # Select columns that exist in the data, prioritizing important ones
    columns = [col for col in priority_columns if col in all_columns]
    # Add any remaining columns not in priority list
    columns.extend([col for col in all_columns if col not in columns])

    # Truncate column values for display
    def truncate(val: str, max_len: int = 25) -> str:
        val = str(val) if val else ""
        return val[:max_len-2] + ".." if len(val) > max_len else val

    # Calculate column widths (with limits)
    col_widths = {}
    for col in columns:
        col_width = min(len(str(col)), 15)
        for item in items:
            val = truncate(str(item.get(col, "")), 25)
            col_width = max(col_width, min(len(val), 25))
        col_widths[col] = col_width

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_text = f"**Falcon Recommendations** ({timestamp})\n```\n"
    footer_text = "\n```"

    # Build table iteratively, checking length
    lines = []

    # Header
    header = " | ".join(str(col)[:col_widths[col]].ljust(col_widths[col]) for col in columns)
    lines.append(header)

    # Separator
    separator = "-+-".join("-" * col_widths[col] for col in columns)
    lines.append(separator)

    # Data rows - add as many as fit
    for item in items:
        row = " | ".join(
            truncate(str(item.get(col, "")), col_widths[col]).ljust(col_widths[col])
            for col in columns
        )
        test_table = "\n".join(lines + [row])
        full_message = header_text + test_table + footer_text

        if len(full_message) > max_length:
            # Can't fit more rows
            if len(lines) > 2:  # Have at least header + separator
                lines.append(f"... and {len(items) - (len(lines) - 2)} more")
            break
        lines.append(row)

    table = "\n".join(lines)
    return f"{header_text}{table}{footer_text}"


def get_recommendations_list(data: Any) -> list[dict[str, Any]]:
    """Extract list of recommendations from data.

    Args:
        data: JSON data from the recommendations endpoint.

    Returns:
        List of recommendation dictionaries.
    """
    if not data:
        return []

    if isinstance(data, dict):
        if "recommendations" in data:
            return data["recommendations"]
        return [data]

    return data if isinstance(data, list) else []


class RecommendationsScheduler:
    """Periodically fetches recommendations and posts to Discord."""

    def __init__(
        self,
        fetcher: RecommendationsFetcher,
        discord_webhook_url: str,
        poll_interval: int = 300,
        min_rvol: float = 2.0,
        check_rvol: bool = True,
        track_posted: bool = True,
        state_file: Optional[Path] = None,
    ):
        """Initialize the scheduler.

        Args:
            fetcher: Recommendations fetcher instance.
            discord_webhook_url: Discord webhook URL for posting.
            poll_interval: Seconds between fetches.
            min_rvol: Minimum RVOL to post (default 2.0).
            check_rvol: Whether to check RVOL from Finviz.
            track_posted: Whether to track posted tickers to avoid duplicates.
            state_file: Optional path for state file.
        """
        self.fetcher = fetcher
        self.discord_webhook_url = discord_webhook_url
        self.poll_interval = poll_interval
        self.min_rvol = min_rvol
        self.check_rvol = check_rvol
        self.track_posted = track_posted
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._discord_client: Optional[httpx.AsyncClient] = None
        self._finviz = FinvizChecker() if check_rvol else None
        self._tracker = PostedTickersTracker(state_file or DEFAULT_DB_FILE) if track_posted else None

    async def _get_discord_client(self) -> httpx.AsyncClient:
        """Get or create the Discord HTTP client."""
        if self._discord_client is None:
            self._discord_client = httpx.AsyncClient(timeout=30.0)
        return self._discord_client

    async def _post_to_discord(self, message: str) -> bool:
        """Post a message to Discord webhook.

        Args:
            message: Message content to post.

        Returns:
            True if successful, False otherwise.
        """
        try:
            client = await self._get_discord_client()
            response = await client.post(
                f"{self.discord_webhook_url}?wait=true",
                json={"content": message},
            )
            response.raise_for_status()
            logger.info("Posted recommendations to Discord")
            return True
        except Exception as e:
            logger.error(f"Failed to post to Discord: {e}")
            return False

    async def _should_post(self, item: dict[str, Any]) -> tuple[bool, Optional[float]]:
        """Check if a recommendation should be posted.

        Args:
            item: Recommendation item.

        Returns:
            Tuple of (should_post, rvol_value).
        """
        ticker = item.get("ticker", "")
        if not ticker:
            return False, None

        # Check if already posted
        if self._tracker and self._tracker.is_posted(ticker):
            logger.debug(f"{ticker}: Already posted, skipping")
            return False, None

        # Check RVOL from Finviz
        rvol = None
        if self._finviz:
            rvol = await self._finviz.get_rvol(ticker)
            if rvol is None:
                logger.warning(f"{ticker}: Could not fetch RVOL, skipping")
                return False, None
            if rvol < self.min_rvol:
                logger.info(f"{ticker}: RVOL {rvol:.2f} < {self.min_rvol}, skipping")
                return False, rvol

        return True, rvol

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        logger.info(f"Starting recommendations polling (interval: {self.poll_interval}s, min_rvol: {self.min_rvol})")

        while self._running:
            try:
                # Fetch recommendations
                data = await self.fetcher.fetch()
                items = get_recommendations_list(data)

                posted_count = 0
                for item in items:
                    ticker = item.get("ticker", "")

                    # Check if should post
                    should_post, rvol = await self._should_post(item)
                    if not should_post:
                        continue

                    # Format and post
                    message = format_single_recommendation(item, rvol)
                    if await self._post_to_discord(message):
                        posted_count += 1
                        # Mark as posted with metadata
                        if self._tracker:
                            self._tracker.mark_posted(
                                ticker,
                                rvol=rvol,
                                theme=item.get("theme"),
                                sector=item.get("sector"),
                            )

                    # Small delay between posts to avoid rate limiting
                    await asyncio.sleep(2)

                logger.info(f"Posted {posted_count}/{len(items)} recommendations (RVOL >= {self.min_rvol})")

            except Exception as e:
                logger.error(f"Error in recommendations poll: {e}")

            # Wait for next poll
            await asyncio.sleep(self.poll_interval)

    async def start(self) -> None:
        """Start the polling scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Recommendations scheduler started")

    async def stop(self) -> None:
        """Stop the polling scheduler."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._discord_client:
            await self._discord_client.aclose()
            self._discord_client = None

        if self._finviz:
            await self._finviz.close()

        if self._tracker:
            self._tracker.close()

        await self.fetcher.close()
        logger.info("Recommendations scheduler stopped")

    async def fetch_once(self) -> str:
        """Fetch recommendations once and return formatted table.

        Returns:
            Formatted table string.
        """
        data = await self.fetcher.fetch()
        return format_recommendations_table(data)

    async def fetch_and_post_once(self) -> tuple[int, int]:
        """Fetch recommendations once and post filtered ones to Discord.

        Returns:
            Tuple of (posted_count, total_count).
        """
        try:
            data = await self.fetcher.fetch()
            items = get_recommendations_list(data)

            if not items:
                logger.warning("No recommendations to post")
                return 0, 0

            posted_count = 0
            for item in items:
                ticker = item.get("ticker", "")

                # Check if should post
                should_post, rvol = await self._should_post(item)
                if not should_post:
                    continue

                # Format and post
                message = format_single_recommendation(item, rvol)
                if await self._post_to_discord(message):
                    posted_count += 1
                    # Mark as posted with metadata
                    if self._tracker:
                        self._tracker.mark_posted(
                            ticker,
                            rvol=rvol,
                            theme=item.get("theme"),
                            sector=item.get("sector"),
                        )

                # Small delay between posts to avoid rate limiting
                await asyncio.sleep(2)

            logger.info(f"Posted {posted_count}/{len(items)} recommendations (RVOL >= {self.min_rvol})")
            return posted_count, len(items)
        except Exception as e:
            logger.error(f"Failed to fetch and post: {e}")
            return 0, 0
