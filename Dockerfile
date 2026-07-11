FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and clean up apt cache in the same layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install uv and sync dependencies.
# We use --no-cache to keep the image small.
RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
RUN uv venv && uv sync --no-cache

COPY src/ /app/src/
COPY prompts/ /app/prompts/

ENV PYTHONPATH=/app
