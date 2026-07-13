# AI Assistant Context

This file provides essential context for AI coding assistants (Cursor, Claude Code, Jules, etc.) working within the `code-intel` repository.

## Project Overview
`code-intel` is a production-ready code intelligence platform. It tracks code structure against a Git DAG using a topological schema, enabling sub-millisecond historical queries and AI-driven analysis.

## Technology Stack
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, tree-sitter.
- **Frontend**: TypeScript, React 18, Vite, Tailwind, Cytoscape.js.
- **Data**: PostgreSQL + `pgvector`, Redis (RQ), Temporal (optional).
- **AI**: Ollama, OpenRouter, Google Gemini.

## Engineering Principles (from Playbook)
1. **Signal Over Noise**: Keep code simple and data-oriented. Avoid "framework bloat".
2. **Bi-Temporal Integrity**: All code facts must be tied to a specific commit/version in the Git-DAG.
3. **Conventional Commits**: All PRs must use conventional commit prefixes (`feat:`, `fix:`, `docs:`, `refactor:`).
4. **Trunk-Based Development**: Favor small, frequent merges over long-lived feature branches.

## Key Directories
- `code_intel/`: Core Python package.
- `ui/`: React frontend.
- `docs/adr/`: Architecture Decision Records.
- `scripts/`: Maintenance and evaluation utilities.

## Testing
- **Backend**: `pytest`
- **Frontend**: (Planned) `playwright`
- **AI**: `promptfoo` (for prompt regression)

Refer to `docs/MATURITY_EVALUATION.md` for our roadmap to world-class engineering status.
