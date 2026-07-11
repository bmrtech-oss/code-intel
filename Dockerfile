# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
RUN uv venv /app/.venv && uv sync --no-cache

# Final stage
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY src/ /app/src/
COPY prompts/ /app/prompts/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

CMD ["uv", "run", "python", "-m", "src", "serve"]
