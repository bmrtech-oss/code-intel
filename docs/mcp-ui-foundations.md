# MCP and UI Foundations

This document captures the current Phase 0.5 foundation work for the local MCP server and the lightweight web UI.

## What is included

- A Git-aware MCP server entrypoint in [src.cli.main mcp.py](../src.cli.main mcp.py)
- A `get_workspace_info` tool that reads the active workspace session and Git state
- A three-panel UI shell in [ui/src/App.tsx](../ui/src/App.tsx) with **Cytoscape.js** graph visualization.
- **Timeline Travel**: A history rail for instant navigation between commit SHAs.
- Zustand-backed workspace state in [ui/src/store/workspaceStore.ts](../ui/src/store/workspaceStore.ts).
- A local MCP manifest in [.mcp.json](../.mcp.json) for Claude Code and other MCP-compatible tools

## Run the MCP server

```bash
uv run python -m src.cli.main mcp
```

The server exposes tools such as `query_call_graph`, `query_dead_code`, `query_impact`, `semantic_search`, and `get_workspace_info`.

## Run the UI locally

```bash
cd ui
npm install
npm run dev
```

Then open http://localhost:5173 to view the three-panel layout:

- Left: history and branch selection
- Center: interactive graph explorer (Cytoscape.js)
- Right: MCP chat surface

## Configure MCP tooling

The repository includes a local [.mcp.json](../.mcp.json) manifest that points to the MCP server entrypoint. This allows tools such as Claude Code to invoke the workspace analysis tools directly.

## Notes

The current UI is a foundation-level wireframe. It is intended to evolve into a richer interactive graph workspace as the Git-DAG and storage layers mature.
