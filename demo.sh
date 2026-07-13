#!/bin/bash
set -e

# --- Colors ---
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# --- Configuration & Defaults ---
DEFAULT_PROVIDER="openrouter"
DEFAULT_MODEL="openai/gpt-oss-120b:free"
DEFAULT_REPO_URL="https://github.com/neubig/starter-repo"
DEFAULTS_MODE=false

if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

DEMO_PROVIDER="${DEMO_PROVIDER:-${LLM_PROVIDER:-$DEFAULT_PROVIDER}}"
DEMO_MODEL="${DEMO_MODEL:-${LLM_MODEL:-$DEFAULT_MODEL}}"
DEMO_API_KEY="${DEMO_API_KEY:-${LLM_API_KEY:-}}"
DEMO_GOOGLE_KEY="${DEMO_GOOGLE_KEY:-${GOOGLE_API_KEY:-}}"
DEMO_BASE_URL="${DEMO_BASE_URL:-${LLM_BASE_URL:-}}"
REPO_SOURCE="${REPO_SOURCE:-$DEFAULT_REPO_URL}"
DEMO_VERSION="demo-v1"

# --- Functions ---
log_phase() { echo -e "\n${BLUE}● Phase $1: $2${NC}"; }
log_step() { echo -e "  ${CYAN}→${NC} $1"; }

show_help() {
    echo "Usage: ./demo.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --provider <name>     LLM Provider (ollama|openrouter|google)"
    echo "  --model <name>        LLM Model"
    echo "  --api-key <key>       API Key for OpenRouter"
    echo "  --google-key <key>    API Key for Google Gemini"
    echo "  --repo-url <url>      Custom Git URL to analyze (default: https://github.com/neubig/starter-repo)"
    echo "  --version-name <name> Version name for analysis (default: demo-v1)"
    echo "  --defaults            Use default provider/model/repo settings and skip prompts"
    echo "  -h, --help            Show this help message"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider=*) DEMO_PROVIDER="${1#*=}"; shift ;;
        --provider) DEMO_PROVIDER="$2"; shift 2 ;;
        --model=*) DEMO_MODEL="${1#*=}"; shift ;;
        --model) DEMO_MODEL="$2"; shift 2 ;;
        --api-key=*) DEMO_API_KEY="${1#*=}"; shift ;;
        --api-key) DEMO_API_KEY="$2"; shift 2 ;;
        --google-key=*) DEMO_GOOGLE_KEY="${1#*=}"; shift ;;
        --google-key) DEMO_GOOGLE_KEY="$2"; shift 2 ;;
        --repo-url=*) REPO_SOURCE="${1#*=}"; shift ;;
        --repo-url) REPO_SOURCE="$2"; shift 2 ;;
        --version-name=*) DEMO_VERSION="${1#*=}"; shift ;;
        --version-name) DEMO_VERSION="$2"; shift 2 ;;
        --defaults|--no-interactive) DEFAULTS_MODE=true; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "❌ Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# If no keys are available, offer to input one unless defaults mode was requested.
if [ "$DEFAULTS_MODE" = false ] && [ -z "$DEMO_API_KEY" ] && [ -z "$DEMO_GOOGLE_KEY" ] && [ "$DEMO_PROVIDER" == "ollama" ]; then
    echo -e "${YELLOW}💡 Optimization Tip:${NC} Using a cloud LLM is much faster than local Ollama."
    echo "   Would you like to provide an API key to speed up Phase 6?"
    echo "   1) OpenRouter"
    echo "   2) Google Gemini"
    echo "   3) Skip (use local Ollama)"

    if [ -t 0 ]; then read -p "   Selection (1/2/3): " -n 1 -r LLM_CHOICE; echo ""; else read -r LLM_CHOICE; fi

    if [[ "$LLM_CHOICE" == "1" ]]; then
        read -p "   Enter OpenRouter API Key: " DEMO_API_KEY
        if [ -n "$DEMO_API_KEY" ]; then
            DEMO_PROVIDER="openrouter"
            DEFAULT_MODEL="google/gemini-flash-1.5"
            read -p "   Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
            DEMO_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}
        fi
    elif [[ "$LLM_CHOICE" == "2" ]]; then
        read -p "   Enter Google API Key: " DEMO_GOOGLE_KEY
        if [ -n "$DEMO_GOOGLE_KEY" ]; then
            DEMO_PROVIDER="google"
            DEFAULT_MODEL="gemini-1.5-flash"
            read -p "   Enter Model Name (default: $DEFAULT_MODEL): " INPUT_MODEL
            DEMO_MODEL=${INPUT_MODEL:-$DEFAULT_MODEL}
        fi
    fi
fi

export LLM_PROVIDER="$DEMO_PROVIDER"
export LLM_MODEL="$DEMO_MODEL"
export LLM_API_KEY="$DEMO_API_KEY"
export GOOGLE_API_KEY="$DEMO_GOOGLE_KEY"

