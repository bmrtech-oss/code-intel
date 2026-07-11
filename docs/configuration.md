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
