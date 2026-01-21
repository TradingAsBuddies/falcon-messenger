FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY falcon_messenger/ ./falcon_messenger/

# Install the package
RUN pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Default environment variables (can be overridden at runtime)
ENV FALCON_HOST=0.0.0.0
ENV FALCON_PORT=8080
ENV FALCON_VERIFY_SSL=false
ENV FALCON_POLL_INTERVAL=300

# Expose the API port
EXPOSE 8080

# Default command: run the recommendations scheduler
# Override with different commands:
#   - "serve" for API server
#   - "recommendations --once" for single fetch
CMD ["falcon-messenger", "recommendations"]
