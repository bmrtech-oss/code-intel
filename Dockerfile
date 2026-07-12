# --- Builder Stage ---
FROM python:3.11-slim AS builder

ARG TIER=minimal
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./

# Conditional sync based on TIER
# minimal:  no semantic extra, cpu torch
# standard: semantic extra, cpu torch
# high:     semantic extra, full torch (requires removing cpu index)
RUN uv venv /app/.venv && \
    if [ "$TIER" = "minimal" ]; then \
        uv sync --extra agents --no-cache; \
    elif [ "$TIER" = "standard" ]; then \
        uv sync --extra agents --extra semantic --no-cache; \
    else \
        # For 'high' tier, we remove the CPU-only source override to allow full CUDA torch
        sed -i '/\[tool.uv.index\]/,/torch = { index = "pytorch-cpu" }/d' pyproject.toml && \
        uv sync --extra agents --extra semantic --no-cache; \
    fi

# --- Final Stage ---
# Use nvidia base for high tier, slim for others
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
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "-m", "src", "serve"]
