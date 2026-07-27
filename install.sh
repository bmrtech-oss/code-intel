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
TIER_PROVIDED=false
DB_BACKEND=""
GRAPH_ENGINE_VAL=""

# --- Functions ---
log_info() { echo -e "${BLUE}info:${NC} $1"; }
log_success() { echo -e "${GREEN}success:${NC} $1"; }
log_warn() { echo -e "${YELLOW}warning:${NC} $1"; }
log_error() { echo -e "${RED}error:${NC} $1"; }

update_env_var() {
    local key=$1
    local val=$2
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

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
    echo "  --db <backend>        Set database backend (postgres|sqlite)"
    echo "  --graph-engine <eng>  Set graph engine (production|local)"
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
        # Check if netstat supports -tuln (Linux netstat)
        if netstat -tuln >/dev/null 2>&1; then
            if netstat -tuln | grep -q ":$port " ; then
                log_error "Port $port ($name) is already in use."
                return 1
            fi
        # Fallback for Windows netstat (Git Bash / MSYS)
        elif netstat -ano >/dev/null 2>&1; then
            if netstat -ano | grep -q "LISTENING" | grep -q ":$port " ; then
                log_error "Port $port ($name) is already in use."
                return 1
            fi
        fi
    fi
    return 0
}

service_container_running() {
    local name=$1
    if command -v podman >/dev/null 2>&1; then
        podman ps --format '{{.Names}}' 2>/dev/null | grep -Fxq "$name" && return 0
    fi
    if command -v docker >/dev/null 2>&1; then
        docker ps --format '{{.Names}}' 2>/dev/null | grep -Fxq "$name" && return 0
    fi
    return 1
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
        --tier) PERFORMANCE_TIER="$2"; TIER_PROVIDED=true; shift 2 ;;
        --db) DB_BACKEND="$2"; shift 2 ;;
        --graph-engine) GRAPH_ENGINE_VAL="$2"; shift 2 ;;
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
# Ensure ALL subdirectories in code_intel have __init__.py for proper module resolution in containers
find code_intel -type d -not -path '*/.*' -not -path '*/__pycache__*' | while read d; do
  touch "$d/__init__.py"
done

# Validate package and imports using verify_pkg.py
if command -v python3 >/dev/null 2>&1; then
    python3 scripts/verify_pkg.py || log_warn "Package verification returned non-zero, continuing..."
elif command -v python >/dev/null 2>&1; then
    python scripts/verify_pkg.py || log_warn "Package verification returned non-zero, continuing..."
fi

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

                update_env_var "LLM_PROVIDER" "openrouter"
                update_env_var "LLM_MODEL" "$INPUT_MODEL"
                update_env_var "LLM_API_KEY" "$INPUT_KEY"
                SKIP_MODELS=true
            fi
            ;;
        3)
            update_env_var "LLM_PROVIDER" "ollama"
            update_env_var "LLM_MODEL" "phi3:mini"
            ;;
        *) # Default: Google Gemini
            read -p "Enter Google Gemini API Key: " INPUT_KEY
            if [ -n "$INPUT_KEY" ]; then
                DEFAULT_MODEL="gemini-1.5-flash"
                read -p "Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
                INPUT_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}

                update_env_var "LLM_PROVIDER" "google"
                update_env_var "LLM_MODEL" "$INPUT_MODEL"
                update_env_var "GOOGLE_API_KEY" "$INPUT_KEY"
                SKIP_MODELS=true
                log_success "Configured for Google Gemini ($INPUT_MODEL)."
            else
                echo "⚠️ No key provided. Falling back to Ollama local defaults."
                update_env_var "LLM_PROVIDER" "ollama"
            fi
            ;;
    esac
fi

# 2.1 Pluggable Database & Graph Engine Configuration
CURRENT_DB_URL=$(grep "^DATABASE_URL=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
CURRENT_GRAPH_ENGINE=$(grep "^GRAPH_ENGINE=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")

DB_CHOICE=""
GRAPH_CHOICE=""

if [ -n "$DB_BACKEND" ]; then
    case "$DB_BACKEND" in
        sqlite) DB_CHOICE="2" ;;
        postgres) DB_CHOICE="1" ;;
        *) log_error "Invalid database backend '$DB_BACKEND'. Expected one of: postgres, sqlite"; exit 1 ;;
    esac
