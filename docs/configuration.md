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

## Installation

Run the one-click installer:
```bash
./install.sh
```

For more options:
```bash
./install.sh --help
```

## Running the Demo

To see Code-Intel in action:
```bash
./demo.sh
```
