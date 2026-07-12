#!/bin/bash
set -e

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Configuration & Defaults ---
VENV_NAME=".venv"
SKIP_MODELS=false
COMPOSE_CMD=""
ENV_FILE=".env"
DEBUG=false
PURGE=false
REQUIRED_SPACE_GB=2
SKIP_VENV=false
PERFORMANCE_TIER="minimal"

# --- Functions ---
log_info() { echo -e "${BLUE}info:${NC} $1"; }
log_success() { echo -e "${GREEN}success:${NC} $1"; }
log_warn() { echo -e "${YELLOW}warning:${NC} $1"; }
log_error() { echo -e "${RED}error:${NC} $1"; }

show_help() {
    echo "Usage: ./install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --venv <name>     Specify virtual environment name (default: .venv)"
    echo "  -s, --skip-models     Skip pulling Ollama models"
    echo "  -e, --env-file <path> Path to environment file (default: .env)"
    echo "  -d, --debug           Enable debug mode (show full logs)"
    echo "  -p, --purge           Run cleanup (purge.sh) before starting"
    echo "  --skip-venv           Skip creating local venv"
    echo "  --tier <tier>         Set performance tier (minimal|standard|high)"
    echo "  -h, --help            Show this help message"
}

check_port() {
    local port=$1
    local name=$2
    if command -v lsof >/dev/null 2>&1; then
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
            log_error "Port $port ($name) is already in use."
            return 1
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep -q ":$port " ; then
            log_error "Port $port ($name) is already in use."
            return 1
        fi
    fi
    return 0
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--venv) VENV_NAME="$2"; shift 2 ;;
        -s|--skip-models) SKIP_MODELS=true; shift ;;
        -e|--env-file) ENV_FILE="$2"; shift 2 ;;
        -d|--debug) DEBUG=true; shift ;;
        -p|--purge) PURGE=true; shift ;;
        --skip-venv) SKIP_VENV=true; shift ;;
        --tier) PERFORMANCE_TIER="$2"; shift 2 ;;
        -h|--help) show_help; exit 0 ;;
        *) log_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

if [ "$PURGE" = true ]; then
    ./purge.sh
fi

echo -e "${CYAN}🚀 Starting Code-Intel One-Click Installation...${NC}"

# 0. Initialize .env
[ ! -f "$ENV_FILE" ] && [ "$ENV_FILE" == ".env" ] && cp .env.example .env

# 1. Package Structure Fix
log_info "Verifying package structure..."
touch src/lang/__init__.py
touch src/storage/__init__.py
touch src/cache/__init__.py
touch src/analytics/__init__.py
touch src/semantic/__init__.py

# 2. Mandatory LLM Configuration Prompt
CURRENT_PROVIDER=$(grep "^LLM_PROVIDER=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
CURRENT_GOOGLE_KEY=$(grep "^GOOGLE_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
CURRENT_OR_KEY=$(grep "^LLM_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")

SHOULD_PROMPT=false
if [ -z "$CURRENT_PROVIDER" ] || [ "$CURRENT_PROVIDER" == "ollama" ]; then
    SHOULD_PROMPT=true
elif [ "$CURRENT_PROVIDER" == "google" ] && [ -z "$CURRENT_GOOGLE_KEY" ]; then
    SHOULD_PROMPT=true
elif [ "$CURRENT_PROVIDER" == "openrouter" ] && [ -z "$CURRENT_OR_KEY" ]; then
    SHOULD_PROMPT=true
fi

if [ "$SHOULD_PROMPT" = true ]; then
    echo ""
    echo -e "${CYAN}🤖 LLM Configuration (Mandatory)${NC}"
    echo "----------------------------"
    echo "To save disk space and ensure high performance, a cloud provider is RECOMMENDED."
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

                sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=openrouter|" "$ENV_FILE"
                sed -i "s|^LLM_MODEL=.*|LLM_MODEL=$INPUT_MODEL|" "$ENV_FILE"
                if grep -q "^LLM_API_KEY=" "$ENV_FILE"; then
                    sed -i "s|^LLM_API_KEY=.*|LLM_API_KEY=$INPUT_KEY|" "$ENV_FILE"
                else
                    echo "LLM_API_KEY=$INPUT_KEY" >> "$ENV_FILE"
                fi
                SKIP_MODELS=true
            fi
            ;;
        3)
            sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" "$ENV_FILE"
            sed -i "s|^LLM_MODEL=.*|LLM_MODEL=phi3:mini|" "$ENV_FILE"
            ;;
        *) # Default: Google Gemini
            read -p "Enter Google Gemini API Key: " INPUT_KEY
            if [ -n "$INPUT_KEY" ]; then
                DEFAULT_MODEL="gemini-1.5-flash"
                read -p "Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
                INPUT_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}

                sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=google|" "$ENV_FILE"
                sed -i "s|^LLM_MODEL=.*|LLM_MODEL=$INPUT_MODEL|" "$ENV_FILE"
                if grep -q "^GOOGLE_API_KEY=" "$ENV_FILE"; then
                    sed -i "s|^GOOGLE_API_KEY=.*|GOOGLE_API_KEY=$INPUT_KEY|" "$ENV_FILE"
                else
                    echo "GOOGLE_API_KEY=$INPUT_KEY" >> "$ENV_FILE"
                fi
                SKIP_MODELS=true
                log_success "Configured for Google Gemini ($INPUT_MODEL)."
            else
                echo "⚠️ No key provided. Falling back to Ollama local defaults."
                sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" "$ENV_FILE"
            fi
            ;;
    esac
