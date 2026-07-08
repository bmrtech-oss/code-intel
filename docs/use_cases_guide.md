# Code-Intel Use Cases Guide

This guide highlights the main scenarios where Code-Intel adds value, from codebase modernization to historical analysis and AI-assisted development.

## 1. Legacy Modernization

Use Code-Intel when you need to understand a legacy system before refactoring it.

- Parse the existing codebase into structured facts.
- Generate requirements from the current implementation rather than from tribal knowledge.
- Trace generated requirements back to the originating symbols for review.

Typical workflow:
1. Ingest the legacy repository.
2. Run requirements generation for the current version.
3. Review the generated epics, features, and stories with traceability links.

## 2. Impact Analysis for Change Planning

Use Code-Intel to estimate the blast radius of a change before making it.

- Query the call graph for a target symbol.
- Inspect transitive dependencies and historical visibility.
- Prioritize review and testing for the most affected areas.

## 3. Historical Code Exploration

Use Code-Intel when you need to understand how a subsystem evolved over time.

- Select a commit SHA or version.
- Inspect the state of the code at that point in history.
- Compare current and historical dependency structures.

## 4. AI-Assisted Development

Use Code-Intel as a grounding layer for MCP-enabled AI assistants.

- Ask for impact analysis, dead code detection, or requirements generation.
- Keep the assistant anchored to repository facts rather than raw source text alone.
- Reuse the same versioned state across CLI, API, and MCP workflows.

## 5. Repository Health and Cleanup

Use Code-Intel to identify maintenance opportunities.

- Detect dead code and unused functions.
- Review dependency hotspots and risky areas.
- Generate follow-up work items from the structured analysis output.
