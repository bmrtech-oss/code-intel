# Code Intelligence Platform (Code-Intel)

Code-Intel is a production-ready, bi-temporal code intelligence platform built on a **Unified Data Plane**. It tracks code structure directly against a Git Directed Acyclic Graph (DAG) using a topological schema, enabling sub-millisecond historical queries, impact analysis, and LLM-driven requirements generation.

## 🏗️ Architecture Overview

The system integrates source code ingestion, atomic fact storage in a versioned SQL database, and declarative insights via a Git-aware dataflow engine.

```mermaid
graph TB
    subgraph "User Interfaces"
        CLI[CLI<br/>Typer]
        WebUI[Web UI<br/>React]
        MCP[MCP Server<br/>FastMCP]
    end

    subgraph "Unified Data Plane"
        API[FastAPI]
        Workspace[Workspace Manager<br/>Redis-backed Git-DAG]
        Engine[Dataflow Engine<br/>SQL + Recursive CTEs]
        subgraph "Optimized Storage"
            Store[(Write Model<br/>Append-only Facts)]
            ReadModel[(Read Model<br/>Graph Index)]
        end
    end

    subgraph "Ingestion Pipeline"
        Walker[File Walker]
        Parser[tree-sitter AST Handlers]
        FactInserter[Fact Inserter]
    end

    subgraph "LLM Integration"
        Ollama[Ollama / vLLM]
    end

    CLI --> API
    WebUI --> API
    MCP --> API
    API --> Workspace
    API --> Engine
    Engine --> Store
    Walker --> Parser --> FactInserter --> Store
    API --> Ollama
```

## 🚀 Key Features

- **Unified Fact Model**: All code data (symbols, calls, data flows) stored as versioned relational facts.
- **Git-DAG Topological Schema**: Native support for branches, merges, and rebases using `introduced_in`, `modified_in`, and `deleted_in` metadata.
- **Bitset-Based Visibility**: Sub-microsecond ancestry filtering using O(1) bitwise operations, optimized for massive commit histories (>100k commits).
- **True Delta (XOR) Sync**: High-performance incremental cache synchronization that only transmits and applies changes between commit states.
- **Timeline Travel**: High-performance historical queries and interactive graph visualization of code structure at any commit SHA.
- **Confidence-Weighted Analysis**: Every call edge is assigned a confidence score (0.0–1.0) based on resolution certainty (static vs. dynamic), providing an honest representation of ambiguity.
- **Hybrid Semantic Search**: Combines structural code identity with BGE-small embeddings via `txtai` for natural language code search.
- **MCP-Native**: First-class Model Context Protocol (MCP) server for seamless integration with AI assistants like Claude Code.
- **Multi-Repo Dependency Detection**: Cross-repo import tracking for Python, TypeScript, and Go, unified as `IMPORTS_FROM` edges.
- **Autonomic Engineering**: Targeted test execution via `verify_impact` to autonomously validate the safety of code modifications.
- **Async LLM Workers**: Requirement generation is offloaded to a background task queue (RQ) to prevent UI blocking, with results retrieved via polling.
- **JSON Schema Enforcement**: Uses Ollama's native grammar-constrained decoding to ensure 100% valid Pydantic models from the LLM.

## 🔄 System Flow

```mermaid
sequenceDiagram
    participant Dev as Developer / AI Assistant
    participant API as FastAPI / MCP
    participant Cache as Memory Cache (O(1))
    participant Adapter as BiTemporalAdapter
    participant Engine as Graph Engine (Git-DAG)

    Dev->>API: query_call_graph(commit_sha="b8f2")
    API->>Cache: check_active_state("b8f2")
    Cache-->>API: result (if hit)
    API->>Adapter: get_calls("b8f2")
    Adapter->>Engine: topological_lookback("b8f2")
    Engine-->>Adapter: filtered visibility set
    Adapter-->>API: call network
    API-->>Dev: JSON / Graph Result
```

## 🛠️ Setup

### One-Click Installation (Recommended)
```bash
./install.sh [env_name]
```
This script handles dependency syncing, starts the infrastructure, runs migrations, pulls the required LLM models, and configures AI agent integrations. You can optionally provide a custom name for the Python virtual environment (defaults to `.venv`).

