# --- Builder Stage ---
FROM python:3.11-slim AS builder

ARG TIER=minimal
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md uv.lock ./
COPY src/ /app/src/

# Conditional sync based on TIER
RUN uv venv /app/.venv && \
    if [ "$TIER" = "minimal" ]; then \
        uv sync --extra agents --no-cache; \
    elif [ "$TIER" = "standard" ]; then \
        uv sync --extra agents --extra semantic --no-cache; \
    else \
        # Remove CPU-only source override for high tier
        sed -i '/\[tool.uv.index\]/,/torch = { index = "pytorch-cpu" }/d' pyproject.toml && \
        uv sync --extra agents --extra semantic --no-cache; \
    fi

# --- Final Stage ---
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy project metadata (needed for uv run)
COPY pyproject.toml README.md uv.lock ./

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy code
COPY src/ /app/src/
COPY prompts/ /app/prompts/

# Environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Use the registered console script for reliability
CMD ["code-intel", "serve"]
