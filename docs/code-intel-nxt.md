# Final Revised Implementation Plan: code-intel Next Gen (Topological Engine)

This single, comprehensive document contains the **complete, production‑ready blueprint** for transforming `code-intel` into a bi‑temporal code intelligence platform with a Git‑DAG topological schema, MCP‑native interface, sub‑millisecond cache, and full time‑travel capabilities. It includes all architectural decisions, upgraded prompts, and implementation details for seamless execution by AI code assistants.

---

## 0. Executive Summary

| Aspect | Details |
|--------|---------|
| **Current State** | PostgreSQL + pgvector, Redis + RQ, FastAPI, Typer CLI, partial language handlers, and an `mcp` dependency. |
| **Architectural Shift** | Replaced wall‑clock bi‑temporality (`valid_from`/`valid_to`) with a **Git‑DAG Topological Schema** that uses `introduced_in`, `modified_in`, and `deleted_in` to handle branches, merges, and rebases natively. |
| **Engine Selection** | Memtrace evaluated in Phase 0; TerminusDB or a custom Git‑DAG schema over a graph‑native store serve as fallbacks. |
| **Total Duration** | **29 Weeks** (includes foundational assessment, UI prototyping, and advanced capabilities). |

---

## 1. Core Architectural Schema (Git Domain vs. Code Domain)

To eliminate temporal collisions during branching and merging, the storage layer separates version control topology from structural code entities.

```
    [ THE GIT DOMAIN ]
    ┌────────────────┐
    │     Commit     │◄──────┐ (PARENT_OF)
    │  (sha: "b8f2") │───────┘
    └───────┬────────┘
            │ (links via relationship attributes)
            ▼
    [ THE CODE DOMAIN ]
    ┌────────────────┐       (CALLS)       ┌────────────────┐
    │   Function     ├────────────────────►│    Function    │
    │ (id: "auth_v1")│                     │ (id: "db_query")│
    └────────────────┘                     └────────────────┘
```

- **Nodes (`DefNode`)**: Retain structural identity (e.g., fully qualified names like `src/auth.py::login`).
- **Edges & States**: Versioned inline using three metadata properties:
  - `introduced_in`: The Git commit SHA where the node/edge was first discovered.
  - `modified_in`: An array of commit SHAs tracking internal content mutations.
  - `deleted_in`: The commit SHA where the node/edge was removed (null if active).

### Schema Definition (YAML)

```yaml
# docs/schema/git_dag_schema.yaml
nodes:
  - Commit:
      properties:
        sha: string
        parents: list[string]
        branch: string
        author: string
        date: string
  - DefNode:
      properties:
        id: string           # unique structural identifier
        kind: string         # function, class, method, file, module
        fqn: string          # fully qualified name
        file: string
        introduced_in: string
        modified_in: list[string]
        deleted_in: string   # null if active
  - FileNode:
      properties:
        path: string
        introduced_in: string
        deleted_in: string

edges:
  - CALLS:
      from: DefNode
      to: DefNode
      properties:
        introduced_in: string
        deleted_in: string
  - CONTAINS:
      from: FileNode
      to: DefNode
      properties:
        introduced_in: string
        deleted_in: string
  - PARENT_OF:
      from: Commit
      to: Commit
```

---

## 2. Phased Implementation Plan with Upgraded Prompts

This section provides **phase‑by‑phase tasks and AI‑ready prompts**. Each prompt is hyper‑specific, context‑aware, and enforces the Git‑DAG design from the start.

---

### Phase 0: Foundation & Topological Assessment (Weeks 1–3)

**Goal:** Bridge core language gaps, initialize the Git‑aware workspace engine, define the Git‑DAG schema, and validate the bi‑temporal graph store.

#### Pre‑Phase: Schema Definition (Task 0.0)

**Prompt:**
> **Context:** We are building `code-intel`, a next‑gen code intelligence platform. We track code structure directly against a Git Directed Acyclic Graph (DAG) using a topological schema rather than database timestamps.
> **Task:** Design and document the core Git‑DAG schema. Define:
> - **Commit Node:** `(commit:Commit {sha: string, parents: list[string], branch: string, author: string, date: string})`
> - **DefNode:** `(def:DefNode {id: string, kind: string, fqn: string, file: string, introduced_in: string, modified_in: list[string], deleted_in: string})`
> - **CallEdge:** `(a)-[:CALLS {introduced_in: string, deleted_in: string}]->(b)`
> - **FileNode:** `(file:FileNode {path: string, introduced_in: string, deleted_in: string})`
> Write the schema as a YAML or JSON file in `docs/schema/` for version control.

#### Task 0.1 & 0.2: Language Handlers & Golden Test Suite

