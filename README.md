# falcon-messenger

Webhook/API server for publishing messages to Bluesky and Discord. Designed to integrate with [super-signal](https://github.com/TradingAsBuddies/super-signal) for stock alerts.

## Installation

```bash
pip install git+https://github.com/TradingAsBuddies/falcon-messenger.git
```

Or for development:

```bash
git clone https://github.com/TradingAsBuddies/falcon-messenger.git
cd falcon-messenger
pip install -e ".[dev]"
```

## Configuration

Set the following environment variables or create a `.env` file:

```bash
# Bluesky credentials
FALCON_BLUESKY_HANDLE=your.handle.bsky.social
FALCON_BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Discord webhook URL
FALCON_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Server settings (optional)
FALCON_HOST=0.0.0.0
FALCON_PORT=8080
FALCON_DEBUG=false
```

### Getting Credentials

**Bluesky App Password:**
1. Go to Settings > App Passwords on Bluesky
2. Create a new app password
3. Use your full handle (e.g., `username.bsky.social`)

**Discord Webhook:**
1. Go to Server Settings > Integrations > Webhooks
2. Create a new webhook
3. Copy the webhook URL

## Usage

### Start the Server

```bash
# Using the CLI
falcon-messenger serve

# With custom port
falcon-messenger serve --port 9000

# With environment file
falcon-messenger serve --env-file .env.production
```

### API Endpoints

#### POST /publish

Publish a message to configured platforms.

```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello from falcon-messenger!",
    "targets": ["bluesky", "discord"]
  }'
```

**Request Body:**

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Required. The message text to publish |
| `image_url` | string | Optional. URL of image to attach |
| `image_data` | string | Optional. Base64-encoded image data |
| `targets` | array | Optional. Target platforms. Default: all configured |
| `metadata` | object | Optional. Metadata for formatting (e.g., super-signal data) |

**Response:**

```json
{
  "success": true,
  "results": {
    "bluesky": {"success": true, "post_uri": "at://..."},
    "discord": {"success": true, "message_id": "123456"}
  }
}
```

#### GET /health

Health check endpoint.

```bash
curl http://localhost:8080/health
```

#### GET /config

Check configuration status.

```bash
curl http://localhost:8080/config
```

### CLI Commands

```bash
# Check configuration
falcon-messenger config --check

# Quick publish from CLI (for testing)
falcon-messenger publish "Test message" --target bluesky
falcon-messenger publish "Test message" --image ./chart.png --target discord
```

### Integration with super-signal

falcon-messenger includes special formatting for super-signal stock alerts. Include metadata in your request:

```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Stock alert",
    "metadata": {
      "source": "super-signal",
      "ticker": "AAPL",
      "risk_count": 3,
      "risk_flags": ["High volatility", "Insider selling", "Volume spike"],
      "price": 178.50
    }
  }'
```

This will format the message with emojis, structured information, and relevant hashtags.

### Python Client Example

```python
import httpx

async def publish_alert(message: str, ticker: str = None):
    async with httpx.AsyncClient() as client:
        payload = {"message": message}
        if ticker:
            payload["metadata"] = {
                "source": "super-signal",
                "ticker": ticker,
            }
        response = await client.post(
            "http://localhost:8080/publish",
            json=payload,
        )
        return response.json()
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=falcon_messenger

# Run linter
ruff check .
```

## Architecture

```
                    +------------------+
                    |  super-signal    |
                    |  (or any app)    |
                    +--------+---------+
                             | HTTP POST
                             v
                    +------------------+
                    | falcon-messenger |
                    |   API Server     |
                    +--------+---------+
                             |
              +--------------+--------------+
              v              v              v
        +----------+  +----------+  +----------+
        |  Bluesky |  |  Discord |  |  (future)|
        +----------+  +----------+  +----------+
```

## License

MIT License - see [LICENSE](LICENSE) for details.
