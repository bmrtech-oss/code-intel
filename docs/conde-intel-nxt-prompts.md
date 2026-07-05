### Phase 0: Foundation & Topological Assessment

#### Prompt for Task 0.1 & 0.2: Language Handlers & Golden Test Suite

> **Context:** We are building `code-intel`, a next-gen code intelligence platform. We track code structure directly against a Git Directed Acyclic Graph (DAG) using a topological schema rather than database timestamps.
> **Task:**
> 1. Create Tree-sitter AST handlers for Python, TypeScript, and Go (`src/lang/python_handler.py`, `ts_handler.py`, `go_handler.py`). They must extract structural identities: fully qualified names for modules, classes, functions, and call actions. Add an explicit pass or stub for tracking cross-file dynamic method invocations.
> 2. Build a small multi-language code fixture workspace inside `tests/golden/` that simulates a common real-world architecture (e.g., an API handler calling a repository layer). Include explicit instances of dead functions and deep call chains to test parsing accuracy.
> 
> 

#### Prompt for Task 0.3 & 0.4: Git-DAG Workspace & Git-Aware MCP Server

> **Context:** We need a session layer that maps user environment lookups to specific points in a project's repository history.
> **Task:**
> 1. Write `src/core/workspace.py`. Implement a Redis-backed session manager that stores and maintains active workspace sessions. Instead of just saving a flat workspace ID, it must actively store: `current_branch`, the active `current_sha`, and a cached, ordered list of all ancestor commit SHAs leading up to that point.
> 2. Build an asynchronous MCP (Model Context Protocol) server in `src/mcp_server.py` using the python `mcp` SDK. Expose 5 core tools: `query_call_graph`, `query_dead_code`, `generate_requirements`, `query_impact`, and `semantic_search`. **Crucial design constraint:** Every tool definition must accept an optional `commit_sha: str` input parameter. If this parameter is omitted by the AI client, default automatically to the active workspace SHA retrieved from Redis.
> 
> 

#### Prompt for Task 0.5 & 0.6: Engine Evaluation Script

> **Context:** We are choosing our core bi-temporal graph storage system. We are evaluating Memtrace and TerminusDB.
> **Task:** Write a Python profiling script (`scripts/evaluate_graph_engines.py`) that spins up containers for both engines, populates them with our mock Git-DAG commit nodes, and benchmarks query performance. The benchmark must test a topological lookback query: given a target commit SHA, fetch its historical ancestor SHAs, and then filter code edges where `edge.introduced_in` is part of that ancestry list. Generate a markdown comparison table displaying query latencies for both engines.

---

### Phase 0.5: Initial MCP & UI Foundations

#### Prompt for Task 0.5.1, 0.5.2 & 0.5.3: Tool Extension & UI Wireframe

> **Context:** Our core MCP tools need full analytical logic, and we need a lightweight visual interface to switch between repository states.
> **Task:**
> 1. Complete the tool execution layers in `src/mcp_server.py` to connect seamlessly with the workspace storage layer. Add `get_workspace_info` to read current Git states.
> 2. Initialize a clean frontend application in `ui/`. Build a responsive three-panel interface layout (Left: File tree & Git history branch selector, Center: Interactive graph rendering view, Right: Interactive MCP Chat panel).
> 3. Create a `.mcp.json` configuration manifest that exposes this local server directly to tooling like Claude Code, allowing it to invoke our workspace analysis tools.
> 
> 

---

### Phase 1: Storage Migration to Git-DAG Engine

#### Prompt for Task 1.1 & 1.2: Topological Exporter & Transaction Importer

> **Context:** We are deprecating our old PostgreSQL database schema to move entirely to our new topological graph database model.
> **Task:**
> 1. Write `scripts/export_postgres_to_jsonl.py`. Read rows from the legacy PostgreSQL `facts`, `symbols`, and `calls` tables. Flatten and map them into three specific JSON Lines output targets: `commits.jsonl` (mapping SHAs and parent dependencies), `nodes.jsonl` (capturing structural identities with `introduced_in`), and `edges.jsonl` (capturing call networks with `introduced_in` and `deleted_in`).
> 2. Write `scripts/import_jsonl_to_engine.py` to ingest these streams into our chosen graph database, constructing native relationships between the Git commit nodes and the structural code elements.
> 
> 

#### Prompt for Task 1.3, 1.4 & 1.5: `BiTemporalAdapter` Implementation

