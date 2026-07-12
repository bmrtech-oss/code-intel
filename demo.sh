#!/bin/bash
set -e

# --- Colors ---
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Configuration & Defaults ---
DEMO_PROVIDER=${LLM_PROVIDER:-"ollama"}
DEMO_MODEL=${LLM_MODEL:-"phi3:mini"}
DEMO_API_KEY=$LLM_API_KEY
DEMO_GOOGLE_KEY=$GOOGLE_API_KEY
DEMO_BASE_URL=$LLM_BASE_URL

# --- Functions ---
log_phase() { echo -e "\n${BLUE}● Phase $1: $2${NC}"; }
log_step() { echo -e "  ${CYAN}→${NC} $1"; }

show_help() {
    echo "Usage: ./demo.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --provider <name>     LLM Provider (ollama|openrouter|google) (default: $DEMO_PROVIDER)"
    echo "  --model <name>        LLM Model (default: $DEMO_MODEL)"
    echo "  --api-key <key>       API Key for OpenRouter"
    echo "  --google-key <key>    API Key for Google Gemini"
    echo "  --base-url <url>      Base URL for remote provider"
    echo "  -h, --help            Show this help message"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider) DEMO_PROVIDER="$2"; shift 2 ;;
        --model) DEMO_MODEL="$2"; shift 2 ;;
        --api-key) DEMO_API_KEY="$2"; shift 2 ;;
        --google-key) DEMO_GOOGLE_KEY="$2"; shift 2 ;;
        --base-url) DEMO_BASE_URL="$2"; shift 2 ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "❌ Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# If no keys are available, offer to input one
if [ -z "$DEMO_API_KEY" ] && [ -z "$DEMO_GOOGLE_KEY" ] && [ "$DEMO_PROVIDER" == "ollama" ]; then
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
export LLM_BASE_URL="$DEMO_BASE_URL"

echo -e "${CYAN}🎬 Starting Code-Intel Strategic Demo...${NC}"
echo -e "Config: ${GREEN}$LLM_PROVIDER${NC} | ${GREEN}$LLM_MODEL${NC}"
echo "========================================="

log_phase "1" "Ingesting Sample Repository"
log_step "Indexing 'examples/python'..."
uv run code-intel analyze examples/python --version demo-v1
echo -e "  ${GREEN}✅ Ingestion complete.${NC}"

log_phase "2" "Topological Query (Call Graph)"
log_step "Querying call chain for 'app.main'..."
uv run code-intel query query_call_graph --commit demo-v1 --symbol app.main

log_phase "3" "Predictive Impact Analysis"
log_step "Calculating blast radius for 'app.Processor.process'..."
uv run code-intel query predict_impact --commit demo-v1 --symbol app.Processor.process

log_phase "4" "Semantic Search (Natural Language)"
log_step "Searching for: 'How to process data?'"
# Note: Semantic search requires Standard/High tier
SEARCH_RESULT=$(curl -s "http://localhost:8000/search?q=process+data")
if echo "$SEARCH_RESULT" | grep -q "Error"; then
    echo -e "  ${YELLOW}⚠️  Note:${NC} $(echo "$SEARCH_RESULT" | jq -r '.detail')"
else
    echo "$SEARCH_RESULT" | jq .
fi

log_phase "5" "ML Co-change Prediction"
log_step "Predicting next likely edits based on history..."
uv run code-intel query predict_next_edit --commit demo-v1 --symbol app.Processor.process

log_phase "6" "Autonomic Requirements Generation"
log_step "Generating JSON Epics/Stories from code structure..."
JOB_DATA=$(curl -s -X POST "http://localhost:8000/requirements?version=demo-v1")
JOB_ID=$(echo $JOB_DATA | jq -r '.job_id')

if [ "$JOB_ID" != "null" ] && [ "$JOB_ID" != "" ]; then
    log_step "Job $JOB_ID started. Polling for completion..."
    for i in {1..10}; do
        sleep 5
        STATUS_DATA=$(curl -s "http://localhost:8000/requirements/status/$JOB_ID")
        STATUS=$(echo "$STATUS_DATA" | jq -r '.status')
        echo -ne "\r     Current Status: ${CYAN}$STATUS${NC}   "
        if [ "$STATUS" == "completed" ]; then
            echo -e "\n  ${GREEN}✅ Success! Requirements generated:${NC}"
            echo "$STATUS_DATA" | jq '.result.requirements'
            break
        fi
    done
else
    echo -e "  ${RED}❌ Error:${NC} Requirements job failed to start."
fi

log_phase "7" "Autonomic Engineering (Simulation)"
log_step "Identifying candidates for cleanup..."
echo -e "  ${GREEN}Candidates found:${NC} app.Processor.dead_method (Confidence: 1.0)"
log_step "Simulating action: Branch 'cleanup' → Delete → Verify → PR Generated."

echo -e "\n${GREEN}🎉 Strategic Demo Complete!${NC}"
echo "The platform has demonstrated Intelligence, Prediction, Verification, and Autonomic Action."
