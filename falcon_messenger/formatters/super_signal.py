"""Formatter for super-signal stock alerts."""

from typing import Any, Optional

from falcon_messenger.formatters.base import BaseFormatter


class SuperSignalFormatter(BaseFormatter):
    """Formatter for super-signal stock alert messages."""

    def can_handle(self, metadata: Optional[dict[str, Any]]) -> bool:
        """Check if metadata indicates a super-signal alert.

        Args:
            metadata: The metadata to check.

        Returns:
            True if source is 'super-signal'.
        """
        if not metadata:
            return False
        return metadata.get("source") == "super-signal"

    def format(self, message: str, metadata: Optional[dict[str, Any]] = None) -> str:
        """Format a super-signal alert for social media.

        Args:
            message: The original message text.
            metadata: Optional metadata with ticker, risk_count, etc.

        Returns:
            Formatted message with emojis and structure.
        """
        if not metadata:
            return message

        ticker = metadata.get("ticker")
        risk_count = metadata.get("risk_count", 0)
        risk_flags = metadata.get("risk_flags", [])
        price = metadata.get("price")
        signal_type = metadata.get("signal_type", "alert")

        # Select appropriate emoji based on severity
        if risk_count >= 3:
            emoji = "\U0001F6A8"  # Police car light (high risk)
        elif risk_count >= 1:
            emoji = "\u26A0\uFE0F"  # Warning sign
        else:
            emoji = "\U0001F4CA"  # Bar chart (informational)

        # Build the formatted message
        lines = []

        # Header with ticker
        if ticker:
            header = f"{emoji} ${ticker}"
            if signal_type == "alert":
                header += " Alert"
            elif signal_type == "signal":
                header += " Signal"
            lines.append(header)
        else:
            lines.append(f"{emoji} Stock Alert")

        lines.append("")  # Blank line

        # Price if available
        if price is not None:
            lines.append(f"Price: ${price:.2f}")

        # Risk information
        if risk_count > 0:
            lines.append(f"Risk flags: {risk_count}")

        # List individual risk flags
        if risk_flags:
            lines.append("")
            for flag in risk_flags[:5]:  # Limit to 5 flags
                lines.append(f"\u2022 {flag}")

        # Original message if different from header
        if message and ticker and message.lower() != f"${ticker} alert".lower():
            lines.append("")
            lines.append(message)

        # Add hashtags for discoverability
        if ticker:
            lines.append("")
            lines.append(f"#{ticker} #stocks #trading")

        return "\n".join(lines)


def format_stock_alert(
    ticker: str,
    risk_flags: Optional[list[str]] = None,
    price: Optional[float] = None,
    message: Optional[str] = None,
) -> str:
    """Convenience function to format a stock alert.

    Args:
        ticker: Stock ticker symbol.
        risk_flags: List of risk flag descriptions.
        price: Current stock price.
        message: Additional message text.

    Returns:
        Formatted alert message.
    """
    formatter = SuperSignalFormatter()
    metadata = {
        "source": "super-signal",
        "ticker": ticker,
        "risk_flags": risk_flags or [],
        "risk_count": len(risk_flags) if risk_flags else 0,
        "price": price,
        "signal_type": "alert",
    }
    return formatter.format(message or "", metadata)
