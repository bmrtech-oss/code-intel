# Code-Intel Engineering Maturity Evaluation

This document evaluates the `code-intel` repository against the [AI Development Playbook](https://github.com/bmrtech-oss/ai-development-playbook) and outlines a prioritized plan to reach "World-Class" engineering status.

## Gap Analysis

| Category | Playbook Requirement | Current Status (code-intel) | Gap |
| :--- | :--- | :--- | :--- |
| **Governance** | ADRs for all major decisions | High-level design docs exist, but no formal ADR process. | No `docs/adr/` directory. |
| **AI Context** | `AGENTS.md` for assistant guidance | `agent-integrations.md` exists, but no standard root `AGENTS.md`. | Missing root `AGENTS.md`. |
| **Workflow** | Conventional Commits & Trunk-based dev | Mentioned in docs but not enforced. | No linting for commit messages. |
| **Testing** | E2E with Playwright | Backend tests (pytest) only. | No frontend E2E tests. |
| **AI Quality** | Prompt evaluation (e.g., `promptfoo`) | Prompts are static files. | No regression testing for prompts. |
| **Security** | Automated security scanning in CI | CI handles linting and unit tests. | No static analysis for security (SAST). |
| **Ops** | RAG/Graph hygiene dashboards | Functional, but no operational runbooks. | Missing maintenance docs. |

## prioritized Enhancement Plan

### Phase 1: Foundation & Governance (Medium Impact, Low Effort)
*Goal: Align with industry-standard communication and decision-making patterns.*

1.  **Initialize ADRs**: Create `docs/adr/0001-unified-data-plane.md` to formalize the core architecture.
2.  **Add `AGENTS.md`**: Provide clear context for AI coding assistants (Cursor, Claude Code, Jules).
3.  **Strengthen `CONTRIBUTING.md`**: Formally adopt Conventional Commits and reference Playbook guidelines.

### Phase 2: Quality & Security (High Impact, Medium Effort)
*Goal: Automate safety and correctness.*

1.  **Security CI**: Add `semgrep` or `bandit` to `.github/workflows/ci.yml`.
2.  **Prompt Evaluation**: Integrate `promptfoo` to test `prompts/requirement_generation.txt`.
3.  **UI E2E Shell**: Setup Playwright in `ui/` to verify critical user journeys (e.g., Ingestion Flow).

### Phase 3: Observability & Autonomics (High Impact, High Effort)
*Goal: Reach the "Self-Healing" tier of the playbook.*

1.  **RAG/Graph Runbook**: Create `docs/operations/graph-hygiene.md`.
2.  **Feature Flags**: Implement a simple, standard feature flag utility in `code_intel.core.settings`.

---
*Status: Evaluation Complete. Implementation Phase 1 underway.*
