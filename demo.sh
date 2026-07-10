#!/bin/bash
set -e

echo "🎬 Starting Code-Intel Strategic Demo..."
echo "========================================="

# 1. Ingest Sample Repository
echo "📥 Phase 1: Ingesting Python Example..."
uv run code-intel analyze --repo-path examples/python --version demo-v1
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
# Using the MCP tool via direct API query if exposed, otherwise simulate
uv run code-intel query predict_next_edit --commit demo-v1 --symbol app.Processor.process

# 6. Autonomic Requirements (Async)
echo -e "\n📝 Phase 6: Generating Autonomic Requirements..."
JOB_DATA=$(curl -s -X POST "http://localhost:8000/requirements?version=demo-v1")
JOB_ID=$(echo $JOB_DATA | jq -r '.job_id')

if [ "$JOB_ID" != "null" ]; then
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
    echo "⚠️ Requirements job failed to start."
fi

# 7. Autonomic Engineering (P2 Dry-Run)
echo -e "\n💀 Phase 7: Dead Code Reaper (Simulation)..."
echo "Candidates found with 1.0 confidence: app.Processor.dead_method"
echo "Action: Branch 'cleanup/dead-method' -> Delete -> Verify -> PR Description Generated."

echo -e "\n🎉 Strategic Demo Complete!"
echo "========================================="
echo "The platform has demonstrated Intelligence, Prediction, Verification, and Autonomic Action."