### One-Click Strategic Demo
```bash
./demo.sh
```
Experience the full power of Code-Intel (Intelligence, Prediction, Verification, and Autonomic Action) using the built-in Python example.

### Manual Setup
```bash
# 1. Install dependencies
uv sync

# 2. Start services
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
- Query dead code at specific commit:
	```bash
	curl -X POST http://localhost:8000/query \
		-H "Content-Type: application/json" \
		-d '{"rule": "dead_code", "commit_sha": "abc123"}'
	```
- Semantic Search:
	```bash
	curl -X GET "http://localhost:8000/search?q=how+to+login"
	```
- Generate requirements:
	```bash
	curl -X POST http://localhost:8000/requirements
	```

## How parser output becomes requirements

The requirements flow is an end-to-end pipeline that starts with AST extraction and ends with traceable requirements:

1. The ingestion pipeline selects a language-specific visitor from the file extension and parses each source file into structured symbols and call edges.
2. Those facts are written into the versioned storage layer as symbol and call records, so each result is tied to a specific repository version.
3. The `/requirements` endpoint initiates an asynchronous background job and returns a `job_id`.
4. The background worker loads the current version’s facts and passes them to `LLMUDF`, which uses **Ollama's JSON Schema enforcement** to ensure the model output is strictly valid.
5. The LLM generates a structured JSON document (Epics, Features, Stories). The worker validates this against a Pydantic model, stores traceability links in `requirement_traceability`, and saves the final result.
6. The client polls the `/requirements/status/{job_id}` endpoint until completion to retrieve the final structured requirements and provenance metadata.

## Documentation Index

The repository documentation set lives under [docs](docs):

- [INSTALL.md](INSTALL.md) — full local setup guide, including prerequisites, services, and a sample repository walkthrough.
- [docs/demo_guide.md](docs/demo_guide.md) — step-by-step feature demo from ingestion through requirements generation.
- [docs/code-intel-design.md](docs/code-intel-design.md) — high-level system design and architecture notes.
- [docs/code-intel-nxt.md](docs/code-intel-nxt.md) — next-step roadmap and product direction.
- [docs/agent-integrations.md](docs/agent-integrations.md) — guide for connecting Code-Intel to Claude, Cursor, and Python agents.
- [docs/code-intel-nxt-prompts.md](docs/code-intel-nxt-prompts.md) — prompt and workflow notes for the next-generation experience.
- [docs/how-code-intel-is-different.md](docs/how-code-intel-is-different.md) — explanation of the platform’s differentiators.
- [docs/mcp-ui-foundations.md](docs/mcp-ui-foundations.md) — current MCP server and UI foundation status.
- [docs/use_cases_guide.md](docs/use_cases_guide.md) — practical use cases for modernization, impact analysis, history exploration, and AI-assisted development.
- [docs/engine_benchmark_results.md](docs/engine_benchmark_results.md) — latest graph engine benchmark report.
- [docs/code-intel-ai-review-results.md](docs/code-intel-ai-review-results.md) — review notes and findings for the current implementation direction.
- [docs/schema/git_dag_schema.yaml](docs/schema/git_dag_schema.yaml) — Git-DAG schema definition.

## MCP and UI Foundations

For the local MCP server, workspace-info tool, and the initial three-panel UI shell, see [docs/mcp-ui-foundations.md](docs/mcp-ui-foundations.md).

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

## Local Development

If you prefer a local flow using `venv` and standard Python tools instead of containers:

### 1. Backend Setup (Python)

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

```bash
# 1. Install dependencies and create venv
uv sync

# 2. Configure environment (customize for your local Postgres/Redis)
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/codeintel"
export REDIS_HOST="localhost"
export USE_BITEMPORAL="true"

# 3. Run database migrations
uv run alembic upgrade head

# 4. Start the FastAPI server
uv run fastapi dev src/api/server.py
```

### 2. Frontend Setup (React)

```bash
cd ui
npm install
npm run dev
```

### 3. Local LLM (Ollama)

Run Ollama locally and pull the required model:
```bash
ollama run phi3:mini
```

## Notes

- The repository contains `pyproject.toml` and other project files; check them for dependency and packaging guidance.
- For detailed client interaction, see [docs/client_usage_guide.md](docs/client_usage_guide.md).