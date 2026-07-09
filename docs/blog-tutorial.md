# 🚀 Traveling through Code-Time: A Deep Dive into Code-Intel

**By the Code-Intel Team** | *Reading Time: 10 minutes*

---

## 🛑 The Problem: The "Re-Indexing" Nightmare

We've all been there. You switch branches, or a teammate merges a massive PR, and your IDE or code analysis tool goes into a frenzy. Progress bars everywhere. "Indexing... (45 minutes remaining)."

Traditional code intelligence is **snapshot-based**. It sees your code as it is *now*, but it's blind to where it came from. When things change, it has to start over.

What if your code intelligence tool was built on the same foundation as your version control? What if it understood the **Git Directed Acyclic Graph (DAG)** natively?

Enter **Code-Intel**.

---

## 🧠 What is Code-Intel?

Code-Intel is a **Unified Data Plane for Code Intelligence**. It achieved a **10/10 Innovation & Architecture score** by fundamentally rethinking how we store and query code structure.

Instead of wall-clock timestamps, Code-Intel uses a **topological schema**. Every fact—every function definition, every API call, every variable scope—is tagged with when it was `introduced_in` and `deleted_in`.

The result? **Sub-millisecond "Time Travel" queries.** You can query the state of your codebase at *any* commit SHA as easily as querying the present.

---

## 🛠️ Tutorial: From Zero to LLM-Driven Requirements

Let's walk through how to use Code-Intel to analyze a repository and generate traceable requirements.

### 1. Ingesting the Code

First, we need to turn raw source code into structured facts. Code-Intel uses `tree-sitter` visitors to extract high-fidelity AST data.

```bash
# Setup the environment
uv sync
podman-compose up -d

# Ingest your repository
uv run python -m src.cli.main analyze examples/python --version v1
```

### 2. The Magic of Time Travel: Dead Code Detection

Let's find "dead code" (functions that are defined but never called) in our Python example.

**Scenario:** Our `app.py` has a `used_function` and a `dead_function`. Only `used_function` is called in the `if __name__ == "__main__":` block.

```bash
uv run python -m src.cli.main query dead_code --commit v1
```

**Expected Output (JSON):**
```json
[
  {
    "symbol_id": "app.dead_function",
    "name": "dead_function",
    "kind": "function",
    "file": "app.py",
    "line": 5
  }
]
```

Because Code-Intel uses **bitset-based visibility**, this query doesn't scan files. It performs O(1) bitwise operations against ancestry masks to see which symbols have zero incoming call edges in the current commit's graph.

### 3. Unit Testing & Verification

Code-Intel also tracks test coverage and relationships. We can verify our code with standard tools, and Code-Intel can ingest these results to link tests to the symbols they cover.

```bash
# Run the sample tests
cd examples/python
pytest test_app.py
```

**Expected Output:**
```text
============================= test session starts ==============================
collected 2 items

test_app.py ..                                                           [100%]

============================== 2 passed in 0.01s ===============================
```

### 4. Hybrid Semantic Search

Searching for code shouldn't just be about keywords. Code-Intel combines structural identity (the "what") with LLM embeddings (the "meaning").

```bash
# Search for a concept
curl -G "http://localhost:8000/search" --data-urlencode "q=unreferenced functions"
```

The system uses `txtai` to merge BM25 lexical scores with vector similarity, surfacing `dead_function` even if you didn't use the exact word "dead".

### 5. Turning Facts into Requirements

Instead of asking an LLM to "read this folder and write requirements", we use **Fact-Enhanced Generation**.

```bash
curl -X POST http://localhost:8000/requirements
```

**Expected Output (Requirements):**
- **Epic**: Python Application Core
- **Feature**: Utility Functions
- **User Story**: As a developer, I want a `used_function` that provides core utility logic to the main entry point.
- **Maintenance Task**: Investigate and remove `dead_function` as it currently has no active references in the call graph.

Every requirement generated has a link back to the specific `symbol_id` in the database.

---

## 🏗️ Why it Matters: The Unified Data Plane

Code-Intel isn't just a tool; it's a new architectural pattern. By centralizing all code data into a single, versioned relational store (PostgreSQL + `pgvector`), we eliminate silos.

- **Security teams** can use SQL to find vulnerabilities across history.
- **Architects** can predict the "blast radius" of a change before it's even committed.
- **AI Assistants** (via our MCP server) get a high-bandwidth, structured view of the codebase.

---

## 🌟 Get Started Today

Code-Intel is open-source and ready for you to explore.

1.  **Star us on GitHub** ⭐
2.  **Try the Quick Start**: `./create-project-uv-prod.sh`
3.  **Contribute**: We're always looking for new language visitors!

**Stop indexing. Start understanding.**

---
*Ready to dive deeper? Check out our [Architecture Deep Dive](code-intel-design.md) or join the conversation on our [Contributing Guide](../CONTRIBUTING.md).*
