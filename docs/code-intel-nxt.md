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
> 2. Build an asynchronous MCP (Model Context Protocol) server in `src/mcp_server.py` using the python `mcp` SDK. Expose 5 core tools: `query_call_graph`, `query_dead_code`, `generate_requirements`, `query_impact`, and `semantic_search`. **Crucial design constraint:** Every tool definition must accept an optional `commit_sha: str` input parameter. If this parameter is omitted by the AI client, default automatically to the active workspace SHA retrieved from Redis.

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
> 1. Complete the tool execution layers in `src/mcp_server.py` to connect seamlessly with the workspace storage layer. Add `get_workspace_info` to read current Git states.
> 2. Initialize a clean frontend application in `ui/`. Build a responsive three-panel interface layout (Left: File tree & Git history branch selector, Center: Interactive graph rendering view, Right: Interactive MCP Chat panel). Use Zustand for state management and cache the last 5 viewed commits to avoid redundant fetches.
> 3. Create a `.mcp.json` configuration manifest that exposes this local server directly to tooling like Claude Code, allowing it to invoke our workspace analysis tools.

---

### Phase 1: Storage Migration to Git‑DAG Engine (Weeks 6–9)

**Goal:** Deprecate flat relational PostgreSQL layouts and migrate structural facts directly into a topological format.

#### Task 1.1, 1.1a & 1.2: Topological Exporter, Migration Mapping, Transaction Importer

**Prompt:**
> **Context:** We are deprecating our old PostgreSQL database schema to move entirely to our new topological graph database model.
> **Task:**
> 1. Write `scripts/export_postgres_to_jsonl.py`. Read rows from the legacy PostgreSQL `facts`, `symbols`, and `calls` tables. Flatten and map them into three specific JSON Lines output targets: `commits.jsonl` (mapping SHAs and parent dependencies), `nodes.jsonl` (capturing structural identities with `introduced_in`), and `edges.jsonl` (capturing call networks with `introduced_in` and `deleted_in`).
> 2. **Crucial – Handle rebase/cherry‑pick:** For each fact, use `git log --follow` to find the earliest commit where the file appeared. If a fact existed before the tool started tracking, set `introduced_in` to the first tracked commit. If multiple commits modified the same symbol, append to `modified_in` rather than creating duplicate nodes.
> 3. Write `scripts/import_jsonl_to_engine.py` to ingest these streams into our chosen graph database, constructing native relationships between the Git commit nodes and the structural code elements.

#### Task 1.3, 1.4 & 1.5: `BiTemporalAdapter` Implementation & Validation

**Upgraded Prompt:**
> **Context:** We need a unified code access layer that replaces relational SQL queries with graph-native topological lookups.
> **Task:**
> 1. Build `src/storage/bitemporal_adapter.py`. Implement standard search functions (`get_symbols`, `get_calls`, `get_transitive_dependencies`). For version‑aware queries, use a **parameterized path query** that limits traversal depth. For the current branch tip, use an **inverted index** mapping commit SHA → a bitmask of reachable ancestors. For historical SHAs (older than 100 commits back), fall back to a recursive query but cache the result for 1 hour. **Do NOT use wall-clock timestamps or dates.** Use the `introduced_in`/`deleted_in` properties.
> 2. Hook up our golden test suite to validate that lookups match the legacy results exactly. Put this execution pass behind a `USE_BITEMPORAL` runtime environment feature flag in `src/settings.py`.

---

### Phase 2: Cache Layer Integration & Delta Sync (Weeks 10–12)

**Goal:** Establish `codebase-memory-mcp` as an ephemeral, read‑optimized mirror for instant branch navigation.

#### Task 2.1, 2.2, 2.3 & Cold‑start (New Task 2.5)

**Upgraded Prompt:**
> **Context:** We want sub-millisecond lookups for current-state codebase queries by running `codebase-memory-mcp` as a fast memory cache sidecar.
> **Task:**
> 1. Write `src/cache/cdc_listener.py`. If the chosen engine provides a webhook or CDC stream, consume it. If not, fall back to a **poll‑based diff** that runs every 5 seconds, comparing the current branch tip SHA with the cached SHA. On diff, fetch the delta of changed nodes/edges and apply them to the cache. Document which engines support which method.
> 2. Update `src/storage/bitemporal_adapter.py`. When a query requests the *active workspace state*, check the memory cache first. Optimize the visibility lookups by caching the current branch’s commit ancestry list as a bitset or quick‑lookup dictionary, achieving O(1) filtering before falling back to the graph store for deep historical queries.
> 3. **New Task – Cold‑start:** Implement a cold‑start mechanism in `src/cache/cache_bootstrap.py`. On service start, if the cache is empty (no `last_sync` marker), perform a full rebuild from the graph store. During rebuild, serve stale data with a `X-Cache-Status: stale` header and log rebuild progress.

