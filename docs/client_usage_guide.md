# Code-Intel Client Usage Guide

This guide describes how to interact with the Code-Intel platform via its API and Model Context Protocol (MCP) server for advanced code analysis, timeline travel, and cross-repo dependency tracking.

## 1. Model Context Protocol (MCP) Integration

Code-Intel provides a first-class MCP server that can be integrated with AI assistants like Claude Code.

### Configuration
Expose the server using a `.mcp.json` or by adding it to your Claude Desktop config:
```json
{
  "mcpServers": {
    "code-intel": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.cli.main mcp"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://...",
        "USE_BITEMPORAL": "true"
      }
    }
  }
}
```

### Key MCP Tools

| Tool | Description |
|------|-------------|
| `query_call_graph` | Get the transitive call graph for a function at a specific commit. |
| `query_cross_repo_imports` | List external dependencies (Python, TS, Go) for the codebase. |
| `query_dead_code` | Find functions that are never called in the current topological state. |
| `query_impact` | Perform blast-radius analysis for a symbol. |
| `predict_impact` | Predict potential impact based on historical modification patterns with confidence weighting. |
| `semantic_search` | Search the codebase using natural language. |
| `generate_requirements` | Generate Epics and User Stories with traceability back to code symbols. |

---

## 2. API Usage (REST)

The platform exposes a FastAPI backend at `http://localhost:8000`.

### Timeline Travel (Topological Query)
Query the state of the codebase at any arbitrary Git commit SHA:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "rule": "query_call_graph",
    "commit_sha": "a1b2c3d4",
    "function": "auth.login"
  }'
```

### Cross-Repo Analysis
Identify external dependencies across polyglot microservices:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "rule": "query_cross_repo_imports",
    "commit_sha": "head"
  }'
```

### Impact Prediction
Use historical data to predict the effect of a proposed change. Results include a confidence score for each caller:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "rule": "predict_impact",
    "symbol": "payment.process_refund"
  }'
```

### Requirements Generation (Async)
Generation of business requirements from code can be time-consuming. This endpoint returns a `job_id` immediately, which you can use to poll for the status.

**Initiate Generation:**
```bash
curl -X POST http://localhost:8000/requirements
```
Response: `{"job_id": "...", "status": "pending"}`

**Poll for Status:**
```bash
curl http://localhost:8000/requirements/status/<job_id>
```
Response (when finished):
```json
{
  "status": "completed",
  "result": {
    "requirements": {
      "epic": "...",
      "feature": "...",
      "user_story": "...",
      "acceptance_criteria": [...],
      "tasks": [...]
    },
    "provenance": {
      "grounded_in": [...],
      "is_verified": true,
      "confidence": 1.0
    }
  }
}
```

### Fact Confidence Levels
The platform assigns confidence scores to call resolution:
- **1.0 (Certain)**: Direct calls to local functions.
- **0.5 (Heuristic)**: Calls resolved via attribute/member access.
- **0.3 (Dynamic)**: Calls via reflection (`getattr`, `eval`).

---

## 3. Reliability and Integrity

### Extractor Versioning
Every fact is tagged with the version of the extractor that produced it. When the platform detects a version mismatch at startup, it automatically deprecates older facts, ensuring that analyses are based on the latest, most accurate parsing logic.

### Incremental Invalidation
The platform uses a dependency-aware invalidation system. Derived facts (e.g., transitive closures) track which base facts they were derived from. If a file is modified and its symbols are updated, all dependent cached analyses are recursively marked as stale and re-computed on the next query.

### Verifying AI Insights (Provenance)
Every AI-generated artifact (like a requirement or summary) is grounded in specific source code facts. Clients can verify the integrity of these insights by checking the `grounded_in` list of fact IDs. The platform automatically validates these citations; if the LLM hallucinates a non-existent symbol, the artifact is flagged as `unverified` and its confidence score is capped at 0.5.

You can query all artifacts grounded in a specific fact using the debug endpoint:
```bash
curl http://localhost:8000/debug/provenance/42
```

## 4. High-Performance Features

### Bitset-Based Visibility
The platform uses bitset-based filtering for ancestry lookups. When querying large repositories (>100k commits), filtering happens in sub-microseconds. Clients can verify this performance by checking the `X-Cache-Status: hit` header in API responses.

### XOR Cache Synchronization
Clients connected to the MCP server benefit from incremental XOR synchronization. Instead of reloading the graph on every branch switch, the system only transmits the delta (added/removed items), ensuring an "instant" feel even for large enterprise codebases.

---

## 5. UI Explorer

The Web UI (`http://localhost:5173`) provides an interactive Graph Explorer:
1. **History Rail**: Navigate through Git commits on the left sidebar.
2. **Relationship Toggle**: Toggle between `CALLS` and `IMPORTS_FROM` edges.
3. **External Symbols**: Modules imported from other repositories are highlighted in the graph.
4. **Context Info**: Click any node to see its `introduced_in` version and historical modifications.