fi

if [ -n "$GRAPH_ENGINE_VAL" ]; then
    case "$GRAPH_ENGINE_VAL" in
        local) GRAPH_CHOICE="2" ;;
        production) GRAPH_CHOICE="1" ;;
        *) log_error "Invalid graph engine '$GRAPH_ENGINE_VAL'. Expected one of: production, local"; exit 1 ;;
    esac
fi

# Fallback to current config if not supplied via command line
if [ -z "$DB_CHOICE" ] && [ -n "$CURRENT_DB_URL" ]; then
    if [[ "$CURRENT_DB_URL" == *"sqlite"* ]]; then
        DB_CHOICE="2"
    elif [[ "$CURRENT_DB_URL" == *"postgres"* ]]; then
        DB_CHOICE="1"
    fi
fi

if [ -z "$GRAPH_CHOICE" ] && [ -n "$CURRENT_GRAPH_ENGINE" ]; then
    if [[ "$CURRENT_GRAPH_ENGINE" == "local" ]]; then
        GRAPH_CHOICE="2"
    elif [[ "$CURRENT_GRAPH_ENGINE" == "production" ]]; then
        GRAPH_CHOICE="1"
    fi
fi

# Prompt if not determined and running interactively
if [ -z "$DB_CHOICE" ]; then
    if [ -t 0 ] && [ -z "${CI:-}" ]; then
        echo ""
        echo -e "${CYAN}💾 Database Backend Configuration${NC}"
        echo "----------------------------"
        echo "Choose the database backend for Code-Intel:"
        echo "1) PostgreSQL (Remote/Containerized - Recommended for Production) [DEFAULT]"
        echo "2) SQLite (Local File-Backed - Lightweight, Zero-Config Fallback)"
        read -p "Selection (1/2): " -n 1 -r TMP_CHOICE
        echo ""
        DB_CHOICE="${TMP_CHOICE:-1}"
    else
        DB_CHOICE="1"
    fi
fi

case "$DB_CHOICE" in
    2)
        update_env_var "DATABASE_URL" "sqlite+aiosqlite:///data/codeintel.db"
        update_env_var "DATABASE_URL_CONTAINER" "sqlite+aiosqlite:///data/codeintel.db"
        log_success "Configured SQLite as the database backend."
        ;;
    *)
        update_env_var "DATABASE_URL" "postgresql+asyncpg://postgres:password@localhost:5432/codeintel"
        update_env_var "DATABASE_URL_CONTAINER" "postgresql+asyncpg://postgres:password@postgres:5432/codeintel"
        log_success "Configured PostgreSQL as the database backend."
        ;;
esac

if [ -z "$GRAPH_CHOICE" ]; then
    if [ -t 0 ] && [ -z "${CI:-}" ]; then
        echo ""
        echo -e "${CYAN}🔌 Graph Engine Configuration${NC}"
        echo "----------------------------"
        echo "Choose the graph execution engine:"
        echo "1) Production (SQL Recursive CTEs - High-Performance SQL) [DEFAULT]"
        echo "2) Local (Embedded SQLite + GraphQLite - Leverages Cypher & Graph Algos)"
        read -p "Selection (1/2): " -n 1 -r TMP_CHOICE
        echo ""
        GRAPH_CHOICE="${TMP_CHOICE:-1}"
    else
        GRAPH_CHOICE="1"
    fi
fi

case "$GRAPH_CHOICE" in
    2)
        update_env_var "GRAPH_ENGINE" "local"
        update_env_var "GRAPHQLITE_DB_PATH" "data/code_intel_graph.db"
        log_success "Configured Local Graph Engine (SQLite + GraphQLite)."
        ;;
    *)
        update_env_var "GRAPH_ENGINE" "production"
        log_success "Configured Production Graph Engine (SQL CTEs)."
        ;;
