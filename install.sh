#!/bin/bash
set -e

# --- Configuration & Defaults ---
VENV_NAME=".venv"
SKIP_MODELS=false
COMPOSE_CMD=""
ENV_FILE=".env"
DEBUG=false
PURGE=false
REQUIRED_SPACE_GB=3
SKIP_VENV=false
LIGHTWEIGHT=true

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
    echo "  --skip-venv           Skip creating local virtual environment (saves host space)"
    echo "  --full                Install heavy AI dependencies (Torch/Semantic Search, ~5GB extra)"
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
        --skip-venv)
            SKIP_VENV=true
            shift
            ;;
        --full)
            LIGHTWEIGHT=false
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
CURRENT_GOOGLE_KEY=$(grep GOOGLE_API_KEY "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
CURRENT_OR_KEY=$(grep LLM_API_KEY "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")

if [ -z "$CURRENT_PROVIDER" ] || ([ "$CURRENT_PROVIDER" == "google" ] && [ -z "$CURRENT_GOOGLE_KEY" ]) || ([ "$CURRENT_PROVIDER" == "openrouter" ] && [ -z "$CURRENT_OR_KEY" ]); then
    echo ""
    echo "🤖 LLM Configuration (Mandatory)"
    echo "----------------------------"
    echo "To save space and ensure high performance, a cloud provider is RECOMMENDED."
    echo "1) Google Gemini (Remote) [DEFAULT - FASTEST/SMALLEST FOOTPRINT]"
    echo "2) OpenRouter (Remote)"
    echo "3) Ollama (Local - ⚠️ Requires ~5GB extra disk space and slow model download)"

    if [ -t 0 ]; then
        read -p "Selection (1/2/3): " -n 1 -r LLM_CHOICE
        echo ""
    else
        read -r LLM_CHOICE
    fi

    case "$LLM_CHOICE" in
        2)
            read -p "Enter OpenRouter API Key (sk-or-...): " INPUT_KEY
            if [ -n "$INPUT_KEY" ]; then
                DEFAULT_MODEL="google/gemini-flash-1.5"
                read -p "Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
                INPUT_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}

                sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=openrouter|" "$ENV_FILE"
                sed -i "s|LLM_MODEL=.*|LLM_MODEL=$INPUT_MODEL|" "$ENV_FILE"
                if grep -q "LLM_API_KEY=" "$ENV_FILE"; then
                    sed -i "s|.*LLM_API_KEY=.*|LLM_API_KEY=$INPUT_KEY|" "$ENV_FILE"
                else
                    echo "LLM_API_KEY=$INPUT_KEY" >> "$ENV_FILE"
                fi
                SKIP_MODELS=true
            fi
            ;;
        3)
            sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" "$ENV_FILE"
            sed -i "s|LLM_MODEL=.*|LLM_MODEL=phi3:mini|" "$ENV_FILE"
            ;;
        *) # Default: Google Gemini
            read -p "Enter Google Gemini API Key: " INPUT_KEY
            if [ -n "$INPUT_KEY" ]; then
                DEFAULT_MODEL="gemini-1.5-flash"
                read -p "Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
                INPUT_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}

                sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=google|" "$ENV_FILE"
                sed -i "s|LLM_MODEL=.*|LLM_MODEL=$INPUT_MODEL|" "$ENV_FILE"
                if grep -q "GOOGLE_API_KEY=" "$ENV_FILE"; then
                    sed -i "s|.*GOOGLE_API_KEY=.*|GOOGLE_API_KEY=$INPUT_KEY|" "$ENV_FILE"
                else
                    echo "GOOGLE_API_KEY=$INPUT_KEY" >> "$ENV_FILE"
                fi
                SKIP_MODELS=true
                echo "✅ Configured for Google Gemini ($INPUT_MODEL)."
            else
                echo "⚠️ No key provided. Falling back to Ollama local defaults."
                sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" "$ENV_FILE"
            fi
            ;;
    esac
fi

