# Code Intelligence Platform – Testing Guide

This guide covers how to test the complete functionality of your code intelligence platform (ADR‑002), including code indexing, analysis queries, requirement generation, traceability, and MCP integration with Claude Code.

---

## 1. Prerequisites

- All containers are running: `podman-compose up -d`
- A small test repository is available (e.g., `test_repo` with Python and Java files)
- The `code-intel` CLI is available via `uv run python -m src`
- Ollama has a model pulled (e.g., `phi3:mini` or `nuextract`)

---

## 2. Testing Ingestion (Indexing)

### 2.1 Index a Local Directory

```bash
uv run python -m src analyze test_repo
```

**Expected output:**  
```
Analyzing test_repo...
Indexed with version 1775449703
```

### 2.2 Index a Git Repository

```bash
uv run python -m src analyze https://github.com/octocat/Hello-World.git --depth 1
```

**Expected:** Clones, indexes, cleans up, prints version.

### 2.3 Verify Database Entries

```bash
podman exec -it codeintel-postgres psql -U postgres -d codeintel -c "SELECT COUNT(*) FROM facts;"
```

Should be >0.

---

## 3. Testing Analysis Queries

### 3.1 Dead Code Detection

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "dead_code"}'
```

**Expected:** JSON list of symbols with `kind=function` or `method` that have no incoming calls.

### 3.2 Call Graph (Transitive Calls)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "transitive_calls"}'
```

**Expected:** List of `caller` → `callee` pairs.

### 3.3 Impact Analysis

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "impact", "symbol": "function:add"}'
```

**Expected:** Callers of `add` up to depth 3 (may be empty if no calls).

---

## 4. Testing Requirements Generation

### 4.1 Non‑streaming Endpoint

```bash
curl -X POST http://localhost:8000/requirements
```

**Expected:** JSON with `epic`, `feature`, `user_story`, `acceptance_criteria`, `tasks`.

### 4.2 Streaming Endpoint

Use the test script `tests/test-stream.py`:

```bash
python3 tests/test-stream.py
```

**Expected:** Tokens printed incrementally, ending with `✅ Streaming completed.`

### 4.3 Manual Model Test (Direct Ollama)

```bash
podman exec -it codeintel-ollama ollama run phi3:mini
```

Paste a short prompt to verify the model responds.

---

## 5. Testing Traceability

### 5.1 Check Traceability Table

After generating requirements, check if traceability links were stored:

```bash
podman exec -it codeintel-postgres psql -U postgres -d codeintel -c "SELECT * FROM requirement_traceability;"
```

### 5.2 Query Traceability via API

```bash
curl http://localhost:8000/trace/EPIC_TASK1   # replace with actual ID
```

**Expected:** List of symbols linked to that requirement.

### 5.3 CLI Trace Command (if implemented)

```bash
uv run python -m src trace EPIC_TASK1
```

---

## 6. Testing Multi‑Language Parsing

### 6.1 Java Parsing

Ensure `test_repo` contains a Java file (e.g., `Shape.java`). Index the directory containing it, then:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"rule": "dead_code"}'
```

Look for symbols like `class:Shape`, `method:getArea`.

### 6.2 Python Parsing

Similar test with `.py` files – functions and classes should appear in `current_symbols`.

---

## 7. Testing MCP Server (Claude Code Integration)

### 7.1 Run MCP Server Manually

```bash
podman exec -it codeintel-api uv run python -m src mcp
```

The server will start and wait for stdio commands (press Ctrl+C to stop).

### 7.2 Configure Claude Code

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "code-intel": {
      "command": "podman",
      "args": ["exec", "-i", "codeintel-api", "uv", "run", "python", "-m", "src", "mcp"]
    }
  }
}
```

### 7.3 Test in Claude Code

Restart Claude Code, then ask:

> "Show me dead code in the current repository"

Claude should invoke the `query_dead_code` tool and return results.

---

## 8. End‑to‑End Workflow Test

1. **Index** a small repository.
2. **Query** dead code – note some functions.
3. **Generate** requirements – get a JSON document.
4. **Store** traceability – check database.
5. **Query** traceability – retrieve symbols for a requirement.
6. **Change** the code (e.g., delete a dead function), re‑index, regenerate requirements – verify that the requirement changes.

---

## 9. Graph Engine Benchmarking

Run the Git-DAG engine comparison script to benchmark the ancestry lookback query and edge-filtering flow:

```bash
uv run python scripts/evaluate_graph_engines.py --runs 5
```

This writes a markdown report to [docs/engine_benchmark_results.md](docs/engine_benchmark_results.md). The benchmark uses synthetic commit and code-edge data to emulate the planned topological query path and compares Memtrace with TerminusDB. The CI workflow runs a one-iteration smoke test of this script automatically.

## 10. Performance & Load Testing (Optional)

- Use `ab` or `wrk` to stress the `/query` endpoint.
- Monitor container resource usage: `podman stats`.
- Test with large repositories (e.g., a real open‑source project) to measure indexing time.

---

## 11. Troubleshooting Common Issues

| Issue | Likely Fix |
|-------|-------------|
| Empty requirements | Check LLM model is pulled, reduce prompt size, switch to `phi3:mini` |
| `KeyError` in prompt | Use double braces `{{symbols}}` in prompt files and `.replace()` in code |
| `InvalidChunkLength` | Use the `requests`-based test script (not `httpx`) or increase chunk size |
| MCP server not responding | Ensure `podman exec` works without `-t` (use `-i` only) |
| Java symbols missing | Implement `JavaVisitor` properly; test with a simple file |

---

## 11. Success Criteria

- [ ] Indexing completes without errors.
- [ ] `/query` returns expected JSON.
- [ ] `/requirements` returns non‑empty structured output.
- [ ] Traceability links are stored and retrievable.
- [ ] MCP tools appear in Claude Code and return data.
- [ ] All tests pass with both Python and Java code.

---

This guide provides a complete test suite for your platform. Run these tests after any change to ensure stability and correctness.