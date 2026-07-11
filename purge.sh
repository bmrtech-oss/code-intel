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

# 4. Remove virtual environment
if [ -d ".venv" ]; then
    echo "📦 Removing Python virtual environment (.venv)..."
    rm -rf .venv
fi

# 5. Optional system-wide cleanup
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