---

### Phase 3: Timeline Travel & Visualization (Weeks 13–17)

**Goal:** Expose DAG‑based navigation options across the command line, web clients, and requirements pipelines.

#### Task 3.1, 3.2 & 3.3: Time‑Travel Operations (CLI, API, UI)

**Prompt:**
> **Context:** We are exposing our topological timeline travel capability out to user-facing interfaces.
> **Task:**
> 1. Modify our Typer CLI codebase under `src/cli/` to accept a `--commit` string argument across all investigative commands (`query`, `impact`, `dead-code`).
> 2. Update our FastAPI endpoints in `src/api/routes.py` to pass an optional `commit_sha` query parameter through to the underlying `BiTemporalAdapter`.
> 3. Update the React application frontend in `ui/`. Integrate a network graph visualization component (such as Sigma.js or Cytoscape.js). When a user picks a different commit from the history rail, trigger an API update to re‑render the exact layout of the codebase as it existed at that specific commit.

---

### Phase 4: Semantic Layer Integration (Weeks 18–21)

**Goal:** Combine structural graph intelligence with vector embeddings via `txtai` for accurate hybrid search.

#### Task 4.1, 4.1a & 4.2: Indexing, Versioning, and Unified Search

**Upgraded Prompt:**
> **Context:** We are adding code search capabilities by combining structural graphs with vector embeddings using `txtai`.
> **Task:**
> 1. Write `src/semantic/indexer.py`. During the ingestion pipeline, extract **only** docstrings, function signatures, and error messages. Skip inline comments (they are often noisy). Generate embeddings using a compact model (like `BAAI/bge-small-en-v1.5`) and store them in a local `txtai` index, tagging each record with its `introduced_in` commit SHA and a reference to the original `DefNode` ID. Implement a **batch re‑indexing** hook that triggers when `modified_in` is updated on a node.
> 2. Build a unified search workflow in `src/semantic/search.py` that merges lexical keyword scores (BM25) with vector similarity distances. Expose this interface as a new `/search` API endpoint and a dedicated `semantic_search` tool on our MCP server.

---

### Phase 5: Production Hardening & Phased Rollout (Weeks 22–25)

**Goal:** Ensure enterprise‑grade resiliency, scale testing, and safe production deployment.

#### Task 5.1, 5.2, 5.3 & New Security/Resiliency Tasks

**Upgraded Prompt:**
> **Context:** We are preparing to launch the Git-DAG architecture into high-traffic production environments.
> **Task:**
> 1. Create an automated workload script (`tests/performance/stress_run.py`) that clones a target repository with a deep commit history (thousands of revisions) to verify how our engine handles deep ancestry graph path traversals.
> 2. Integrate Prometheus metrics hooks throughout `src/storage/bitemporal_adapter.py` and the cache layer. Track cache hit ratios, delta sync delays, graph lookup times, and system error events. Provide a standard Grafana dashboard configuration JSON.
> 3. **New – Security:** Implement API key or JWT‑based authentication for all REST and MCP endpoints. Use the workspace context to enforce that a user can only access repositories they are authorized for.
> 4. **New – Graceful Degradation:** Implement circuit breakers for the graph engine and cache connections. If response times exceed 2 seconds, fall back to a read‑only mode using the last known good cache. Log all fallback events for post‑mortem analysis.

---

### Phase 6: Advanced Platform Capabilities (Weeks 26–29)

**Goal:** Deliver deep cross‑system analysis and integrated workspace tools.

#### Task 6.1, 6.1a & 6.2: Cross‑Repo Linker & Impact Predictor

**Upgraded Prompt:**
> **Context:** We are building advanced, enterprise-grade capabilities over our stable code intelligence platform.
> **Task:**
> 1. Extend our graph database node definition schema to support cross-repository references. Define a `RemoteReference` node type: `(remote:RemoteReference {repo_url: string, ref_sha: string, exposed_interface: string})`. Create `IMPORTS_FROM` edges between local `DefNode`s and `RemoteReference`s. Ensure these remote nodes are not recursively indexed (to avoid infinite loops).
> 2. Write a predictive analysis engine in `src/analytics/predictor.py`. Look back through the historical modification records (`modified_in` lists) across our call graphs to find components that are frequently modified together. Use this structural coupling data to predict and display the potential blast radius of proposed code modifications.

---

## 3. Cross‑Cutting Concerns (Observability & Logging)

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