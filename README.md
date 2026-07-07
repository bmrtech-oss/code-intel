# Code Intelligence Platform (Production)

This is a production-ready version of ADR-002, using PostgreSQL + pgvector, Redis, async workers, and Ollama.

## Setup

```bash
# Clone or create project
./create-project-uv-prod.sh

# Start all services (Linux/macOS). On Windows use a compatible container runtime.
podman-compose up -d

# Run database migrations
podman exec -it codeintel-api alembic upgrade head

# Pull a model into Ollama
podman exec -it codeintel-ollama ollama pull phi3:mini
```

## Usage

- API docs: http://localhost:8000/docs
- Analyze a repo:
	```bash
	curl -X POST http://localhost:8000/analyze \
		-H "Content-Type: application/json" \
		-d '{"repo_path": "/repo"}'
	```
- Query dead code:
	```bash
	curl -X POST http://localhost:8000/query \
		-H "Content-Type: application/json" \
		-d '{"rule": "dead_code"}'
	```
- Generate requirements:
	```bash
	curl -X POST http://localhost:8000/requirements
	```

## Graph Engine Benchmarking

To compare the mock Git-DAG query path for Memtrace and TerminusDB, run:

```bash
uv run python scripts/evaluate_graph_engines.py --runs 5
```

The script launches lightweight container-backed mock servers, populates them with synthetic commit and code-edge data, executes a topological ancestry lookup plus an edge filter, and writes a markdown comparison report to [docs/engine_benchmark_results.md](docs/engine_benchmark_results.md). CI also runs a smoke-test version of this workflow to keep the benchmark path covered automatically.

## Production Considerations

- Replace `postgres` with Azure Database for PostgreSQL Flexible Server.
- Replace `redis` with Azure Cache for Redis.
- Replace `ollama` with vLLM on GPU nodes.
- Use a reverse proxy (Nginx) with HTTPS and authentication.
- Set up monitoring with Prometheus + Grafana.

## Notes

- The repository contains `pyproject.toml` and other project files; check them for dependency and packaging guidance.
- If you want a local development flow using `venv` and Python tools instead of containers, tell me and I can add a "Local development" section with commands.
