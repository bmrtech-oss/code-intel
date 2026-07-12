# Code-Intel: Strategic Demo Guide

This guide walkthrough the platform's core capabilities using our optimized **Strategic Demo** script.

---

## 🚀 Running the Automated Demo

The fastest way to see Code-Intel in action is to run:

```bash
./demo.sh
```

### What this demo covers:

1. **📥 Source Ingestion**: Indexes the `examples/python` repository, converting code into structured versioned facts.
2. **🔍 Topological Queries**: Runs a `query_call_graph` to map exactly how functions interact.
3. **💥 Impact Prediction**: Calculates the "blast radius" for a change to a core processing method.
4. **🧠 Semantic Search**: Uses natural language to find relevant code (Requires **Standard** or **High** tier).
5. **📈 Co-change Prediction**: Predicts likely "Next Edits" based on historical modification patterns.
6. **📝 Requirement Generation**: Uses an LLM to generate Epics and User Stories directly from the call graph facts.

---

## ⚡ Speeding up the Demo with Cloud LLMs

If you don't want to wait for local Ollama models to download, you can provide a cloud API key directly:

```bash
# Using Google Gemini (FASTEST)
./demo.sh --provider google --google-key AIza...

# Using OpenRouter
./demo.sh --provider openrouter --api-key sk-or-...
```

---

## 🧪 Testing Performance Tiers

You can see how different tiers behave by switching your configuration:

### 1. Minimal Tier (Default)
In this mode, Phase 4 (Semantic Search) will show an error message: *"Semantic search is not available in Lightweight mode."*. This is expected and ensures your system stays fast and light.

### 2. Standard Tier
If you re-install with the **Standard** tier, you can run semantic queries like:
```bash
curl -X GET "http://localhost:8000/search?q=how+to+process+data"
```

---

## 🛠️ Advanced: Manual Exploration

If you have indexed a repository, you can query it via the CLI:

```bash
# List all dead code in the demo version
uv run code-intel query dead_code --commit demo-v1

# Trace a requirement back to its source code
uv run code-intel trace REQUIREMENT_ID
```

For a full API reference, visit `http://localhost:8000/docs` while the server is running.
