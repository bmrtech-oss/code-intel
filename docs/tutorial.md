# Building a Code Intelligence Platform: A Hands-On Tutorial with Code-Intel

*Learn how to build a production-ready code intelligence platform that understands your codebase at a granular level—tracking symbols, call graphs, and historical changes across Git commits.*

---

## The Problem: Codebases Are Hard to Understand

Modern codebases are complex. When you join a new team, inherit a legacy project, or simply return to code you wrote six months ago, the same questions arise:

- *What does this function actually do?*
- *If I change this method, what breaks?*
- *Why was this code written this way?*
- *Can I generate documentation or requirements from this codebase?*

Traditional tools give you grep, maybe a half-working IDE indexer, and hope. But what if you could query your codebase like a database—asking questions about dead code, impact analysis, and historical changes with sub-millisecond latency?

Enter **Code-Intel**.

---

## What Is Code-Intel?

Code-Intel is an open-source, production-ready code intelligence platform built on a **Unified Data Plane** that tracks code structure directly against a Git Directed Acyclic Graph (DAG) using a topological schema.

The architecture combines several powerful ideas:

| Component | What It Does |
|-----------|--------------|
| **Git-DAG Topological Schema** | Tracks symbols with `introduced_in`, `modified_in`, and `deleted_in` metadata—natively handling branches, merges, and rebases |
| **Bitset-Based Visibility** | Enables O(1) ancestry filtering using bitwise operations, optimized for massive commit histories (>100k commits) |
| **Hybrid Semantic Search** | Combines structural code identity with BGE-small embeddings via `txtai` for natural language code search |
| **LLM as a UDF** | Treats requirements generation as a first-class query inside the database flow |
| **MCP-Native** | First-class Model Context Protocol (MCP) server for seamless integration with AI assistants like Claude Code |

The system integrates source code ingestion, atomic fact storage in a versioned SQL database, and declarative insights via a Git-aware dataflow engine.

---

## Prerequisites

Before we dive in, make sure you have:

- **Ubuntu 22.04+**, Debian 12+, or WSL2 on Windows 10/11
- **Python 3.11+**
- **Podman or Docker-compatible runtime**
- **Git**

On Ubuntu/Debian, install the system packages:

```bash
sudo apt update
sudo apt install -y git python3.11 python3.11-venv podman podman-compose
```

Then install `uv`, the fast Python package installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

---

## Step 1: Clone and Set Up the Project

```bash
git clone https://github.com/bmrtech-oss/code-intel.git
cd code-intel
```

Create the Python environment and sync dependencies:

```bash
uv venv .venv-linux
source .venv-linux/bin/activate
uv sync
```

---

## Step 2: Start the Supporting Services

Code-Intel expects PostgreSQL, Redis, and Ollama to be available. The repository includes a Compose file for this purpose:

```bash
podman-compose up -d
```

Verify the services are running:

```bash
podman ps
```

You should see containers for the database, Redis, and Ollama.

Pull a model for requirements generation:

```bash
podman exec -it codeintel-ollama ollama pull phi3:mini
```

*This may take several minutes depending on your network speed.*

---

## Step 3: Start the API Server

From the repo root:

```bash
uv run python -m src.cli.main serve
```

The API will be available at `http://localhost:8000`. You can verify it's up with:

```bash
curl http://localhost:8000/docs | head
```

---

## Step 4: Create Sample Test Data

Let's create a small sample repository to index and query:

```bash
mkdir -p /tmp/codeintel-sample/src
```

Create `app.py`:

```bash
cat > /tmp/codeintel-sample/src/app.py <<'PY'
from src.helpers import format_message

def greet(name: str) -> str:
    return format_message(f"Hello {name}")

def unused_helper() -> str:
    return "unused"
PY
```

Create `helpers.py`:

```bash
cat > /tmp/codeintel-sample/src/helpers.py <<'PY'
def format_message(text: str) -> str:
    return text.upper()
PY
```

This sample gives you:
- One function (`greet`) that calls another function (`format_message`)
- One unused helper that will appear in dead-code analysis

---

## Step 5: Index the Sample Repository

```bash
uv run python -m src.cli.main analyze /tmp/codeintel-sample --version sample-v1
```

The indexing step parses the sample files and writes facts into the versioned storage layer.

---

## Step 6: Query Your Codebase

Now the fun part—querying your codebase like a database.

### 6.1 Find Dead Code

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "dead_code", "commit_sha": "sample-v1"}'
```

You should see `unused_helper` appear in the result set.

### 6.2 Analyze Impact

Want to know what happens if you change `greet`?

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "impact", "commit_sha": "sample-v1", "symbol": "src.app.greet"}'
```

### 6.3 Generate Requirements with LLM

This is where Code-Intel gets really interesting. Generate epics, features, and stories directly from the structural facts of your codebase:

```bash
curl -X POST http://localhost:8000/requirements \
  -H "Content-Type: application/json" \
  -d '{"version": "sample-v1"}'
```

