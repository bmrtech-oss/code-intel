# --- Builder Stage ---
FROM python:3.11-slim AS builder

WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ARG LIGHTWEIGHT=true
COPY pyproject.toml README.md ./
# Use --no-cache and specialized venv location
RUN uv venv /app/.venv && \
    if [ "$LIGHTWEIGHT" = "true" ]; then \
        uv sync --extra agents --no-cache; \
    else \
        uv sync --extra agents --extra semantic --no-cache; \
    fi

# --- Final Stage ---
FROM python:3.11-slim

WORKDIR /app

# Copy only the virtual environment and uv binary
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Install minimal runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy source code and prompts
COPY src/ /app/src/
COPY prompts/ /app/prompts/

# Configure environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
# Ensure python doesn't write .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "-m", "src", "serve"]
