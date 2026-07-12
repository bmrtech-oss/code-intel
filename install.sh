#!/bin/bash
set -e

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

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
    echo "  -v, --venv <name>     Specify the Python virtual environment name (default: .venv)"
    echo "  -s, --skip-models     Skip pulling Ollama models"
    echo "  -e, --env-file <path> Path to environment file (default: .env)"
    echo "  -d, --debug           Enable debug mode (don't detach containers, show full logs)"
    echo "  -p, --purge           Run cleanup (purge.sh) before starting installation"
    echo "  --skip-venv           Skip creating local virtual environment (saves host space)"
    echo "  --tier <minimal|standard|high> Set performance tier (default: minimal)"
    echo "  -h, --help            Show this help message"
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

# 1. Mandatory LLM Configuration Prompt
CURRENT_PROVIDER=$(grep LLM_PROVIDER "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
if [ -z "$CURRENT_PROVIDER" ] || [ "$CURRENT_PROVIDER" == "ollama" ]; then
    echo ""
    echo -e "${CYAN}🤖 LLM Configuration (Mandatory)${NC}"
    echo "----------------------------"
    echo "1) Google Gemini (Remote) [DEFAULT - FASTEST]"
    echo "2) OpenRouter (Remote)"
    echo "3) Ollama (Local - ⚠️ Requires ~5GB extra disk space)"

    if [ -t 0 ]; then read -p "Selection (1/2/3): " -n 1 -r LLM_CHOICE; echo ""; else read -r LLM_CHOICE; fi

    case "$LLM_CHOICE" in
        2)
            read -p "Enter OpenRouter API Key: " INPUT_KEY
            DEFAULT_MODEL="google/gemini-flash-1.5"
            read -p "Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
            INPUT_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}
            sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=openrouter|" "$ENV_FILE"
            sed -i "s|LLM_MODEL=.*|LLM_MODEL=$INPUT_MODEL|" "$ENV_FILE"
            if grep -q "LLM_API_KEY=" "$ENV_FILE"; then sed -i "s|.*LLM_API_KEY=.*|LLM_API_KEY=$INPUT_KEY|" "$ENV_FILE"
            else echo "LLM_API_KEY=$INPUT_KEY" >> "$ENV_FILE"; fi
            SKIP_MODELS=true
            ;;
        3)
            sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" "$ENV_FILE"
            sed -i "s|LLM_MODEL=.*|LLM_MODEL=phi3:mini|" "$ENV_FILE"
            ;;
        *)
            read -p "Enter Google Gemini API Key: " INPUT_KEY
            if [ -n "$INPUT_KEY" ]; then
                DEFAULT_MODEL="gemini-1.5-flash"
                read -p "Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
                INPUT_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}
                sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=google|" "$ENV_FILE"
                sed -i "s|LLM_MODEL=.*|LLM_MODEL=$INPUT_MODEL|" "$ENV_FILE"
                if grep -q "GOOGLE_API_KEY=" "$ENV_FILE"; then sed -i "s|.*GOOGLE_API_KEY=.*|GOOGLE_API_KEY=$INPUT_KEY|" "$ENV_FILE"
                else echo "GOOGLE_API_KEY=$INPUT_KEY" >> "$ENV_FILE"; fi
                SKIP_MODELS=true
                log_success "Configured for Google Gemini ($INPUT_MODEL)."
            else
                log_warn "No key provided. Falling back to local Ollama."
                sed -i "s|LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" "$ENV_FILE"
            fi
            ;;
    esac
fi

# 2. Performance Tier Selection
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

log_success "Selected Tier: $PERFORMANCE_TIER"

# Summary
echo ""
echo -e "${CYAN}📋 Configuration Summary${NC}"
echo "----------------------"
log_info "Environment: $VENV_NAME (Skip: $SKIP_VENV)"
log_info "Tier:        $PERFORMANCE_TIER"
log_info "Provider:    $(grep LLM_PROVIDER "$ENV_FILE" | cut -d'=' -f2)"
echo ""

