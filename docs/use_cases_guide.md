# Code-Intel: Comprehensive Use Cases

## Overview

Code-Intel is a **production-ready, local-first code intelligence platform** that builds a **Knowledge Graph** from your source code and makes it explorable through a Web UI, HTTP API, CLI, and MCP server. It parses **14+ languages** (TypeScript, JavaScript, Python, Java, Go, C, C++, C#, Rust, PHP, Ruby, Swift, Kotlin, Dart) via tree-sitter AST, creating a bi-temporal, Git-DAG-aware fact model that enables sub-millisecond historical queries, impact analysis, and LLM-driven requirements generation.

**Key Differentiators:**

- ✅ **Local-first** — All analysis runs on your machine; no code leaves your workspace.
- ✅ **Privacy-preserving** — No hosted embedding APIs or external code index required.
- ✅ **Bi-temporal fact model** — Track code structure against Git DAG with `introduced_in`, `modified_in`, `deleted_in`.
- ✅ **MCP-native** — First-class Model Context Protocol server for AI agent integration.
- ✅ **Provenance-grounded** — Every LLM-generated artifact cites exact source facts.

---

## Use Case Matrix

| User Role | Primary Use Cases |
| --- | --- |
| **Developer** | Code navigation, semantic search, AI chat, dependency tracing, security scanning, complexity metrics, test coverage analysis |
| **Architect** | Architecture visualization, impact analysis, architectural drift monitoring, circular dependency detection |
| **AI Agent** | Grounded code tools via MCP, auto-generated context files, local-first indexing for agentic workflows |
| **DevOps** | CI/CD integration, large-scale analysis, incremental indexing, SARIF output for security dashboards |
| **Engineering Leadership** | Health scores, dead code detection, complexity hotspots, portfolio-level insights |
| **Legacy Modernization** | Knowledge graph construction, impact analysis, AI-powered comprehension, safe incremental migration |
| **Compliance & Audit** | Traceability from code to requirements, grounded explanations, regulatory-ready documentation |

---

## For Developers

### 1. Understand Unfamiliar Code Faster

Jump into any codebase and immediately see how it's structured.

- **Force-directed Graph Explorer** — Interactive Sigma.js visualization with color-coded node types (functions, classes, files, etc.), hover highlighting, and filters.
- **Source Code Preview** — Click any node to open syntax-highlighted source at the exact line; "Open in editor" (`vscode://`) button for seamless integration.
- **AI-Generated Symbol Summaries** — Optional `--summarize` flag generates 1-2 sentence summaries per symbol via OpenAI, Anthropic, or Ollama; cached by code hash.

**Example Workflow:**

```bash
# Analyze a repository
code-intel analyze /path/to/repo --summarize

# Open the web UI
code-intel serve

# Navigate to any symbol → instantly see where it's defined, where it's called, and what it does
```

### 2. Search for Code Semantically

Find what you need, even if you don't remember the exact name.

- **Hybrid Search (BM25 + Vector RRF)** — Reciprocal Rank Fusion of keyword + semantic search with configurable search modes (`bm25`, `vector`, `hybrid`).
- **Semantic Vector Search** — Embeddings via all-MiniLM-L6-v2; enriched with symbol summaries when available.

**Example:**

```bash
# Search by concept
code-intel search "authentication flow"

# Search by exact symbol
code-intel search "validateUser"
```

### 3. Get Grounded AI Assistance

Ask questions about the code and get answers that cite actual source files.

- **Code AI Chat** — Grounded assistant that cites source files in every answer.
- **Hybrid Search** surfaces relevant context for LLM conversations.
- **Traceability** — Every answer includes references to specific files, lines, and symbols.

### 4. Trace Dependencies and Impact

Understand what breaks when you change something.

- **Blast Radius** — See what depends on a symbol via HTTP API, CLI, and MCP tool.
- **Graph Query Language (GQL)** — Query your codebase with `FIND`, `TRAVERSE`, `PATH`, `COUNT GROUP BY`.
- **Call Paths and Imports** — Trace references, call paths, and imports.

**Example GQL Query:**

```sql
FIND function calculateInterest 
TRAVERSE CALLS DEPTH 3
PATH FROM function calculateInterest TO function auditLog
```

### 5. Catch Issues Before They Ship

Scan for security, quality, and complexity problems.

- **Security & Quality Scanning** — Detects SQL Injection (CWE-89), XSS (CWE-79), SSRF (CWE-918), Path Traversal (CWE-22), Command Injection (CWE-78).
- **Secrets Detection** — Finds hardcoded API keys, DB URLs, RSA keys.
- **Deprecated API Detection** — Finds usages of `@deprecated` JSDoc, `@Deprecated` (Java), `#[deprecated]` (Rust), and built-in Node.js deprecated APIs.
- **SARIF Output** — `--format sarif` for CI integration.

**Example:**

```bash
# Run a security scan
code-intel scan /path/to/repo --output sarif

# Detect secrets
code-intel secrets /path/to/repo

# Get complexity metrics
code-intel complexity --top 20
```

### 6. Measure Test Coverage Gaps

Identify under-tested parts of your codebase.

- **Test Coverage Analysis** — Lists untested exported symbols sorted by blast radius.
- **Threshold Enforcement** — `--threshold <pct>` fails CI if coverage falls below target.
- **CI Integration** — Run in CI pipelines to enforce quality gates.

**Example:**

```bash
code-intel coverage /path/to/repo --threshold 80
```

### 7. Generate AI Context Files

Keep AI assistants in sync with your codebase.

- **Context File Generation** — Auto-generates `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/code-intel.mdc`, and more after every analysis.
- **Always Up-to-Date** — Context files stay current with the codebase.

---

## For Architects and Tech Leads

### 8. Visualize System Architecture

See the big picture of how modules connect.

- **Force-directed Graph Explorer** — Interactive visualization of the entire knowledge graph.
- **Query Console** — Web UI panel with GQL editor, sortable results table, query history, and example queries.
- **Filters** — Hide/show node types, zoom in on specific modules, export graph snapshots.

### 9. Perform Impact Analysis Before Refactoring

Know exactly what will be affected.

- **Blast Radius** — Identify all dependents of a function, class, or file.
- **Impact Analysis** — CLI and MCP tools for PR impact analysis.
- **Call Path Tracing** — Understand how data and control flow through the system.

**Example MCP Tool:**

```
pr_impact(repo_path: "/path/to/repo", commit_sha: "abc123")
→ Returns list of affected files and functions
```

### 10. Monitor Architectural Drift

Catch violations and erosion over time.

- **Circular Dependencies** — Detected via Tarjan's SCC algorithm.
- **Orphan Files** — Files with no incoming dependencies (potential dead code).
- **Health Score** — Aggregate 0–100 score for quick assessment.
- **Dead Code Detection** — Identify code that's no longer used.

### 11. Measure and Improve Code Health

Get data-driven insights into codebase quality.

- **Health Score** — 0–100 aggregate score per repository, updated incrementally.
- **Complexity Hotspots** — Rank functions by cyclomatic + cognitive complexity.
- **Dead Code** — Functions, classes, and files that are never referenced.

---

## For AI Agents and LLM Tooling

### 12. Ground AI Agents with Real Code Context

Give your LLM tools accurate, up-to-date code intelligence.

- **MCP Server** — Model Context Protocol integration with **6 reasoning tools**:
  
  1. `explain_relationship` — Understand connections between symbols
  
  2. `pr_impact` — Analyze what a PR would affect
  
  3. `similar_symbols` — Find semantically related code
  
  4. `health_report` — Get codebase health metrics
  
  5. `suggest_tests` — Recommend tests for untested code
  
  6. `cluster_summary` — Summarize groups of similar code
  
- **MCP tool-chaining hints** and pagination for complex workflows.
  
- **10+ built-in prompt examples** for agentic workflows.
  

**Example Agentic Workflow:**

```
AI Agent: "What's the blast radius of changing calculateInterest()?"

→ MCP Tool: blast_radius(symbol: "calculateInterest")
→ Returns list of all files, functions, and tests that depend on it
→ AI Agent summarizes findings
```

### 13. Auto-Generate AI Context Files

Keep AI assistants in sync with your codebase.

- **Context File Generation** — Auto-generates `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/code-intel.mdc`, and more after every analysis.
- **Always Up-to-Date** — Context files stay current with the codebase.

### 14. Local-First, Privacy-Preserving Code Intelligence

No code leaves your workspace.

- **Local-first indexing** — Indexes a workspace into a local graph and vector store.
- **No hosted embedding API** — All embeddings are generated locally.
- **No hosted code index** — No external data files required beyond the workspace and index path.
- **No external dependencies** — Runs entirely on your infrastructure.

---

## For DevOps and Platform Engineers

### 15. CI/CD Integration

Automate code quality gates.

- **SARIF Output** — `--format sarif` for integration with security and quality dashboards.
- **Test Coverage Threshold** — `--threshold <pct>` fails CI if coverage is below target.
- **CLI** — All functionality available via command line for scripting.

**Example CI Pipeline Integration:**

```yaml
# .gitlab-ci.yml
code-quality:
  script:
    - code-intel scan /code --format sarif > gl-sast-report.json
    - code-intel coverage /code --threshold 80
  artifacts:
    paths:
      - gl-sast-report.json
```

### 16. Large-Scale Repository Analysis

Handle big codebases efficiently.

- **Incremental Analysis** — `--incremental` flag re-parses only git-changed/mtime-changed files; 10k-file repo with 3 changes completes in **288ms**.
- **Parallel Analysis** — `--parallel` flag runs parse + resolve phases on worker threads for large repos.
- **File Watcher & Auto-Reindex** — `code-intel watch` detects file saves and patches the live graph within **~1 second**; WebSocket push notifies connected clients.
- **Bi-temporal fact model** — Tracks code structure across Git DAG; bitset-based visibility for O(1) ancestry filtering.

### 17. Deployment Flexibility

Run anywhere — from local machine to enterprise data center.

- **Docker/Podman** — Containerized deployment with `docker-compose.yml`.
- **Local CLI** — Run directly on any machine with Python 3.12+.
- **MCP Server** — For integration with Claude Code, Cursor, and other AI agents.
- **HTTP API** — RESTful API for custom integrations.

---

## For Product and Engineering Leadership

### 18. Executive Dashboard

Quickly assess the health of your engineering portfolio.

- **Health Score** — 0–100 aggregate score per repository.
- **Dead Code Detection** — Identify code that's no longer used.
- **Complexity Hotspots** — Find the most complex functions that need refactoring.
- **Trends Over Time** — Track code health changes across sprints.

### 19. Portfolio-Level Insights

Compare multiple repositories.

- **Repository Health Dashboard** — Web UI with sortable columns for health score, dead code %, circular deps, and test coverage.
- **CI Integration** — Check health status before approving PRs.

---

## For Legacy Modernization Teams

### 20. Knowledge Graph Construction for Legacy Systems

Create a map of systems that have evolved over decades.

- **Language Support** — 14+ languages including Python, Java, Go, C++, Rust, and more.
- **COBOL Extension** — `cobol-intel` sibling project specifically for COBOL mainframe codebases (banking, fintech, regulated industries).
- **Node Types** — Programs, sections, paragraphs, copybooks for COBOL; functions, classes, files for modern languages.
- **Edge Types** — Calls, performs, imports, extends, data flow.

### 21. Impact Analysis for Safe Modernization

Know exactly what breaks when you change a legacy module.

- **Blast Radius** — Identify all dependents of any legacy symbol.
- **Call Path Tracing** — Understand how data and control flow through the system.
- **Dead Code Detection** — Identify code that is never invoked and can be safely removed.
- **Circular Dependency Detection** — Uncover tangled relationships that make the system hard to change.

### 22. AI-Powered Code Comprehension

Understand legacy code without original documentation.

- **AI-generated symbol summaries** — One- to two-sentence explanations of what each program, function, or class does.
- **Grounded AI Chat** — Ask questions about the codebase and get answers that cite actual source files.
- **Requirements Generation** — Automatically generate structured requirements from code analysis.
- **Traceability** — Every LLM-generated artifact includes `grounded_in` fact IDs, creating an audit trail.

**Example Legacy Workflow:**

```bash
# Analyze a COBOL codebase (via cobol-intel)
cobol-intel analyze /path/to/cobol/codebase --summarize

# Ask: "What does program PAYROLL-001 do?"
# Response: Covers payroll calculation, tax withholding, and employee record updates
# Citations: PAYROLL-001 (lines 12-345), TAX-CALC (copybook), EMPLOYEE-FILE (data definition)

# Impact analysis: "What depends on TAX-CALC?"
# Response: 14 programs directly call TAX-CALC
# Blast radius: 3 of those programs are in critical path; 11 are safe to modify
```

### 23. Business Rule Extraction

Isolate core business logic from infrastructure code.

- **Data Flow Tracing** — Follow data through the system to identify business logic entry points.
- **Call Path Clustering** — Group code by functional area (e.g., "customer onboarding," "payment processing").
- **Dead Code Isolation** — Remove non-executed code to simplify understanding.
- **Cluster Summaries** — MCP tool `cluster_summary` provides high-level overviews of functional groups.

### 24. Compliance and Audit Readiness

Generate audit-ready documentation.

- **Traceability** — From code to requirements via `grounded_in` fact IDs.
- **Documentation Generation** — Auto-generate symbol summaries and call graphs.
- **Impact Analysis Reports** — Document what depends on what for change management reviews.
- **Health Reports** — Quantitative baseline for modernization progress tracking.

---

## Getting Started

```bash
# Install
curl -sSL https://raw.githubusercontent.com/bmrtech-oss/code-intel/main/install.sh | bash

# Analyze a repository
code-intel analyze /path/to/your/repo

# Start the web UI
code-intel serve

# Search semantically
code-intel search "authentication flow"

# Run a health check
code-intel health

# Generate AI context files
code-intel context /path/to/your/repo

# Start the MCP server for AI agents
code-intel mcp
```

---

## Summary

Code-Intel transforms how engineering teams understand, evolve, and modernize code. Whether you're a developer exploring a new codebase, an architect planning a refactor, an AI agent needing grounded code context, or a legacy modernization team planning a safe migration, Code-Intel provides the intelligence you need—**locally, privately, and at scale**.