fi

# 3. Performance Tier Selection
echo ""
echo -e "${CYAN}⚡ Performance & Feature Tier${NC}"
echo "--------------------------"
echo "1) Minimal  (~600MB image) - Graph only. No Semantic Search."
echo "2) Standard (~2.5GB image) - Semantic Search enabled (CPU optimized)."
echo "3) High     (~7GB image)   - Semantic Search enabled (Nvidia CUDA accelerated)."
if [ -t 0 ]; then read -p "Selection (1/2/3): " -n 1 -r TIER_CHOICE; echo ""; else read -r TIER_CHOICE; fi

case "$TIER_CHOICE" in
    2) PERFORMANCE_TIER="standard" ;;
    3) PERFORMANCE_TIER="high" ;;
    *) PERFORMANCE_TIER="minimal" ;;
esac

# 4. Port Conflict Check
log_info "Checking for port conflicts..."
CONFLICT=false
check_port 8000 "API" || CONFLICT=true
check_port 5432 "Postgres" || CONFLICT=true
check_port 6379 "Redis" || CONFLICT=true

FINAL_PROVIDER=$(grep "^LLM_PROVIDER=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "ollama")
if [ "$FINAL_PROVIDER" == "ollama" ]; then
    [ "$SKIP_MODELS" = false ] && { check_port 11434 "Ollama" || CONFLICT=true; }
fi

if [ "$CONFLICT" = true ]; then
    log_error "Port conflicts detected. Stop conflicting services or run './purge.sh'."
    exit 1
fi

# 5. Check prerequisites
log_info "Checking prerequisites..."
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
    log_error "docker-compose or podman-compose is required."; exit 1
fi
echo "✅ Using $COMPOSE_CMD"

# Verify engine
if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
    log_warn "Container engine is not responding. Attempting restart..."
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl restart podman.socket podman.service 2>/dev/null || true
    fi
    sleep 5
    if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
        echo "❌ Error: Container engine is still not responding. Run: podman system reset"
        exit 1
    fi
fi

# 6. Setup Python environment
if [ "$SKIP_VENV" = false ]; then
    log_info "Syncing host environment..."
    export UV_PROJECT_ENVIRONMENT="$VENV_NAME"
    if [ "$PERFORMANCE_TIER" == "minimal" ]; then
        uv sync --extra agents --no-cache
    else
        uv sync --extra agents --extra semantic --no-cache
    fi
else
    log_info "Skipping local virtual environment creation."
fi

# 7. Start Infrastructure
log_info "Starting containers..."
UP_FLAGS="-d --build"
[ "$DEBUG" = true ] && UP_FLAGS="--build"

COMPOSE_PROFILES=""
if [ "$FINAL_PROVIDER" == "ollama" ]; then
    COMPOSE_PROFILES="--profile ollama"
fi

export CODEINTEL_TIER="$PERFORMANCE_TIER"
if ! $COMPOSE_CMD $COMPOSE_PROFILES --env-file "$ENV_FILE" up $UP_FLAGS; then
    log_error "Failed to start containers. Check disk space or logs."; exit 1
fi

[ "$DEBUG" = true ] && exit 0

# 8. Wait for API
echo ""
log_info "Waiting for services to initialize..."
MAX_RETRIES=60; COUNT=0
until timeout 10s $COMPOSE_CMD exec -i api python -c "import sqlalchemy; print('API Ready')" > /dev/null 2>&1 || [ $COUNT -eq $MAX_RETRIES ]; do
  if [[ "$COMPOSE_CMD" == "docker compose" ]]; then
      STATUSES=$(timeout 5s $COMPOSE_CMD ps --format "{{.Service}} [{{.Status}}]" 2>/dev/null | tr '\n' ', ' | sed 's/, $//')
      echo -ne "\r   [${COUNT}/${MAX_RETRIES}] Status: ${CYAN}${STATUSES}${NC}   "
  else
      echo -ne "\r   [${COUNT}/${MAX_RETRIES}] Waiting for API...   "
  fi
  sleep 5; COUNT=$((COUNT + 1))
done
echo ""

if [ $COUNT -eq $MAX_RETRIES ]; then
    log_error "API service failed to start."
    log_info "Last 20 lines of API logs:"
    $COMPOSE_CMD logs api | tail -n 20
    exit 1
fi

$COMPOSE_CMD exec -i api alembic upgrade head
./scripts/setup-agent.sh

# 9. Model Pull
if [ "$FINAL_PROVIDER" == "ollama" ] && [ "$SKIP_MODELS" = false ]; then
    MODEL=$(grep "^LLM_MODEL=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "phi3:mini")
    log_info "Pulling Ollama model ($MODEL)..."
    $COMPOSE_CMD exec -i ollama ollama pull "$MODEL"
fi

echo ""
echo -e "${GREEN}┌───────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│      🎉 Code-Intel is ready for use!      │${NC}"
echo -e "${GREEN}└───────────────────────────────────────────┘${NC}"
echo ""
echo -e "${BLUE}Dashboard & Access:${NC}"
echo -e "  • REST API:  ${CYAN}http://localhost:8000${NC}"
echo -e "  • Web UI:    ${CYAN}http://localhost:5173${NC}"
echo -e "  • MCP Hub:   Configured for ${GREEN}Claude Desktop${NC} & ${GREEN}Cursor${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  • Tier:      ${GREEN}$PERFORMANCE_TIER${NC}"
echo -e "  • LLM:       ${GREEN}$FINAL_PROVIDER${NC}"
echo ""
echo -e "${CYAN}Welcome Wizard: What would you like to do next?${NC}"
echo "----------------------------------------------"
echo "1) Run the Strategic Demo (Uses built-in Python example)"
echo "2) Analyze your own Git Repository (GitHub/GitLab URL)"
echo "3) Exit and explore later"
echo ""

if [ -t 0 ]; then read -p "Selection (1/2/3): " -n 1 -r NEXT_STEP; echo ""; else read -r NEXT_STEP; fi

case "$NEXT_STEP" in
    1) ./demo.sh ;;
    2)
        echo ""
        read -p "Enter Git Repository URL: " REPO_URL
        read -p "Enter Branch (default: main): " REPO_BRANCH
        REPO_BRANCH=${REPO_BRANCH:-main}
        read -p "Enter Version Name (default: custom-v1): " REPO_VERSION
        REPO_VERSION=${REPO_VERSION:-custom-v1}
        echo -e "\n📥 ${CYAN}Starting analysis...${NC}"
        $COMPOSE_CMD exec -i api code-intel analyze "$REPO_URL" --version "$REPO_VERSION" --branch "$REPO_BRANCH"
        log_success "Analysis complete! You can now query this repository."
        ;;
    *) log_info "Happy Hacking! Access the UI at http://localhost:5173" ;;
esac