# 3. Check prerequisites
log_info "Checking prerequisites..."
if command -v podman-compose >/dev/null 2>&1; then COMPOSE_CMD="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then COMPOSE_CMD="docker compose"
else log_error "docker-compose or podman-compose is required."; exit 1; fi

# Verify engine
if ! timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
    log_warn "Container engine is not responding. Attempting restart..."
    sudo systemctl restart podman.socket podman.service 2>/dev/null || true
    sleep 5
fi

# 4. Setup Python environment
if [ "$SKIP_VENV" = false ]; then
    log_info "Syncing host environment (this may take a few minutes)..."
    export UV_PROJECT_ENVIRONMENT="$VENV_NAME"
    case "$PERFORMANCE_TIER" in
        "minimal")  uv sync --extra agents --no-cache ;;
        "standard") uv sync --extra agents --extra semantic --no-cache ;;
        "high")     uv sync --extra agents --extra semantic --no-cache ;;
    esac
fi

# 5. Start Infrastructure
log_info "Starting containers..."
UP_FLAGS="-d --build"
[ "$DEBUG" = true ] && UP_FLAGS="--build"

export CODEINTEL_TIER="$PERFORMANCE_TIER"
if ! $COMPOSE_CMD --env-file "$ENV_FILE" up $UP_FLAGS; then
    log_error "Failed to start containers. Check disk space or logs."; exit 1
fi

[ "$DEBUG" = true ] && exit 0

# 6. Wait for API
echo ""
log_info "Waiting for services to initialize..."
MAX_RETRIES=60; COUNT=0
until timeout 10s $COMPOSE_CMD exec -i api python -c "import sqlalchemy; print('API Ready')" > /dev/null 2>&1 || [ $COUNT -eq $MAX_RETRIES ]; do
  # Detailed status dashboard
  if [[ "$COMPOSE_CMD" == "docker compose" ]]; then
      STATUSES=$(timeout 5s $COMPOSE_CMD ps --format "{{.Service}} [{{.Status}}]" 2>/dev/null | tr '\n' ', ' | sed 's/, $//')
      echo -ne "\r   [${COUNT}/${MAX_RETRIES}] Current Status: ${CYAN}${STATUSES}${NC}   "
  else
      echo -ne "\r   [${COUNT}/${MAX_RETRIES}] Waiting for API service...   "
  fi
  sleep 5; COUNT=$((COUNT + 1))
done
echo ""

if [ $COUNT -eq $MAX_RETRIES ]; then
    log_error "API service failed to start in time."; exit 1
fi

log_info "Running database migrations..."
$COMPOSE_CMD exec -i api alembic upgrade head
./scripts/setup-agent.sh

# 7. Model Pull
FINAL_PROVIDER=$(grep LLM_PROVIDER "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "ollama")
if [ "$FINAL_PROVIDER" == "ollama" ] && [ "$SKIP_MODELS" = false ]; then
    MODEL=$(grep LLM_MODEL "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "phi3:mini")
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
echo -e "${BLUE}Quick Commands:${NC}"
echo -e "  • Strategic Demo:  ${YELLOW}./demo.sh${NC}"
echo -e "  • Analyze Code:    ${YELLOW}uv run code-intel analyze <PATH>${NC}"
echo -e "  • Cleanup / Reset: ${YELLOW}./purge.sh${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  • Tier:      ${GREEN}$PERFORMANCE_TIER${NC}"
echo -e "  • LLM:       ${GREEN}$(grep LLM_PROVIDER "$ENV_FILE" | cut -d'=' -f2)${NC} (${GREEN}$(grep LLM_MODEL "$ENV_FILE" | cut -d'=' -f2)${NC})"
echo ""

read -p "❓ Would you like to run the Strategic Demo now? (y/N): " -n 1 -r RUN_DEMO
echo ""
if [[ $RUN_DEMO =~ ^[Yy]$ ]]; then
    ./demo.sh
fi