esac

# 3. Performance Tier Selection
case "$PERFORMANCE_TIER" in
    standard|high|minimal)
        ;;
    *)
        log_error "Invalid tier '$PERFORMANCE_TIER'. Expected one of: minimal, standard, high"
        exit 1
        ;;
esac

if [ "$TIER_PROVIDED" = false ] && [ -z "${CI:-}" ] && [ -t 0 ]; then
    echo ""
    echo -e "${CYAN}⚡ Performance & Feature Tier${NC}"
    echo "--------------------------"
    echo "1) Minimal  (~600MB image) - Graph only. No Semantic Search."
    echo "2) Standard (~2.5GB image) - Semantic Search enabled (CPU optimized)."
    echo "3) High     (~7GB image)   - Semantic Search enabled (Nvidia CUDA accelerated)."
    read -p "Selection (1/2/3): " -n 1 -r TIER_CHOICE
    echo ""

    case "$TIER_CHOICE" in
        2) PERFORMANCE_TIER="standard" ;;
        3) PERFORMANCE_TIER="high" ;;
        *) PERFORMANCE_TIER="minimal" ;;
    esac
else
    echo "Using requested performance tier: $PERFORMANCE_TIER"
fi

# 4. Port Conflict Check
log_info "Checking for port conflicts..."
CONFLICT=false
API_RUNNING=false
POSTGRES_RUNNING=false
REDIS_RUNNING=false

if service_container_running codeintel-api; then
    API_RUNNING=true
    log_info "API container is already running; skipping API port check."
else
    check_port 8000 "API" || CONFLICT=true
fi

if service_container_running codeintel-postgres; then
    POSTGRES_RUNNING=true
    log_info "Postgres container is already running; skipping Postgres port check."
else
    check_port 5432 "Postgres" || CONFLICT=true
fi

if service_container_running codeintel-redis; then
    REDIS_RUNNING=true
    log_info "Redis container is already running; skipping Redis port check."
else
    check_port 6379 "Redis" || CONFLICT=true
fi

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

# Verify engine with safe timeout check (handles Windows/Git Bash compat)
engine_responsive=false
if command -v timeout >/dev/null 2>&1 && timeout --version >/dev/null 2>&1; then
    if timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
        engine_responsive=true
    fi
else
    # Fallback to direct invocation if GNU timeout is not available
    if $COMPOSE_CMD ps >/dev/null 2>&1; then
        engine_responsive=true
    fi
fi

if [ "$engine_responsive" = false ]; then
    log_warn "Container engine is not responding. Attempting restart..."
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl restart podman.socket podman.service 2>/dev/null || true
    fi
    sleep 5

    engine_responsive_second=false
    if command -v timeout >/dev/null 2>&1 && timeout --version >/dev/null 2>&1; then
        if timeout 15s $COMPOSE_CMD ps >/dev/null 2>&1; then
            engine_responsive_second=true
        fi
    else
        if $COMPOSE_CMD ps >/dev/null 2>&1; then
            engine_responsive_second=true
        fi
    fi

    if [ "$engine_responsive_second" = false ]; then
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
if [ "$API_RUNNING" = true ] && [ "$POSTGRES_RUNNING" = true ]; then
    log_info "Existing Code-Intel containers detected; reusing the running stack."