if [ "$DEFAULTS_MODE" = true ]; then
    DEMO_PROVIDER="$DEFAULT_PROVIDER"
    DEMO_MODEL="$DEFAULT_MODEL"
    REPO_SOURCE="$DEFAULT_REPO_URL"
    DEMO_VERSION="demo-v1"
fi

export LLM_PROVIDER="$DEMO_PROVIDER"
export LLM_MODEL="$DEMO_MODEL"
export LLM_API_KEY="$DEMO_API_KEY"
export GOOGLE_API_KEY="$DEMO_GOOGLE_KEY"

echo -e "${CYAN}🎬 Starting Code-Intel Strategic Demo...${NC}"
echo -e "Config: ${GREEN}$LLM_PROVIDER${NC} | ${GREEN}$LLM_MODEL${NC}"
echo "========================================="

log_phase "1" "Ingesting Source Code"
log_step "Indexing '$REPO_SOURCE' as version '$DEMO_VERSION'..."
# Determine if we should use local uv run or container
if command -v code-intel >/dev/null 2>&1 || [ -d ".venv" ]; then
    uv run code-intel analyze "$REPO_SOURCE" --version "$DEMO_VERSION"
else
    # Fallback to using the container for analysis
    if command -v podman-compose >/dev/null 2>&1; then COMPOSE_CMD="podman-compose"; else COMPOSE_CMD="docker compose"; fi
    $COMPOSE_CMD exec -i api code-intel analyze "$REPO_SOURCE" --version "$DEMO_VERSION"
fi
echo -e "  ${GREEN}✅ Ingestion complete.${NC}"

log_phase "2" "Topological Query (Call Graph)"
log_step "Querying call relationships..."
# Try to find a representative symbol
if [[ "$REPO_SOURCE" == "examples/python" ]]; then
    SYM="app.main"
else
    SYM=$(curl -s "http://localhost:8000/query" -H "Content-Type: application/json" -d "{\"rule\": \"get_symbols\", \"commit_sha\": \"$DEMO_VERSION\"}" | jq -r '.result[0].fqn // "main"')
fi
log_step "Querying for symbol: $SYM"
curl -s -X POST "http://localhost:8000/query" -H "Content-Type: application/json" -d "{\"rule\": \"query_call_graph\", \"commit_sha\": \"$DEMO_VERSION\", \"symbol\": \"$SYM\"}" | jq .

log_phase "3" "Predictive Impact Analysis"
log_step "Calculating blast radius for: $SYM"
curl -s -X POST "http://localhost:8000/query" -H "Content-Type: application/json" -d "{\"rule\": \"predict_impact\", \"commit_sha\": \"$DEMO_VERSION\", \"symbol\": \"$SYM\"}" | jq .

log_phase "4" "Semantic Search (Natural Language)"
log_step "Searching for context..."
SEARCH_RESULT=$(curl -s "http://localhost:8000/search?q=core+logic")
if echo "$SEARCH_RESULT" | grep -q "Error"; then
    echo -e "  ${YELLOW}⚠️  Note:${NC} $(echo "$SEARCH_RESULT" | jq -r '.detail')"
else
    echo "$SEARCH_RESULT" | jq .
fi

log_phase "5" "ML Co-change Prediction"
log_step "Predicting next likely edits..."
curl -s -X POST "http://localhost:8000/query" -H "Content-Type: application/json" -d "{\"rule\": \"predict_next_edit\", \"commit_sha\": \"$DEMO_VERSION\", \"symbol\": \"$SYM\"}" | jq .

log_phase "6" "Autonomic Requirements Generation"
log_step "Generating JSON Epics/Stories..."
JOB_DATA=$(curl -s -X POST "http://localhost:8000/requirements?version=$DEMO_VERSION")
JOB_ID=$(echo $JOB_DATA | jq -r '.job_id')

if [ "$JOB_ID" != "null" ] && [ "$JOB_ID" != "" ]; then
    log_step "Job $JOB_ID started. Polling..."
    for i in {1..10}; do
        sleep 5
        STATUS_DATA=$(curl -s "http://localhost:8000/requirements/status/$JOB_ID")
        STATUS=$(echo "$STATUS_DATA" | jq -r '.status')
        echo -ne "\r     Current Status: ${CYAN}$STATUS${NC}   "
        if [ "$STATUS" == "completed" ]; then
            echo -e "\n  ${GREEN}✅ Success! Requirements generated.${NC}"
            echo "$STATUS_DATA" | jq '.result.requirements'
            break
        fi
    done
else
    echo -e "  ${RED}❌ Error:${NC} Requirements job failed to start."
fi

log_phase "7" "Autonomic Engineering (Simulation)"
log_step "Identifying candidates for cleanup..."
echo -e "  ${GREEN}Candidates found:${NC} dead_code, verified impact results."
log_step "Demo simulation finished."

echo -e "\n${GREEN}🎉 Strategic Demo Complete!${NC}"
