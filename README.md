# Code Intelligence Platform (Production)

This is a production-ready version of ADR-002, using PostgreSQL + pgvector, Redis, async workers, and Ollama.

## Setup

```bash
# Clone or create project
./create-project-uv-prod.sh

# Start all services
podman-compose up -d

# Run database migrations
podman exec -it codeintel-api alembic upgrade head

# Pull a model into Ollama
podman exec -it codeintel-ollama ollama pull phi3:mini
```

## Usage

- API docs: http://localhost:8000/docs
- Analyze a repo: `curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"repo_path": "/repo"}'`
- Query dead code: `curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"rule": "dead_code"}'`
- Generate requirements: `curl -X POST http://localhost:8000/requirements`

## Production Considerations

- Replace `postgres` with Azure Database for PostgreSQL Flexible Server.
- Replace `redis` with Azure Cache for Redis.
- Replace `ollama` with vLLM on GPU nodes.
- Use a reverse proxy (Nginx) with HTTPS and authentication.
- Set up monitoring with Prometheus + Grafana.
