# Code-Intel: Complete Feature Demo Guide

This guide provides a step-by-step walkthrough of the Code-Intel platform's core capabilities, from source ingestion to advanced topological analysis and LLM-driven requirements generation.

---

## 1. Environment Setup

Ensure you have the necessary dependencies installed and services running.

```bash
# Install dependencies
uv sync

# Start the core services (PostgreSQL, Redis)
podman-compose up -d

# Enable the new topological architecture
export USE_BITEMPORAL=true
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/codeintel"
```

---

## 2. Source Ingestion & Migration

Code-Intel ingests source code into atomic relational facts and then migrates them to a high-performance topological format.

### 2.1 Ingest a Repository
```bash
# Ingest the current repository as version 'v1'
uv run python -m src.cli.main analyze . --version v1
```

### 2.2 Migrate to Topological Format
```bash
# Export relational facts to topological JSONL
uv run python scripts/export_postgres_to_jsonl.py

# Verified JSONL files (nodes.jsonl, edges.jsonl, commits.jsonl) are created.
```

---

## 3. High-Performance Time-Travel

Navigate the history of your codebase with sub-millisecond latency.

### 3.1 CLI-based Historical Query
```bash
# Query dead code at version v1
uv run python -m src.cli.main query dead_code --commit v1
```

### 3.2 Visual Time-Travel (Web UI)
1. Start the API and UI:
   ```bash
   uv run python -m src.cli.main serve &
   cd ui && npm run dev
   ```
2. Open `http://localhost:5173`.
3. Use the **History Rail** (left panel) to select different commit SHAs.
4. Observe the **Graph Explorer** re-rendering the call graph for that specific point in time.

---

## 4. Hybrid Semantic Search

Find code using natural language, combining structural identity with LLM embeddings.

```bash
# Re-index the semantic layer (uses BAAI/bge-small-en-v1.5)
uv run python -c "import asyncio; from src.semantic.indexer import SemanticIndexer; import json; nodes = [json.loads(l) for l in open('nodes.jsonl')]; asyncio.run(SemanticIndexer().index_nodes(nodes))"

# Perform a search
curl -X GET "http://localhost:8000/search?q=how+to+handle+git+cloning"
```

---

## 5. Predictive Impact Analysis

Predict the blast radius of a code change based on both the call graph and historical co-modification patterns.

```bash
# Predict impact for a specific function
curl -X GET "http://localhost:8000/analytics/predict-impact?symbol=src.core.git_handler.GitRepoHandler.clone&commit_sha=v1"
```

---

## 6. LLM-Driven Requirements Generation

Generate epics, features, and stories directly from the structural facts of your codebase.

```bash
# Generate requirements for the current state
curl -X POST http://localhost:8000/requirements
```

### How it Works: Parser Output → Requirements

The generation process is **fact-enhanced**, which is significantly more robust than traditional "Naive LLM Prompting".

#### The Pipeline:
1. **Deterministic Extraction**: The `tree-sitter` handlers extract strict identities (FQNs, signatures, docstrings, and call networks).
2. **Context Compression**: Instead of feeding thousands of lines of raw source code to an LLM (which exceeds context windows and invites hallucinations), we feed it a **structured JSON summary** of the facts.
3. **UDF Execution**: The `LLMUDF` (`src/core/udf.py`) constructs a prompt containing these facts and calls a local model (via Ollama).
4. **Traceability**: Because the input is based on `DefNode` IDs, the generated requirements can be deterministically linked back to the exact code symbols that inspired them.

#### Why is this better than just using an LLM on raw code?

| Feature | Naive LLM (Raw Code) | Code-Intel (Fact-Enhanced) |
|---------|-----------------------|----------------------------|
| **Scalability** | Limited by context window (e.g., 128k tokens). | Unlimited - handles millions of LOC via fact grouping. |
| **Accuracy** | Prone to hallucinations on deep call chains. | Deterministic - based on verified AST call graphs. |
| **History** | Usually limited to the current file or "active" window. | Git-aware - can generate requirements for any point in history. |
| **Traceability** | "Black box" - hard to know why a requirement was generated. | Fully traceable - links specific requirements to `symbol_id` in the DB. |
| **Cost/Latency** | High (processing raw text is expensive). | Low (processing structured facts is 10x faster and cheaper). |

---

## 7. Advanced: Model Context Protocol (MCP)

Connect Claude Code or other AI assistants directly to your codebase intelligence.

```bash
# Start the MCP server
uv run python -m src.mcp_server
```

Claude can now call tools like `predict_impact`, `query_dead_code`, and `semantic_search` to assist you in real-time during your development sessions.
