# Installation and Setup Guide

This guide walks through a complete local setup of Code-Intel, starting from prerequisites and ending with a small sample repository that can be indexed, queried, and used to generate requirements.

## 🚀 Quick Start (One-Click)

The easiest way to get started is using the provided installation script:

```bash
./install.sh
```

This script automates:
- Dependency syncing via `uv`.
- Infrastructure startup (PostgreSQL, Redis, Ollama).
- Database migrations.
- Ollama model initialization.

For advanced options (skipping models, custom venv), run `./install.sh --help`.

---

## 1. Prerequisites

### Supported environments
- Ubuntu 22.04+, Debian 12+, or WSL2 on Windows 10/11
- Python 3.11+
- Podman or Docker-compatible runtime (including Docker Compose V2 plugin)
- Git

### Install system packages

On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git python3.11 python3.11-venv podman podman-compose
```

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Configuration

Code-Intel is configured via environment variables. See [Configuration Guide](docs/configuration.md) for details.

To use **OpenRouter** (Cloud LLM) instead of local Ollama:
1. Create a `.env` file (copy from `.env.example`).
2. Set `LLM_PROVIDER=openrouter` and your `LLM_API_KEY`.
3. Run `./install.sh --skip-models`.

---

## 3. Running the Strategic Demo

To verify everything is working correctly, run the strategic demo:

```bash
./demo.sh
```

If you are using OpenRouter, you can speed up the demo significantly:
```bash
./demo.sh --api-key YOUR_OPENROUTER_KEY
```

---

## 4. Manual Setup (Optional)

If you prefer a manual flow instead of using `install.sh`:

### 4.1 Create the Python environment
```bash
uv sync
```

### 4.2 Start the supporting services
```bash
podman-compose up -d
# Run database migrations
uv run alembic upgrade head
```

### 4.3 Pull a model (if using local Ollama)
```bash
podman exec -it codeintel-ollama ollama pull phi3:mini
```

### 4.4 Start the API server
```bash
uv run code-intel serve
```

---

## 5. Troubleshooting

### API fails to start
- Check the logs with `podman logs codeintel-api` (if using containers) or check your terminal output.
- Confirm the database and Redis containers are healthy.

### Requirements generation issues
- If using Ollama, ensure the model was pulled successfully.
- If using OpenRouter, verify your API key and internet connectivity.
- Check [docs/configuration.md](docs/configuration.md) to ensure your provider settings match.

---

## 6. Next steps

- [docs/use_cases_guide.md](docs/use_cases_guide.md) — practical use cases.
- [docs/agent-integrations.md](docs/agent-integrations.md) — connecting to Claude or Cursor.
- [docs/configuration.md](docs/configuration.md) — advanced settings.
