#!/bin/bash
# Example curl commands for falcon-messenger API

BASE_URL="${FALCON_URL:-http://localhost:8080}"

echo "=== falcon-messenger API Examples ==="
echo ""

# Health check
echo "1. Health Check"
echo "---------------"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""

# Configuration check
echo "2. Configuration Check"
echo "----------------------"
curl -s "$BASE_URL/config" | python3 -m json.tool
echo ""

# Simple text message to all targets
echo "3. Publish Simple Message (all targets)"
echo "----------------------------------------"
curl -s -X POST "$BASE_URL/publish" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello from falcon-messenger!"
  }' | python3 -m json.tool
echo ""

# Message to specific target
echo "4. Publish to Bluesky Only"
echo "--------------------------"
curl -s -X POST "$BASE_URL/publish" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "This goes to Bluesky only",
    "targets": ["bluesky"]
  }' | python3 -m json.tool
echo ""

# Message with super-signal metadata
echo "5. Publish Stock Alert (super-signal format)"
echo "---------------------------------------------"
curl -s -X POST "$BASE_URL/publish" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Stock alert triggered",
    "metadata": {
      "source": "super-signal",
      "ticker": "AAPL",
      "risk_count": 3,
      "risk_flags": ["High volatility", "Insider selling", "Volume spike"],
      "price": 178.50
    }
  }' | python3 -m json.tool
echo ""

# Message with image URL
echo "6. Publish with Image URL"
echo "-------------------------"
curl -s -X POST "$BASE_URL/publish" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Check out this chart!",
    "image_url": "https://example.com/chart.png"
  }' | python3 -m json.tool
echo ""

echo "=== Done ==="
