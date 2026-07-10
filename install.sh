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
echo "📦 Syncing Python dependencies..."
uv sync

# 3. Start Infrastructure
echo "🐳 Starting services (Postgres, Redis, Ollama)..."
$COMPOSE_CMD up -d

# 4. Wait for Postgres and run migrations
echo "⏳ Waiting for database to be ready..."
sleep 10 # Basic wait, could be more robust with a loop
echo "📂 Running database migrations..."
$COMPOSE_CMD exec -it api alembic upgrade head

# 5. Setup AI Agent Integrations
echo "🤖 Configuring AI agent integrations..."
./scripts/setup-agent.sh

# 6. Initialize local Ollama model
echo "🧠 Pulling Ollama model (phi3:mini)..."
$COMPOSE_CMD exec -it ollama ollama pull phi3:mini

echo ""
echo "🎉 Code-Intel is now ready for use!"
echo "-----------------------------------"
echo "REST API:    http://localhost:8000"
echo "Web UI:      http://localhost:5173 (if frontend is running)"
echo "MCP Server:  Configured for Claude Desktop & Cursor"
echo ""
echo "To analyze your first repository:"
echo "code-intel analyze --repo-path <PATH>"