> **Context:** We need a unified code access layer that replaces relational SQL queries with graph-native topological lookups.
> **Task:**
> 1. Build `src/storage/bitemporal_adapter.py`. Implement standard search functions (`get_symbols`, `get_calls`, `get_transitive_dependencies`). Do NOT use wall-clock timestamps or dates. Use a graph path lookup query that traces the target commit's ancestry tree: `MATCH (t:Commit {sha: $sha})-[:PARENT_OF*0..]->(a:Commit)` and filters code elements where `edge.introduced_in` matches a valid ancestor SHA and `edge.deleted_in` is either null or not in that ancestry.
> 2. Hook up our golden test suite to validate that lookups match the legacy results exactly. Put this execution pass behind a `USE_BITEMPORAL` runtime environment feature flag in `src/settings.py`.
> 
> 

---

### Phase 2: Cache Layer Integration & Delta Sync

#### Prompt for Task 2.1, 2.2 & 2.3: Cache Sync & Ancestor Fallback Logic

> **Context:** We want sub-millisecond lookups for current-state codebase queries by running `codebase-memory-mcp` as a fast memory cache sidecar.
> **Task:**
> 1. Write `src/cache/cdc_listener.py`. Establish an event listener that hooks into the graph engine's transaction logs or webhooks. When a new Git commit is processed, extract only the structural delta changes (newly introduced or deleted nodes/edges) and apply them directly to the in-memory cache layer.
> 2. Update `src/storage/bitemporal_adapter.py`. When a query requests the *active workspace state*, check the memory cache first. Optimize the visibility lookups by caching the current branch’s commit ancestry list as a bitset or quick-lookup dictionary, achieving O(1) filtering before falling back to the graph store for deep historical queries.
> 
> 

---

### Phase 3: Timeline Travel & Visualization

#### Prompt for Task 3.1, 3.2 & 3.3: Time-Travel Operations (CLI, API, UI)

> **Context:** We are exposing our topological timeline travel capability out to user-facing interfaces.
> **Task:**
> 1. Modify our Typer CLI codebase under `src/cli/` to accept a `--commit` string argument across all investigative commands (`query`, `impact`, `dead-code`).
> 2. Update our FastAPI endpoints in `src/api/routes.py` to pass an optional `commit_sha` query parameter through to the underlying `BiTemporalAdapter`.
> 3. Update the React application frontend in `ui/`. Integrate a network graph visualization component (such as Sigma.js or Cytoscape.js). When a user picks a different commit from the history rail, trigger an API update to re-render the exact layout of the codebase as it existed at that specific commit.
> 
> 

---

### Phase 4: Semantic Layer Integration

#### Prompt for Task 4.1 & 4.2: Hybrid Ingestion and Search API

> **Context:** We are adding code search capabilities by combining structural graphs with vector embeddings using `txtai`.
> **Task:**
> 1. Write `src/semantic/indexer.py`. During the ingestion pipeline, extract function headers, variable scopes, documentation, and inline comments. Generate embeddings using a compact model (like `BAAI/bge-small-en-v1.5`) and store them in a local `txtai` index, tagging each record with its unique structural ID.
> 2. Build a unified search workflow in `src/semantic/search.py` that merges lexical keyword scores (BM25) with vector similarity distances. Expose this interface as a new `/search` API endpoint and a dedicated `semantic_search` tool on our MCP server.
> 
> 

---

### Phase 5: Production Hardening & Phased Rollout

#### Prompt for Task 5.1, 5.2 & 5.3: Stress Testing and Production Metrics

> **Context:** We are preparing to launch the Git-DAG architecture into high-traffic production environments.
> **Task:**
> 1. Create an automated workload script (`tests/performance/stress_run.py`) that clones a target repository with a deep commit history (thousands of revisions) to verify how our engine handles deep ancestry graph path traversals.
> 2. Integrate Prometheus metrics hooks throughout `src/storage/bitemporal_adapter.py` and the cache layer. Track cache hit ratios, delta sync delays, graph lookup times, and system error events. Provide a standard Grafana dashboard dashboard configuration JSON.
> 
> 

---

### Phase 6: Advanced Platform Capabilities

#### Prompt for Task 6.1 & 6.2: Multi-Repository Linker & Impact Predictor

> **Context:** We are building advanced, enterprise-grade capabilities over our stable code intelligence platform.
> **Task:**
> 1. Extend our graph database node definition schema to support cross-repository references. If an internal microservice references an external library or API interface tracked in another repository, create a cross-repo edge linking the two distinct code graph definitions.
> 2. Write a predictive analysis engine in `src/analytics/predictor.py`. Look back through the historical modification records (`modified_in` lists) across our call graphs to find components that are frequently modified together. Use this structural coupling data to predict and display the potential blast radius of proposed code modifications.
> 
>