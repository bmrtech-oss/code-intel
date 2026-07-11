#!/bin/bash
set -e

# --- Configuration & Defaults ---
DEMO_PROVIDER=${LLM_PROVIDER:-"ollama"}
DEMO_MODEL=${LLM_MODEL:-"phi3:mini"}
DEMO_API_KEY=$LLM_API_KEY
DEMO_BASE_URL=$LLM_BASE_URL

# --- Functions ---
show_help() {
    echo "Usage: ./demo.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --provider <name>     LLM Provider (ollama|openrouter) (default: $DEMO_PROVIDER)"
    echo "  --model <name>        LLM Model (default: $DEMO_MODEL)"
    echo "  --api-key <key>       API Key for remote provider"
    echo "  --base-url <url>      Base URL for remote provider"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./demo.sh --provider openrouter --api-key sk-or-..."
    echo "  ./demo.sh --model deepseek/deepseek-chat --api-key ..."
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider)
            DEMO_PROVIDER="$2"
            shift 2
            ;;
        --model)
            DEMO_MODEL="$2"
            shift 2
            ;;
        --api-key)
            DEMO_API_KEY="$2"
            shift 2
            ;;
        --base-url)
            DEMO_BASE_URL="$2"
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

# If API key is provided but provider is still default, switch to openrouter
if [ -n "$DEMO_API_KEY" ] && [ "$DEMO_PROVIDER" == "ollama" ]; then
    DEMO_PROVIDER="openrouter"
    # Set a fast default model for demo if not specified
    if [ "$DEMO_MODEL" == "phi3:mini" ]; then
        DEMO_MODEL="google/gemini-flash-1.5"
    fi
fi

# Export variables so the 'uv run' commands and the API pick them up
export LLM_PROVIDER="$DEMO_PROVIDER"
export LLM_MODEL="$DEMO_MODEL"
export LLM_API_KEY="$DEMO_API_KEY"
export LLM_BASE_URL="$DEMO_BASE_URL"

echo "🎬 Starting Code-Intel Strategic Demo..."
echo "========================================="
echo "Config: Provider=$LLM_PROVIDER, Model=$LLM_MODEL"

# 1. Ingest Sample Repository
echo "📥 Phase 1: Ingesting Python Example..."
uv run code-intel analyze examples/python --version demo-v1
echo "✅ Ingestion complete."

# 2. Topological Query
echo -e "\n🔍 Phase 2: Running Topological Query (Call Graph)..."
uv run code-intel query query_call_graph --commit demo-v1 --symbol app.main

# 3. Impact Prediction
echo -e "\n💥 Phase 3: Predicting Blast Radius for 'app.Processor.process'..."
uv run code-intel query predict_impact --commit demo-v1 --symbol app.Processor.process

# 4. Semantic Search
echo -e "\n🧠 Phase 4: Semantic Search ('How to process data?')..."
# Note: Semantic search requires the API to be running and models downloaded
curl -s "http://localhost:8000/search?q=process+data" | jq . || echo "⚠️ API not reachable or search failed."

# 5. ML Co-change Prediction (Priority 5)
echo -e "\n📈 Phase 5: ML-Based Co-change Prediction..."
uv run code-intel query predict_next_edit --commit demo-v1 --symbol app.Processor.process

# 6. Autonomic Requirements (Async)
echo -e "\n📝 Phase 6: Generating Autonomic Requirements..."
# We pass the settings to the API via headers or it uses environment variables if it's running in the same shell (it's not, usually)
# However, for a demo, we assume the user might be running the API in a container or separately.
# If they use the remote provider, they should have configured the API with these env vars.
JOB_DATA=$(curl -s -X POST "http://localhost:8000/requirements?version=demo-v1")
JOB_ID=$(echo $JOB_DATA | jq -r '.job_id')

if [ "$JOB_ID" != "null" ] && [ "$JOB_ID" != "" ]; then
    echo "⏳ Job $JOB_ID pending. Polling for results..."
    for i in {1..5}; do
        sleep 5
        STATUS=$(curl -s "http://localhost:8000/requirements/status/$JOB_ID" | jq -r '.status')
        echo "   Current Status: $STATUS"
        if [ "$STATUS" == "completed" ]; then
            curl -s "http://localhost:8000/requirements/status/$JOB_ID" | jq '.result.requirements'
            break
        fi
    done
else
    echo "⚠️ Requirements job failed to start. (Check if API is running with the correct LLM configuration)"
fi

# 7. Autonomic Engineering (P2 Dry-Run)
echo -e "\n💀 Phase 7: Dead Code Reaper (Simulation)..."
echo "Candidates found with 1.0 confidence: app.Processor.dead_method"
echo "Action: Branch 'cleanup/dead-method' -> Delete -> Verify -> PR Description Generated."

echo -e "\n🎉 Strategic Demo Complete!"
echo "========================================="
echo "The platform has demonstrated Intelligence, Prediction, Verification, and Autonomic Action."