The endpoint returns structured requirements and stores traceability links for the underlying symbols.

---

## How Requirements Generation Works

The requirements flow is an end-to-end pipeline that starts with AST extraction and ends with traceable requirements:

1. **Parser Stage**: Language-specific visitors walk the AST and emit structured facts—symbol definitions, file locations, kinds, and call edges.

2. **Storage Stage**: The ingestion pipeline writes those facts into the versioned storage layer, available for the active repository version and for historical queries.

3. **Prompt Construction**: The `/requirements` endpoint loads the current version's symbol and call rows and passes them to `LLMUDF`, which serializes them into a prompt using the model-specific template from the prompts directory.

4. **LLM Stage**: Ollama generates a JSON response describing epics, features, and stories; the server cleans and parses the response and produces structured requirements.

5. **Traceability Stage**: The API inserts links into `requirement_traceability` so each requirement can be tied back to the original symbol IDs.

### Why Is This Better Than Just Using an LLM on Raw Code?

| Feature | Naive LLM (Raw Code) | Code-Intel (Fact-Enhanced) |
|---------|---------------------|---------------------------|
| **Scalability** | Limited by context window (e.g., 128k tokens) | Unlimited—handles millions of LOC via fact grouping |
| **Accuracy** | Prone to hallucinations on deep call chains | Deterministic—based on verified AST call graphs |
| **History** | Usually limited to the current file | Git-aware—can generate requirements for any point in history |
| **Traceability** | "Black box"—hard to know why a requirement was generated | Fully traceable—links specific requirements to `symbol_id` in the DB |
| **Cost/Latency** | High (processing raw text is expensive) | Low (processing structured facts is 10x faster and cheaper) |

---

## Advanced: Semantic Search

Code-Intel combines structural code identity with embeddings for natural language search:

```bash
# Re-index the semantic layer (uses BAAI/bge-small-en-v1.5)
uv run python -c "import asyncio; from src.semantic.indexer import SemanticIndexer; import json; nodes = [json.loads(l) for l in open('nodes.jsonl')]; asyncio.run(SemanticIndexer().index_nodes(nodes))"

# Perform a search
curl -X GET "http://localhost:8000/search?q=how+to+handle+git+cloning"
```

---

## Advanced: Predictive Impact Analysis

Predict the blast radius of a code change based on both the call graph and historical co-modification patterns:

```bash
curl -X GET "http://localhost:8000/analytics/predict-impact?symbol=src.core.git_handler.GitRepoHandler.clone&commit_sha=v1"
```

---

## Advanced: Model Context Protocol (MCP)

Connect Claude Code or other AI assistants directly to your codebase intelligence:

```bash
uv run python -m src.cli.main mcp
```

Claude can now call tools like `predict_impact`, `query_dead_code`, and `semantic_search` to assist you in real-time during your development sessions.

---

## Optional: Start the Web UI

If the frontend is available in your checkout:

```bash
cd ui
npm install
npm run dev
```

Then open `http://localhost:5173` and use the **History Rail** (left panel) to select different commit SHAs. Observe the Graph Explorer re-rendering the call graph for that specific point in time.

---

## Stopping and Resetting Services

Stop the containers:

```bash
podman-compose down
```

To remove volumes and reset the database:

```bash
podman-compose down -v
```

---

## Troubleshooting

### API Fails to Start
- Check the logs with `podman logs codeintel-api`
- Confirm the database and Redis containers are healthy

### Requirements Are Empty
- Ensure Ollama is running and the model was pulled successfully
- Verify the API can reach `http://ollama:11434` from the container network

### Indexing Reports No Symbols
- Confirm the sample files exist at the path you passed into the analyzer
- Check that the repository uses a supported extension such as `.py`

---

## What Makes Code-Intel Different?

- **Git-Native Visibility**: The move from wall-clock timestamps to commit-ancestry tracing natively handles branches, merges, and rebases without temporal collisions.
- **Unified Data Plane**: All interfaces (CLI, REST API, Web UI, MCP) query the same versioned facts, ensuring consistency.
- **True Delta Calculation**: High-performance incremental cache synchronization that only transmits and applies changes between commit states.

---

## Next Steps

- Add more sample files in other languages (Python, TypeScript, Go are supported)
- Try the MCP workflow with Claude Code or similar clients
- Explore the benchmark script in the `scripts` folder for graph-engine comparisons

---

## Conclusion

Code-Intel transforms how you interact with your codebase. Instead of guessing what a function does or manually tracing call graphs, you get a queryable, time-travel-enabled intelligence layer that understands your code at a structural level.

Whether you're:

- **Modernizing a legacy codebase** and need to understand dependencies
- **Onboarding new developers** and want to generate documentation automatically
- **Building AI-powered developer tools** that need deep code understanding

...Code-Intel provides a foundation that's both powerful and production-ready.

---

*Code-Intel is open-source and available at [github.com/bmrtech-oss/code-intel](https://github.com/bmrtech-oss/code-intel). Star the repo, try it out, and contribute to the project!*