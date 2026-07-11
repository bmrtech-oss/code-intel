#!/bin/bash
set -e

echo "🚀 Starting Code-Intel One-Click Installation..."

# 1. Check prerequisites
echo "🔍 Checking prerequisites..."
command -v uv >/dev/null 2>&1 || { echo "❌ uv is required. Install it via 'curl -LsSf https://astral.sh/uv/install.sh | sh'"; exit 1; }
command -v podman-compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || { echo "❌ docker-compose or podman-compose is required."; exit 1; }

COMPOSE_CMD="podman-compose"
if ! command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
fi

# 2. Setup Python environment
VENV_NAME=${1:-".venv"}
echo "📦 Syncing Python dependencies (Env: $VENV_NAME)..."
export UV_PROJECT_ENVIRONMENT="$VENV_NAME"
uv sync

# 3. Start Infrastructure
echo "🐳 Starting services (Postgres, Redis, Ollama)..."
# We use --build to ensure the latest code is used. 
# If you hit I/O errors, ensure you have enough disk space and your local .venv isn't being copied.
$COMPOSE_CMD up -d --build

# 4. Wait for Postgres and run migrations
echo "⏳ Waiting for services to be ready..."
MAX_RETRIES=60 # Increased timeout for heavy builds
COUNT=0
until $COMPOSE_CMD exec -i api python -c "import sqlalchemy; print('API Ready')" > /dev/null 2>&1 || [ $COUNT -eq $MAX_RETRIES ]; do
  if ! $COMPOSE_CMD ps | grep -q "api.*running"; then
    echo "   ⚠️ API container not yet running, waiting..."
  else
    echo "   Waiting for API dependencies ($COUNT/$MAX_RETRIES)..."
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
echo "🧠 Pulling Ollama model (phi3:mini)..."
$COMPOSE_CMD exec -i ollama ollama pull phi3:mini

echo ""
echo "🎉 Code-Intel is now ready for use!"
echo "-----------------------------------"
echo "REST API:    http://localhost:8000"
echo "Web UI:      http://localhost:5173 (if frontend is running)"
echo "MCP Server:  Configured for Claude Desktop & Cursor"
echo ""
echo "To analyze your first repository:"
echo "uv run --env $VENV_NAME code-intel analyze <PATH>"