**Prompt:**
> **Context:** We are building `code-intel`, a next-gen code intelligence platform. We track code structure directly against a Git Directed Acyclic Graph (DAG) using a topological schema rather than database timestamps.
> **Task:**
> 1. Create Tree-sitter AST handlers for Python, TypeScript, and Go (`src/lang/python_handler.py`, `ts_handler.py`, `go_handler.py`). They must extract structural identities: fully qualified names for modules, classes, functions, and call actions. Add an explicit pass or stub for tracking cross-file dynamic method invocations.
> 2. Build a small multi-language code fixture workspace inside `tests/golden/` that simulates a common real-world architecture (e.g., an API handler calling a repository layer). Include explicit instances of dead functions and deep call chains to test parsing accuracy.

#### Task 0.3 & 0.4: Git‑DAG Workspace & Git‑Aware MCP Server

**Upgraded Prompt:**
> **Context:** We need a session layer that maps user environment lookups to specific points in a project's repository history.
> **Task:**
> 1. Write `src/core/workspace.py`. Implement a Redis-backed session manager that stores and maintains active workspace sessions. Store `current_branch`, `current_sha`, and the **branch tip SHA**. For ancestry lookups, do **not** pre‑cache the entire ancestor list. Instead, implement a paginated ancestry query that walks the commit DAG on demand, with an in‑memory LRU for the most recent 100 commits. Use Redis to cache the ancestor list per commit with a TTL of 1 hour.
> 2. Build an asynchronous MCP (Model Context Protocol) server in `src.mcp.server.py` using the python `mcp` SDK. Expose 5 core tools: `query_call_graph`, `query_dead_code`, `generate_requirements`, `query_impact`, and `semantic_search`. **Crucial design constraint:** Every tool definition must accept an optional `commit_sha: str` input parameter. If this parameter is omitted by the AI client, default automatically to the active workspace SHA retrieved from Redis.

#### Task 0.5 & 0.6: Engine Evaluation Script

**Prompt:**
> **Context:** We are choosing our core bi-temporal graph storage system. We are evaluating Memtrace and TerminusDB.
> **Task:** Write a Python profiling script (`scripts/evaluate_graph_engines.py`) that spins up containers for both engines, populates them with our mock Git-DAG commit nodes, and benchmarks query performance. The benchmark must test a topological lookback query: given a target commit SHA, fetch its historical ancestor SHAs, and then filter code edges where `edge.introduced_in` is part of that ancestry list. Generate a markdown comparison table displaying query latencies for both engines.

---

### Phase 0.5: Initial MCP & UI Foundations (Weeks 4–5)

**Goal:** Expose the complete toolset to automated environments and build the visual shell.

#### Prompt for Task 0.5.1, 0.5.2 & 0.5.3: Tool Extension & UI Wireframe

**Prompt:**
> **Context:** Our core MCP tools need full analytical logic, and we need a lightweight visual interface to switch between repository states.
> **Task:**
> 1. Complete the tool execution layers in `src.mcp.server.py` to connect seamlessly with the workspace storage layer. Add `get_workspace_info` to read current Git states.
> 2. Initialize a clean frontend application in `ui/`. Build a responsive three-panel interface layout (Left: File tree & Git history branch selector, Center: Interactive graph rendering view, Right: Interactive MCP Chat panel). Use Zustand for state management and cache the last 5 viewed commits to avoid redundant fetches.
> 3. Create a `.mcp.json` configuration manifest that exposes this local server directly to tooling like Claude Code, allowing it to invoke our workspace analysis tools.

---

### Phase 1: Storage Migration to Git‑DAG Engine [IMPLEMENTED]

**Goal:** Deprecate flat relational PostgreSQL layouts and migrate structural facts directly into a topological format.

- **Tasks 1.1, 1.1a, 1.2**: Implemented `scripts/export_postgres_to_jsonl.py` and `scripts/import_jsonl_to_engine.py`.
- **Tasks 1.3, 1.4, 1.5**: Implemented `src/storage/bitemporal_adapter.py` and `src/storage/graph_engine.py`. Validated via `scripts/compare_legacy_vs_topo.py`.

---

### Phase 2: Cache Layer Integration & Delta Sync [IMPLEMENTED]

**Goal:** Establish `codebase-memory-mcp` as an ephemeral, read‑optimized mirror for instant branch navigation.

- **Tasks 2.1, 2.2, 2.3, 2.5**: Implemented `src/cache/memory_cache.py`, `src/cache/cdc_listener.py`, and `src/cache/cache_bootstrap.py`.

---

### Phase 3: Timeline Travel & Visualization [IMPLEMENTED]

**Goal:** Expose DAG‑based navigation options across the command line, web clients, and requirements pipelines.

- **Tasks 3.1, 3.2, 3.3**: Updated `src/cli/main.py` and `src/api/server.py` for `--commit`/`commit_sha` support. Integrated **Cytoscape.js** in `ui/src/GraphExplorer.tsx` with a history rail.

---

### Phase 4: Semantic Layer Integration [IMPLEMENTED]

**Goal:** Combine structural graph intelligence with vector embeddings via `txtai` for accurate hybrid search.

- **Tasks 4.1, 4.1a, 4.2**: Implemented `src/semantic/indexer.py` and `src/semantic/search.py` using `txtai` and `BAAI/bge-small-en-v1.5`. Updated Python handler to extract docstrings/signatures.

