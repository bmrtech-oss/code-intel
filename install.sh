#!/bin/bash
set -e

# --- Configuration & Defaults ---
VENV_NAME=".venv"
SKIP_MODELS=false
COMPOSE_CMD=""
ENV_FILE=".env"

# --- Functions ---
show_help() {
    echo "Usage: ./install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --venv <name>     Specify the Python virtual environment name (default: .venv)"
    echo "  -s, --skip-models     Skip pulling Ollama models"
    echo "  -e, --env-file <path> Path to environment file (default: .env)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./install.sh --venv .myvenv"
    echo "  ./install.sh --skip-models"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--venv)
            VENV_NAME="$2"
            shift 2
            ;;
        -s|--skip-models)
            SKIP_MODELS=true
            shift
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "🚀 Starting Code-Intel One-Click Installation..."

# 1. Check prerequisites
echo "🔍 Checking prerequisites..."
if ! command -v uv >/dev/null 2>&1; then
    echo "❌ uv is required. Install it via 'curl -LsSf https://astral.sh/uv/install.sh | sh'"
    exit 1
fi

if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose or podman-compose is required."
    exit 1
fi
echo "✅ Using $COMPOSE_CMD"

# 2. Setup Python environment
echo "📦 Syncing Python dependencies (Env: $VENV_NAME)..."
export UV_PROJECT_ENVIRONMENT="$VENV_NAME"
uv sync

# 3. Start Infrastructure
echo "🐳 Starting services (Postgres, Redis, Ollama)..."
# Pass the env file to compose
$COMPOSE_CMD --env-file "$ENV_FILE" up -d --build

# 4. Wait for Postgres and run migrations
echo "⏳ Waiting for services to be ready..."
MAX_RETRIES=60
COUNT=0
until $COMPOSE_CMD exec -i api python -c "import sqlalchemy; print('API Ready')" > /dev/null 2>&1 || [ $COUNT -eq $MAX_RETRIES ]; do
  RUNNING_SERVICES=$($COMPOSE_CMD ps --format "{{.Service}} [{{.Status}}]" | tr '\n' ', ' | sed 's/, $//')
  echo "   [$COUNT/$MAX_RETRIES] Current status: $RUNNING_SERVICES"
  sleep 5
  COUNT=$((COUNT + 1))
done

if [ $COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Error: API service failed to start in time."
    $COMPOSE_CMD logs api
    exit 1
fi

echo "📂 Running database migrations..."
$COMPOSE_CMD exec -i api alembic upgrade head

# 5. Setup AI Agent Integrations
echo "🤖 Configuring AI agent integrations..."
./scripts/setup-agent.sh

# 6. Initialize local Ollama model
if [ "$SKIP_MODELS" = false ]; then
    MODEL=$(grep LLM_MODEL "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "phi3:mini")
    echo "🧠 Pulling Ollama model ($MODEL). This may take several minutes depending on your connection..."
    # Ensure -i is used for streaming output. -t might not work in all CI/non-interactive shells, but -i usually does.
    $COMPOSE_CMD exec -i ollama ollama pull "$MODEL"
else
    echo "⏭️ Skipping Ollama model pull."
fi

echo ""
echo "🎉 Code-Intel is now ready for use!"
echo "-----------------------------------"
echo "REST API:    http://localhost:8000"
echo "Web UI:      http://localhost:5173 (if frontend is running)"
echo "MCP Server:  Configured for Claude Desktop & Cursor"
echo ""
echo "To analyze your first repository:"
echo "uv run --env $VENV_NAME code-intel analyze <PATH>"
