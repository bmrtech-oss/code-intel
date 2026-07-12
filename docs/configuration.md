# Code-Intel Configuration Guide

## Environment Variables

Code-Intel can be configured using environment variables. You can create a `.env` file in the root directory.

### Core Settings
- `DATABASE_URL`: PostgreSQL connection string (asyncpg).
- `REDIS_HOST`: Redis server hostname.
- `REDIS_PORT`: Redis server port (default: 6379).
- `READ_MODEL_STRICT_SYNC`: Whether to sync the read model (graph) immediately on fact insertion (default: true).
- `USE_TEMPORAL`: Enable Temporal.io for durable indexing (default: false).

### LLM Settings

#### Ollama (Default)
- `LLM_PROVIDER`: `ollama`
- `LLM_MODEL`: The model name (e.g., `phi3:mini`, `deepseek-coder`).
- `OLLAMA_URL`: URL to the Ollama API (default: `http://ollama:11434`).
- `LLM_TEMPERATURE`: LLM sampling temperature (default: 0.7).

#### OpenRouter / OpenAI Compatible
- `LLM_PROVIDER`: `openrouter`
- `LLM_MODEL`: The model identifier (e.g., `anthropic/claude-3-sonnet`).
- `LLM_API_KEY`: Your OpenRouter or OpenAI API key.
- `LLM_BASE_URL`: Base URL for the API (default: `https://openrouter.ai/api/v1`).
- `LLM_TEMPERATURE`: LLM sampling temperature (default: 0.7).

#### Google Gemini
- `LLM_PROVIDER`: `google`
- `LLM_MODEL`: The model identifier (e.g., `gemini-1.5-flash`).
- `GOOGLE_API_KEY`: Your Google AI Studio API key.
- `LLM_TEMPERATURE`: LLM sampling temperature (default: 0.7).

---

## Source Code Ingestion

Code-Intel supports indexing both local directories and remote Git repositories (GitHub, GitLab, Bitbucket, etc.).

### Local Directory
```bash
uv run code-intel analyze /path/to/local/repo
```

### Remote Git Repository
```bash
uv run code-intel analyze https://github.com/user/repo.git --branch main --depth 1
```
The platform will automatically clone the repository into a temporary directory, analyze it, and then clean up.

---

## Podman / Rocky Linux Troubleshooting

If you are using Podman on Rocky Linux (or RHEL) and the installation "hangs" or the engine becomes unresponsive:

1. **Storage Driver Performance**: Podman may report "Not using native diff for overlay." This causes slow image builds. Ensure your storage driver is optimized or use the `.dockerignore` file provided in the root to skip heavy local directories like `.venv`.
2. **Socket Deadlocks**: If `podman ps` hangs, the Podman socket might be deadlocked. The `install.sh` script will attempt to restart the services, but you can also run:
   ```bash
   sudo systemctl restart podman.socket podman.service
   ```
3. **SELinux**: SELinux can sometimes block Podman socket access. Check with `sudo journalctl -xeu podman`.
4. **System Reset**: As a last resort, if Podman is completely stuck, you can reset it (this deletes all your local containers and images):
   ```bash
   podman system reset
   ```
5. **Disk Space Management**: The platform footprint varies significantly based on the selected mode.

### Setup Footprint Comparison

| Mode | Host Space (`.venv`) | Image Space | Key Features |
| :--- | :--- | :--- | :--- |
| **Lightweight (Default)** | **~600 MB** | **~800 MB** | Graph, Impact, Dead Code, Gemini/OpenRouter |
| **Full (`--full`)** | **~6.3 GB** | **~5.5 GB** | All above + **Semantic Search** |

### Recommendations for Minimal Space:
1. **Use Cloud LLM**: Select Google Gemini or OpenRouter during setup to bypass the **5GB** Ollama model download.
2. **Skip Local Venv**: Use `./install.sh --skip-venv` to avoid the local footprint entirely; the app will run inside containers.
3. **Lightweight Mode**: Stay with the default (don't use `--full`) if you don't need semantic (natural language) search.

### Cleanup & Recovery:
- **Reset**: Run `./purge.sh` to completely remove all Code-Intel containers, images, and local caches.
- **Prune**: If you see "no space left on device":
  - `podman system prune -a`
  - `podman volume prune`

### Production & Performance: Switching to CUDA

By default, the platform uses **CPU-only** libraries to minimize disk usage (~600MB vs ~6GB). For large-scale production deployments where high-speed semantic search is required:

1. **Impact**: CPU-only mode is efficient for smaller repositories but will be slower for initial indexing of very large codebases (>1M lines).
2. **Switching to CUDA**:
   - In `pyproject.toml`, remove the `[[tool.uv.index]]` and `[tool.uv.sources]` sections related to `pytorch-cpu`.
   - Update `Dockerfile` to use a CUDA-enabled base image (e.g., `nvidia/cuda:12.1.0-base-ubuntu22.04`).
   - Run `uv sync --extra semantic` to pull the full GPU-enabled dependencies.

---

## Script Reference

### `install.sh`

The one-click installer handles dependency syncing, infrastructure startup, and model initialization.

**Defaults:**
- Virtual Environment: `.venv`
- Env File: `.env`
- Model Pulling: Enabled
- Container Engine: Auto-detected (Podman > Docker Compose plugin > Docker-compose)

**Options:**
- `-v, --venv <name>`: Specify custom Python virtual environment.
- `-s, --skip-models`: Skip pulling Ollama models (useful if using OpenRouter).
- `-e, --env-file <path>`: Use a specific environment file.
- `-h, --help`: Show help.

### `demo.sh`

Runs an end-to-end strategic demo of the platform's capabilities.

**Defaults:**
- LLM Provider: `ollama`
- LLM Model: `phi3:mini`

**Remote Optimization:**
If an `--api-key` or `LLM_API_KEY` is detected, the script automatically switches the provider to `openrouter` and uses `google/gemini-flash-1.5` as a fast default to avoid local download delays.

**Options:**
- `--provider <name>`: LLM Provider (ollama|openrouter).
- `--model <name>`: LLM Model identifier.
- `--api-key <key>`: API Key for remote provider.
- `--base-url <url>`: Base URL for remote provider.
- `-h, --help`: Show help.