FINAL_PROVIDER=$(grep LLM_PROVIDER "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "ollama")
[ "$FINAL_PROVIDER" != "ollama" ] && SKIP_MODELS=true

# 2. Check prerequisites
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
if [ "$FREE_SPACE_GB" -lt "$REQUIRED_SPACE_GB" ]; then
    echo "⚠️ Warning: Low disk space detected ($FREE_SPACE_GB GB available)."
    if [ "$SKIP_MODELS" = false ]; then
        echo "Local Ollama models require ~5GB. Please switch to a remote provider or free up space."
        if [ -t 0 ]; then
            read -p "Continue anyway? (y/N) " -n 1 -r
            echo ""
            [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
        fi
    fi
fi

# Verify engine is responsive
echo "🚢 Checking container engine responsiveness..."
if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
    echo "⚠️ Warning: Container engine ($COMPOSE_CMD) is not responding. Attempting restart..."
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl restart podman.socket podman.service 2>/dev/null || true
    fi
    sleep 5
    if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
        echo "❌ Error: Container engine is still not responding. Run: podman system reset"
        exit 1
    fi
fi

# 3. Setup Python environment
if [ "$SKIP_VENV" = false ]; then
    echo "📦 Syncing Python dependencies (Env: $VENV_NAME)..."
    export UV_PROJECT_ENVIRONMENT="$VENV_NAME"
    if [ "$LIGHTWEIGHT" = true ]; then
        echo "⚡ Using Lightweight mode (excludes heavy semantic search libs)."
        uv sync --extra agents --no-cache
    else
        echo "🚀 Using Full mode (includes all AI/Semantic Search libs, ~5GB)."
        uv sync --extra agents --extra semantic --no-cache
    fi
else
    echo "⏭️ Skipping local virtual environment creation."
fi

# 4. Start Infrastructure
echo "🐳 Starting services (Postgres, Redis, Ollama)..."
UP_FLAGS="-d --build"
[ "$DEBUG" = true ] && UP_FLAGS="--build"

# Pass whether to use lightweight mode to containers via env
export CODEINTEL_LIGHTWEIGHT="$LIGHTWEIGHT"

if ! $COMPOSE_CMD --env-file "$ENV_FILE" up $UP_FLAGS; then
    echo "❌ Error: Failed to start containers. If 'no space left', run './purge.sh' and use cloud LLM."
    exit 1
fi

[ "$DEBUG" = true ] && exit 0

# 5. Wait for API
echo "⏳ Waiting for services to be ready..."
MAX_RETRIES=60
COUNT=0
until timeout 10s $COMPOSE_CMD exec -i api python -c "import sqlalchemy; print('API Ready')" > /dev/null 2>&1 || [ $COUNT -eq $MAX_RETRIES ]; do
  if [[ "$COMPOSE_CMD" == "docker compose" ]]; then
      # Only try to ps if we are using docker compose v2
      RUNNING_SERVICES=$(timeout 5s $COMPOSE_CMD ps --format "{{.Service}} [{{.Status}}]" 2>/dev/null | tr '\n' ', ' | sed 's/, $//')
      [ -n "$RUNNING_SERVICES" ] && echo "   [$COUNT/$MAX_RETRIES] Status: $RUNNING_SERVICES" || echo "   [$COUNT/$MAX_RETRIES] Waiting for API..."
  else
      echo "   [$COUNT/$MAX_RETRIES] Waiting for API..."
  fi
  sleep 5
  COUNT=$((COUNT + 1))
done

if [ $COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Error: API service failed to start."
    exit 1
fi

echo "📂 Running migrations..."
$COMPOSE_CMD exec -i api alembic upgrade head

# 6. Setup Agents
echo "🤖 Configuring AI agent integrations..."
./scripts/setup-agent.sh

# 7. Model Pull
if [ "$SKIP_MODELS" = false ]; then
    MODEL=$(grep LLM_MODEL "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "phi3:mini")
    echo "🧠 Pulling Ollama model ($MODEL)..."
    $COMPOSE_CMD exec -i ollama ollama pull "$MODEL"
else
    echo "⏭️ Skipping Ollama model pull (using remote provider)."
fi

echo ""
echo "🎉 Code-Intel is now ready for use!"
echo "-----------------------------------"
echo "To analyze your first repository:"
if [ "$SKIP_VENV" = false ]; then
    echo "uv run --env $VENV_NAME code-intel analyze <PATH>"
else
    echo "curl -X POST http://localhost:8000/analyze -d '{\"repo_path\": \"<PATH>\"}'"
fi
