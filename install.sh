#!/bin/bash
set -e

# --- Configuration & Defaults ---
VENV_NAME=".venv"
SKIP_MODELS=false
COMPOSE_CMD=""
ENV_FILE=".env"
DEBUG=false
PURGE=false
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
    echo "  -p, --purge           Run cleanup (purge.sh) before starting installation"
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
        -p|--purge)
            PURGE=true
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

if [ "$PURGE" = true ]; then
    ./purge.sh
fi

echo "🚀 Starting Code-Intel One-Click Installation..."

# 0. Initialize .env if it doesn't exist
if [ ! -f "$ENV_FILE" ] && [ "$ENV_FILE" == ".env" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
fi

# 1. Mandatory LLM Configuration Prompt
CURRENT_PROVIDER=$(grep LLM_PROVIDER "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
CURRENT_KEY=$(grep LLM_API_KEY "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
CURRENT_GOOGLE_KEY=$(grep GOOGLE_API_KEY "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")

# If provider is not explicitly set in .env or keys are missing, prompt user
if [ -z "$CURRENT_PROVIDER" ] || ([ "$CURRENT_PROVIDER" == "google" ] && [ -z "$CURRENT_GOOGLE_KEY" ]) || ([ "$CURRENT_PROVIDER" == "openrouter" ] && [ -z "$CURRENT_KEY" ]); then
    echo ""
    echo "🤖 LLM Configuration (Required)"
    echo "----------------------------"
    echo "Code-Intel requires an LLM provider. Remote providers are RECOMMENDED for speed and space."
    echo "1) Google Gemini (Remote) [DEFAULT/FASTEST]"
    echo "2) OpenRouter (Remote)"
    echo "3) Ollama (Local - requires ~5GB space & slow download)"
    read -p "Select provider (1/2/3): " -n 1 -r LLM_CHOICE
    echo ""

    case "$LLM_CHOICE" in
        2)
            read -p "Enter OpenRouter API Key (sk-or-...): " INPUT_KEY
            if [ -n "$INPUT_KEY" ]; then
                sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=openrouter/" "$ENV_FILE"
                sed -i "s/LLM_MODEL=.*/LLM_MODEL=google\/gemini-flash-1.5/" "$ENV_FILE"
                if grep -q "LLM_API_KEY=" "$ENV_FILE"; then
                    sed -i "s/.*LLM_API_KEY=.*/LLM_API_KEY=$INPUT_KEY/" "$ENV_FILE"
                else
                    echo "LLM_API_KEY=$INPUT_KEY" >> "$ENV_FILE"
                fi
                SKIP_MODELS=true
            fi
            ;;
        3)
            sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=ollama/" "$ENV_FILE"
            sed -i "s/LLM_MODEL=.*/LLM_MODEL=phi3:mini/" "$ENV_FILE"
            ;;
        *) # Default to Google Gemini
            read -p "Enter Google API Key: " INPUT_KEY
            if [ -n "$INPUT_KEY" ]; then
                sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=google/" "$ENV_FILE"
                sed -i "s/LLM_MODEL=.*/LLM_MODEL=gemini-1.5-flash/" "$ENV_FILE"
                if grep -q "GOOGLE_API_KEY=" "$ENV_FILE"; then
                    sed -i "s/.*GOOGLE_API_KEY=.*/GOOGLE_API_KEY=$INPUT_KEY/" "$ENV_FILE"
                else
                    echo "GOOGLE_API_KEY=$INPUT_KEY" >> "$ENV_FILE"
                fi
                SKIP_MODELS=true
            else
                echo "⚠️ No key provided. Proceeding with default config (Ollama fallback)."
                sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=ollama/" "$ENV_FILE"
            fi
            ;;
    esac
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
    echo "Consider running './purge.sh' or switching to a remote LLM provider (Google Gemini)."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Verify engine is responsive with a timeout
echo "🚢 Checking container engine responsiveness..."
if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
    echo "⚠️ Warning: Container engine ($COMPOSE_CMD) is not responding within 15s."
    echo "Attempting to restart services..."
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
# Use --no-cache to save disk space
uv sync --extra agents --no-cache

# 3. Start Infrastructure
echo "🐳 Starting services (Postgres, Redis, Ollama)..."
UP_FLAGS="-d --build"
if [ "$DEBUG" = true ]; then
    UP_FLAGS="--build"
fi

if ! $COMPOSE_CMD --env-file "$ENV_FILE" up $UP_FLAGS; then
    echo "❌ Error: Failed to start containers. If out of space, run './purge.sh' and try remote LLM."
    exit 1
fi

if [ "$DEBUG" = true ]; then
    echo ""
    echo "⚠️ Debug session finished. Restart without -d to complete setup."
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
    echo "⏭️ Skipping Ollama model pull (using remote provider)."
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
