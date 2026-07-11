#!/bin/bash
set -e

# --- Configuration & Defaults ---
VENV_NAME=".venv"
SKIP_MODELS=false
COMPOSE_CMD=""
ENV_FILE=".env"
DEBUG=false
REQUIRED_SPACE_GB=5

# --- Functions ---
show_help() {
    echo "Usage: ./install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --venv <name>     Specify the Python virtual environment name (default: .venv)"
    echo "  -s, --skip-models     Skip pulling Ollama models"
    echo "  -e, --env-file <path> Path to environment file (default: .env)"
    echo "  -d, --debug           Enable debug mode (don't detach containers, show full logs)"
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
        -d|--debug)
            DEBUG=true
            shift
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

# 0. Initialize .env if it doesn't exist
if [ ! -f "$ENV_FILE" ] && [ "$ENV_FILE" == ".env" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
fi

# 1. LLM Configuration Prompt (if not configured)
CURRENT_PROVIDER=$(grep LLM_PROVIDER "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "ollama")
CURRENT_KEY=$(grep LLM_API_KEY "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")

if [ "$CURRENT_PROVIDER" == "ollama" ] && [ -z "$CURRENT_KEY" ] && [ -z "$LLM_API_KEY" ]; then
    echo ""
    echo "🤖 LLM Configuration"
    echo "-----------------"
    echo "Code-Intel needs an LLM to generate requirements."
    echo "Would you like to use a remote provider (faster, cloud-based) or local Ollama (private, requires ~5GB space)?"
    echo "1) Remote (OpenRouter/OpenAI Compatible) [RECOMMENDED]"
    echo "2) Local (Ollama)"
    read -p "Selection (1/2): " -n 1 -r LLM_CHOICE
    echo ""

    if [[ "$LLM_CHOICE" == "1" ]]; then
        read -p "Enter your OpenRouter API Key (sk-or-...): " INPUT_KEY
        if [ -n "$INPUT_KEY" ]; then
            # Update .env
            sed -i "s/LLM_PROVIDER=ollama/LLM_PROVIDER=openrouter/" "$ENV_FILE"
            sed -i "s/LLM_MODEL=phi3:mini/LLM_MODEL=google\/gemini-flash-1.5/" "$ENV_FILE"
            # Replace commented or empty API key
            if grep -q "LLM_API_KEY=" "$ENV_FILE"; then
                sed -i "s/.*LLM_API_KEY=.*/LLM_API_KEY=$INPUT_KEY/" "$ENV_FILE"
            else
                echo "LLM_API_KEY=$INPUT_KEY" >> "$ENV_FILE"
            fi
            SKIP_MODELS=true
            echo "✅ Configured for OpenRouter. Skipping local model downloads."
        else
            echo "⚠️ No key provided. Falling back to local Ollama."
        fi
    fi
fi

# Re-check SKIP_MODELS based on final provider
FINAL_PROVIDER=$(grep LLM_PROVIDER "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "ollama")
if [ "$FINAL_PROVIDER" != "ollama" ]; then
    SKIP_MODELS=true
fi

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

# Disk Space Check
FREE_SPACE=$(df -k . | awk 'NR==2 {print $4}')
FREE_SPACE_GB=$((FREE_SPACE / 1024 / 1024))
if [ "$FREE_SPACE_GB" -lt "$REQUIRED_SPACE_GB" ] && [ "$SKIP_MODELS" = false ]; then
    echo "⚠️ Warning: Low disk space detected ($FREE_SPACE_GB GB available). Local Ollama models may fail to pull."
    echo "Consider running 'podman system prune -a' or switching to a remote LLM provider."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Verify engine is responsive
echo "🚢 Checking container engine responsiveness..."
if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
    echo "⚠️ Warning: Container engine ($COMPOSE_CMD) is not responding within 15s."
    echo "Attempting to restart Podman/Docker services..."

    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl restart podman.socket podman.service 2>/dev/null || true
    fi

    sleep 5
    if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
        echo "❌ Error: Container engine is still not responding."
        exit 1
    fi
    echo "✅ Container engine recovered."
fi

# 2. Setup Python environment
echo "📦 Syncing Python dependencies (Env: $VENV_NAME)..."
export UV_PROJECT_ENVIRONMENT="$VENV_NAME"
uv sync

# 3. Start Infrastructure
echo "🐳 Starting services (Postgres, Redis, Ollama)..."
UP_FLAGS="-d --build"
if [ "$DEBUG" = true ]; then
    echo "🐞 Debug mode enabled. Showing full logs..."
    UP_FLAGS="--build"
fi

if ! $COMPOSE_CMD --env-file "$ENV_FILE" up $UP_FLAGS; then
    echo "❌ Error: Failed to start containers. Check logs or disk space."
    exit 1
fi

if [ "$DEBUG" = true ]; then
    echo ""
    echo "⚠️ Debug session finished. Restart without -d to complete the setup."
    exit 0
fi

# 4. Wait for Postgres and run migrations
echo "⏳ Waiting for services to be ready..."
MAX_RETRIES=60
COUNT=0
until timeout 10s $COMPOSE_CMD exec -i api python -c "import sqlalchemy; print('API Ready')" > /dev/null 2>&1 || [ $COUNT -eq $MAX_RETRIES ]; do
  if [[ "$COMPOSE_CMD" == "docker compose" ]]; then
      RUNNING_SERVICES=$(timeout 5s $COMPOSE_CMD ps --format "{{.Service}} [{{.Status}}]" | tr '\n' ', ' | sed 's/, $//')
      echo "   [$COUNT/$MAX_RETRIES] Status: $RUNNING_SERVICES"
  else
      echo "   [$COUNT/$MAX_RETRIES] Waiting for API service..."
  fi
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
    echo "🧠 Pulling Ollama model ($MODEL). This may take several minutes..."
    $COMPOSE_CMD exec -i ollama ollama pull "$MODEL"
else
    echo "⏭️ Skipping Ollama model pull (using remote provider or --skip-models)."
fi

echo ""
echo "🎉 Code-Intel is now ready for use!"
echo "-----------------------------------"
echo "REST API:    http://localhost:8000"
echo "Web UI:      http://localhost:5173"
echo "MCP Server:  Configured for Claude Desktop & Cursor"
echo ""
echo "To analyze your first repository:"
echo "uv run --env $VENV_NAME code-intel analyze <PATH>"
