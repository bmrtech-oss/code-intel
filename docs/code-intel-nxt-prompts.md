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
> 2. Build an asynchronous MCP (Model Context Protocol) server in `src.mcp.server.py` using the python `mcp` SDK. Expose 5 core tools: `query_call_graph`, `query_dead_code`, `generate_requirements`, `query_impact`, and `semantic_search`. **Crucial design constraint:** Every tool definition must accept an optional `commit_sha: str` input parameter. If this parameter is omitted by the AI client, default automatically to the active workspace SHA retrieved from Redis.
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
> 1. Complete the tool execution layers in `src.mcp.server.py` to connect seamlessly with the workspace storage layer. Add `get_workspace_info` to read current Git states.
> 2. Initialize a clean frontend application in `ui/`. Build a responsive three-panel interface layout (Left: File tree & Git history branch selector, Center: Interactive graph rendering view, Right: Interactive MCP Chat panel).
> 3. Create a `.mcp.json` configuration manifest that exposes this local server directly to tooling like Claude Code, allowing it to invoke our workspace analysis tools.
> 
> 

---

### Phase 1: Storage Migration to Git-DAG Engine [COMPLETED]

Tasks 1.1 through 1.5 are fully implemented. Relational facts are migrated to topological JSONL, and the `BiTemporalAdapter` provides ancestry-based visibility.

---

### Phase 2: Cache Layer Integration & Delta Sync [COMPLETED]

Tasks 2.1 through 2.5 are fully implemented. `MemoryCache` provides sub-millisecond lookups, synchronized via `CDCListener` and initialized via `CacheBootstrap`.

---

### Phase 3: Timeline Travel & Visualization [COMPLETED]

Tasks 3.1 through 3.3 are fully implemented. CLI, API, and UI all support native timeline travel between commit SHAs.

---

### Phase 4: Semantic Layer Integration [COMPLETED]

Tasks 4.1 and 4.2 are fully implemented. `txtai` with `BAAI/bge-small-en-v1.5` powers hybrid semantic search across the platform.
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