---

### Phase 5: Production Hardening & Phased Rollout [COMPLETED]

**Goal:** Ensure enterprise‑grade resiliency, scale testing, and safe production deployment.

- **Bitset-Based Visibility**: Implemented O(1) bitwise visibility filtering in `SimpleGraphEngine` and `MemoryCache` to support >100k commits with sub-microsecond performance.
- **Stress Testing**: Implemented `tests/performance/stress_run.py` to verify engine performance on deep commit histories.
- **Observability**: Integrated Prometheus metrics for tracking cache hit ratios, sync delays, and lookup latencies.

---

### Phase 6: Advanced Platform Capabilities [COMPLETED]

**Goal:** Deliver deep cross‑system analysis and integrated workspace tools.

- **Multi-Repo Dependency Detection**: Extended TypeScript and Go handlers to detect external imports, unified as `IMPORTS_FROM` edges.
- **Impact Prediction**: Implemented `ImpactPredictor` in `src/analytics/predictor.py` using historical `modified_in` metadata to calculate structural coupling.

---

## 3. Future Roadmap: Enterprise Scalability & Intelligence

While the core topological engine is complete, the following areas are identified for further development:

### 3.1 Distributed Indexing & Global Deduplication
- **Task:** Implement a distributed ingestion worker pool (e.g., using Celery or Temporal) to handle repositories with >10M LOC.
- **Goal:** Enable global symbol deduplication across multiple repositories to identify common internal library dependencies and version skew.

### 3.2 Advanced Predictive Refactoring
- **Task:** Enhance `ImpactPredictor` with ML-based sequence modeling (e.g., Transformers) to predict which files will likely change based on past commit patterns, rather than just structural coupling.
- **Goal:** Provide "Likely Next Edit" suggestions in the UI Graph Explorer.

### 3.3 Zero-Trust Workspace Authorization
- **Task:** Implement fine-grained RBAC (Role-Based Access Control) integrated with GitHub/GitLab SSO.
- **Goal:** Enforce that cross-repo import visibility in the Graph Explorer only shows modules the user has explicit access to.

### 3.4 Incremental Semantic Re-indexing
- **Task:** Refactor `SemanticIndexer` to perform incremental updates based on the XOR deltas from the topological engine.
- **Goal:** Reduce embedding generation time by only processing changed function headers and docstrings.

---

## 4. Cross‑Cutting Concerns (Observability & Logging)

**Prompt for All Phases:**
> **Context:** Debugging a distributed, Git‑aware system requires rich contextual logging.
> **Task:** Ensure every adapter, cache, and engine module uses structured logging (e.g., `structlog` or `json‑logger`) with `commit_sha`, `workspace_id`, and `request_id` as default fields. This will enable distributed tracing across the MCP server, storage, and cache layers.

---

## 4. Risk Mitigation Index

| Threat Scenario | Proactive Defense Strategy | Owner |
|-----------------|----------------------------|-------|
| **Memtrace fails relation scale test** | Maintain strict `BiTemporalAdapter` decoupling; switch to TerminusDB within 1 week | Storage Lead |
| **Data variation or data loss during migration** | Run legacy and new systems in parallel; use feature flags for instant traffic fallback | DevOps Lead |
| **Invalidation storm on large branch merges** | Pre‑compute delta packages explicitly during commit ingestion | Backend Lead |
| **Deep history traversal performance** | Use bitset caching and paginated ancestry queries | Backend Lead |
| **Cache cold‑start latency** | Full rebuild runs in background; serve stale data during rebuild | Backend Lead |

---

## 5. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Current State Query Latency** | <1ms | Cache (codebase-memory-mcp) |
| **Historical Query Latency** | <100ms | Direct graph engine query |
| **Timeline Accuracy** | 100% | Golden test suite |
| **Cache Synchronization Freshness** | <5s | CDC stream monitoring |
| **Indexing Speed** | <5 min for 1M LOC | Benchmark |
| **Cache Hit Rate** | >95% | Prometheus metrics |

---

## 6. Immediate Week 1 Action Plan

1. **Lock Down the Model:** Finalize the internal tracking properties (`introduced_in`, `modified_in`, `deleted_in`) and the schema YAML.
2. **Launch Tasks 0.0, 0.1 & 0.3:** Define schema, begin building Python/TS/Go tree‑sitter modules, and set up Redis Git‑DAG workspace.
3. **Spin Up Evaluation Stores:** Deploy local docker instances of Memtrace and TerminusDB to prepare for ancestry lookup testing in Week 3.

---

## 7. Conclusion

This revised plan incorporates all feedback and upgrades. It provides a clear, incremental path to a world‑class code intelligence platform with a Git‑DAG topological engine, MCP‑native tools, and full time‑travel. The prompts are ready to feed into AI code assistants, ensuring consistent, high‑quality implementations.

**Status:** Approved. Proceed immediately.