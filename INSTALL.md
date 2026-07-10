# Installation and Setup Guide

This guide walks through a complete local setup of Code-Intel, starting from prerequisites and ending with a small sample repository that can be indexed, queried, and used to generate requirements.

## 1. Prerequisites

### Supported environments
- Ubuntu 22.04+, Debian 12+, or WSL2 on Windows 10/11
- Python 3.11+
- Podman or Docker-compatible runtime
- Git

### Install system packages

On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git python3.11 python3.11-venv podman podman-compose
```

If you are using WSL2, make sure your distribution has access to the container runtime. On Windows, Podman Desktop or Docker Desktop can be used as the backend.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

## 2. Clone the repository

```bash
git clone https://github.com/bmrtech-oss/code-intel.git
cd code-intel
```

## 3. Create the Python environment

The project already includes a Linux virtual environment folder in the repo, but a fresh setup can be created with:

```bash
uv sync
```

If you want to use the repository-local environment explicitly:

```bash
uv venv .venv-linux
source .venv-linux/bin/activate
uv sync
```

## 4. Start the supporting services

The project expects PostgreSQL, Redis, and Ollama to be available. The repo includes a Compose file for this purpose.

```bash
podman-compose up -d
```

If you are using Docker instead of Podman, adjust the runtime command accordingly. Verify the services are running:

```bash
podman ps
```

You should see containers for the database, Redis, and Ollama.

### Pull a model for requirements generation

```bash
podman exec -it codeintel-ollama ollama pull phi3:mini
```

This may take several minutes depending on your network speed.

## 5. Start the API server

From the repo root:

```bash
uv run python -m src.cli.main serve
```

The API will be available at:
- http://localhost:8000/docs
- http://localhost:8000/requirements

You can verify the API is up with:

```bash
curl http://localhost:8000/docs | head
```

## 6. Create sample test data

A simple sample repository is enough to verify indexing, graph queries, and requirements generation.

### 6.1 Create a small sample project

```bash
mkdir -p /tmp/codeintel-sample/src
cat > /tmp/codeintel-sample/src/app.py <<'PY'
from src.helpers import format_message


def greet(name: str) -> str:
    return format_message(f"Hello {name}")


def unused_helper() -> str:
    return "unused"
PY

cat > /tmp/codeintel-sample/src/helpers.py <<'PY'
def format_message(text: str) -> str:
    return text.upper()
PY
```

This sample gives you:
- one function that is used by another function
- one unused helper that can appear in dead-code analysis

### 6.2 Index the sample repository

```bash
uv run python -m src.cli.main analyze /tmp/codeintel-sample --version sample-v1
```

The indexing step parses the sample files and writes facts into the versioned storage layer.

## 7. Exercise the core workflows

### 7.1 Query dead code

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "dead_code", "commit_sha": "sample-v1"}'
```

You should see the unused helper appear in the result set.

### 7.2 Query impact or call relationships

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "impact", "commit_sha": "sample-v1", "symbol": "src.app.greet"}'
```

### 7.3 Generate requirements

```bash
curl -X POST http://localhost:8000/requirements \
  -H "Content-Type: application/json" \
  -d '{"version": "sample-v1"}'
```

The endpoint returns structured requirements and stores traceability links for the underlying symbols.

## 8. Start the MCP server (optional)

If you want to use Code-Intel from an MCP-compatible client:

```bash
uv run python -m src.cli.main mcp
```

## 9. Start the web UI (optional)

If the frontend is available in your checkout:

```bash
cd ui
npm install
npm run dev
```

Then open http://localhost:5173.

## 10. Stop and reset services

Stop the containers:

```bash
podman-compose down
```

To remove volumes and reset the database:

```bash
podman-compose down -v
```

## 11. Troubleshooting

### API fails to start
- Check the logs with `podman logs codeintel-api`.
- Confirm the database and Redis containers are healthy.

### Requirements are empty
- Ensure Ollama is running and the model was pulled successfully.
- Verify the API can reach `http://ollama:11434` from the container network.

### Indexing reports no symbols
- Confirm the sample files exist at the path you passed into the analyzer.
- Check that the repository uses a supported extension such as `.py`.

## 12. Next steps

- Add more sample files in other languages.
- Try the MCP workflow with Claude Code or similar clients.
- Explore the benchmark script in the scripts folder for graph-engine comparisons.