else
    log_info "Starting core services..."
    export CODEINTEL_TIER="$PERFORMANCE_TIER"

    COMPOSE_PROFILES=""
    if [ "$FINAL_PROVIDER" == "ollama" ]; then
        COMPOSE_PROFILES="--profile ollama"
    fi

    if ! $COMPOSE_CMD $COMPOSE_PROFILES --env-file "$ENV_FILE" up -d --build postgres redis; then
        log_error "Failed to start Postgres/Redis. Check disk space or logs."; exit 1
    fi

    if [ "$DB_CHOICE" = "1" ]; then
        log_info "Waiting for Postgres to become ready..."
        COUNT=0
        while [ $COUNT -lt 60 ]; do
            if $COMPOSE_CMD exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
                break
            fi
            # Fallback local TCP socket port check to prevent hangs on Windows/Git Bash
            if command -v python3 >/dev/null 2>&1 && python3 -c "import socket; s = socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', 5432))" >/dev/null 2>&1; then
                break
            elif command -v python >/dev/null 2>&1 && python -c "import socket; s = socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', 5432))" >/dev/null 2>&1; then
                break
            fi
            sleep 5; COUNT=$((COUNT + 1))
        done

        if [ $COUNT -eq 60 ]; then
            log_error "Postgres did not become ready in time."
            $COMPOSE_CMD logs postgres | tail -n 20
            exit 1
        fi
    else
        log_info "SQLite database backend selected; skipping Postgres readiness wait loop."
    fi

    log_info "Waiting for Redis to become ready..."
    COUNT=0
    while [ $COUNT -lt 60 ]; do
        if $COMPOSE_CMD exec -T redis redis-cli ping >/dev/null 2>&1; then
            break
        fi
        # Fallback local TCP socket port check to prevent hangs on Windows/Git Bash
        if command -v python3 >/dev/null 2>&1 && python3 -c "import socket; s = socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', 6379))" >/dev/null 2>&1; then
            break
        elif command -v python >/dev/null 2>&1 && python -c "import socket; s = socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', 6379))" >/dev/null 2>&1; then
            break
        fi
        sleep 5; COUNT=$((COUNT + 1))
    done

    if [ $COUNT -eq 60 ]; then
        log_error "Redis did not become ready in time."
        $COMPOSE_CMD logs redis | tail -n 20
        exit 1
    fi

    if ! $COMPOSE_CMD $COMPOSE_PROFILES --env-file "$ENV_FILE" up -d --build api worker; then
        log_error "Failed to start API/worker. Check disk space or logs."; exit 1
    fi

    for container in codeintel-api codeintel-worker; do
        if podman ps -a --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -Fxq "$container created"; then
            log_info "Starting $container from Created state..."
            podman start "$container" >/dev/null 2>&1 || true
        fi
    done

    if podman ps --filter name=codeintel-worker --format '{{.Status}}' 2>/dev/null | grep -q '^Up'; then
        log_success "Worker container is running."
    fi

    if [ "$FINAL_PROVIDER" == "ollama" ]; then
        if ! $COMPOSE_CMD $COMPOSE_PROFILES --env-file "$ENV_FILE" up -d --build ollama; then
            log_error "Failed to start Ollama. Check disk space or logs."; exit 1
        fi
    fi
fi

[ "$DEBUG" = true ] && exit 0

# 8. Wait for API
echo ""
log_info "Waiting for services to initialize..."
MAX_RETRIES=30; COUNT=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    if $COMPOSE_CMD exec api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/docs', timeout=2).read(); print('API Ready')" > /dev/null 2>&1; then
        break
    fi

    echo -ne "\r   [${COUNT}/${MAX_RETRIES}] Waiting for API to respond on port 8000...   "
    sleep 5; COUNT=$((COUNT + 1))
done
echo ""

if ! $COMPOSE_CMD exec api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/docs', timeout=2).read(); print('API Ready')" > /dev/null 2>&1; then
    log_error "API did not become ready in time."
    log_info "Container status:"
    $COMPOSE_CMD ps || true
    log_info "Last 20 lines of API logs:"
    $COMPOSE_CMD logs api | tail -n 20 || true
    exit 1
fi

log_success "API is responding on port 8000."

$COMPOSE_CMD exec api alembic upgrade head || true
./scripts/setup-agent.sh || true

# 9. Model Pull
if [ "$FINAL_PROVIDER" == "ollama" ] && [ "$SKIP_MODELS" = false ]; then
    MODEL=$(grep "^LLM_MODEL=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "phi3:mini")
    log_info "Pulling Ollama model ($MODEL)..."
    $COMPOSE_CMD exec ollama ollama pull "$MODEL"
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

if [ -t 0 ]; then
    read -p "Selection (1/2/3): " -n 1 -r NEXT_STEP
    echo ""
else
    NEXT_STEP=1
fi

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
