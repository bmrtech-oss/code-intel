#!/bin/bash

echo "🗑️ Starting Code-Intel Purge & Cleanup..."

# 1. Determine Compose Command
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD=""
fi

# 2. Stop and remove containers, volumes, and images
if [ -n "$COMPOSE_CMD" ]; then
    echo "🛑 Stopping and removing containers and volumes..."
    $COMPOSE_CMD down -v --rmi local 2>/dev/null || true
fi

# 3. Clean up Podman/Docker specifically if they are stuck
if command -v podman >/dev/null 2>&1; then
    echo "🚢 Cleaning up Podman resources..."
    podman ps -aq --filter "name=codeintel" | xargs -r podman rm -f 2>/dev/null || true
    podman volume ls -q --filter "name=codeintel" | xargs -r podman volume rm 2>/dev/null || true
elif command -v docker >/dev/null 2>&1; then
    echo "🐳 Cleaning up Docker resources..."
    docker ps -aq --filter "name=codeintel" | xargs -r docker rm -f 2>/dev/null || true
    docker volume ls -q --filter "name=codeintel" | xargs -r docker volume rm 2>/dev/null || true
fi

# 4. Clear Port Conflicts
clear_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        PID=$(lsof -Pi :$port -sTCP:LISTEN -t)
        if [ -n "$PID" ]; then
            echo "🔥 Clearing process $PID on port $port..."
            kill -9 $PID 2>/dev/null || true
        fi
    fi
}

echo "🔌 Checking for lingering port conflicts..."
for port in 8000 5432 6379 11434; do
    clear_port $port
done

# 5. Remove virtual environment and caches
echo "📦 Cleaning up local artifacts..."
rm -rf .venv
rm -rf .pytest_cache
rm -rf .ruff_cache
rm -rf .mypy_cache
find . -type d -name "__pycache__" -exec rm -rf {} +

# 6. Clean uv cache
if command -v uv >/dev/null 2>&1; then
    echo "🧹 Cleaning uv cache..."
    uv cache clean
fi

# 7. Optional system-wide cleanup
read -p "❓ Would you like to perform a full container system prune? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v podman >/dev/null 2>&1; then
        podman system prune -a -f
    elif command -v docker >/dev/null 2>&1; then
        docker system prune -a -f
    fi
fi

echo "✨ Cleanup complete!"
