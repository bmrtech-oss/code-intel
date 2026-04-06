# Installation Guide for Code Intelligence Platform

This guide walks you through installing and running the **Unified Dataflow Code Intelligence Platform** on a Linux environment (Ubuntu/Debian or WSL2). The platform uses Podman for containerization, PostgreSQL with pgvector, Redis, Ollama for LLM, and a FastAPI backend.

## 1. System Requirements

- **OS**: Ubuntu 22.04+, Debian 12+, or WSL2 on Windows 10/11
- **RAM**: Minimum 8 GB (16 GB recommended for LLM)
- **Disk**: 20 GB free space (models take ~4-8 GB)
- **CPU**: 4 cores (or more)
- **GPU**: Optional but recommended for LLM inference

## 2. Install Prerequisites

### 2.1 Install Podman and Podman-Compose

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y podman podman-compose

# Verify
podman --version
podman-compose --version
```

### 2.2 Install uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # or restart shell
uv --version
```

### 2.3 Install Git

```bash
sudo apt install -y git
```

### 2.4 (Optional) Install Python 3.11+ if not available

```bash
sudo apt install -y python3.11 python3.11-venv
```

## 3. Get the Source Code

Clone the repository (or use the `create_project_uv.sh` script to generate a fresh project). For this guide, we assume you already have the project directory `code-intel-unified/`.

```bash
git clone https://github.com/your-org/code-intel-unified.git
cd code-intel-unified
```

## 4. Build and Start Containers

### 4.1 Build the Images

```bash
podman-compose build --no-cache
```

This builds the `api` and `worker` images.

### 4.2 Start All Services

```bash
podman-compose up -d
```

Services started:
- `postgres` (PostgreSQL + pgvector)
- `redis` (for job queues)
- `ollama` (LLM server)
- `worker` (background ingestion)
- `api` (FastAPI server)

### 4.3 Check Container Status

```bash
podman ps
```

All containers should show `Up`.

### 4.4 Pull an LLM Model (e.g., phi3:mini)

```bash
podman exec -it codeintel-ollama ollama pull phi3:mini
```

This may take a few minutes depending on network.

## 5. Run Database Migrations

The API automatically creates tables on startup, but you can run migrations manually (if using Alembic). However, for first run, just restart the API:

```bash
podman restart codeintel-api
```

Wait 10 seconds, then check logs:

```bash
podman logs codeintel-api --tail 30
```

You should see `Application startup complete.`

## 6. Test the Installation

### 6.1 Health Check

```bash
curl http://localhost:8000/docs
```

You should see the Swagger UI.

### 6.2 Index a Sample Repository

Create a small test repo:

```bash
mkdir -p /tmp/test_repo
echo 'def hello(): pass' > /tmp/test_repo/test.py
```

Index it using the CLI inside the container:

```bash
podman exec -it codeintel-api uv run python -m src analyze /tmp/test_repo
```

### 6.3 Query for Dead Code

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "dead_code"}'
```

Expected output: `{"result": [{"symbol_id":"function:hello",...}]}`

### 6.4 Generate Requirements

```bash
curl -X POST http://localhost:8000/requirements
```

You should receive a JSON with epic, feature, user story, etc.

## 7. Using the CLI Locally (Optional)

If you want to run the CLI without entering the container, install the package in a virtual environment:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Now you can use `code-intel` commands:

```bash
code-intel analyze /tmp/test_repo
code-intel query dead_code
code-intel requirements
```

## 8. Configure MCP Server for Claude Code (Optional)

1. Create a file `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "code-intel": {
      "command": "podman",
      "args": ["exec", "-i", "codeintel-api", "uv", "run", "python", "-m", "src", "mcp"]
    }
  }
}
```

2. Restart Claude Code and verify the tools are available.

## 9. Stopping and Removing Containers

```bash
podman-compose down          # stop containers
podman-compose down -v       # also remove volumes (deletes database and models)
```

## 10. Troubleshooting

| Issue | Solution |
|-------|----------|
| `podman-compose: command not found` | Install via `pip install podman-compose` or your package manager. |
| `short-name` resolution errors | Add `unqualified-search-registries = ["docker.io"]` to `/etc/containers/registries.conf`. |
| API container crashes | Check logs: `podman logs codeintel-api`. Common issues: missing `git` in Dockerfile or missing Python dependencies. |
| Ollama model not responding | Ensure the model is pulled: `podman exec -it codeintel-ollama ollama list`. |
| Port 8000 already in use | Change host port in `podman-compose.yml` to `"8080:8000"` and update URLs accordingly. |
| Empty requirements output | Switch to a smaller model (e.g., `phi3:mini`), limit symbols in prompt, or increase timeout. |

## 11. Next Steps

- **Add more languages** – Extend tree‑sitter handlers for Java, COBOL, Delphi.
- **Deploy to Kubernetes** – Use the provided `podman-compose.yml` as a blueprint for AKS.
- **Build a Web UI** – Use the shared React component library.
- **Integrate with CI/CD** – Run `code-intel analyze` in your pipeline.

The platform is now ready for production use. For advanced configuration, refer to the documentation.