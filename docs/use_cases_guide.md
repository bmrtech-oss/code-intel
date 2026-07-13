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

## 5. High-Performance Analysis for Monorepos

Use Code-Intel to analyze massive codebases where traditional graph traversals fail.

- Leverage the **Optimized Read Model** (flattened graph index) for sub-millisecond recursive queries.
- Scale to monorepos with hundreds of thousands of commits and millions of LOC without performance degradation.
- Benefit from **Incremental Invalidation** that only re-computes stale parts of the analysis when files change.

## 6. Verifiable AI Requirements Generation

Use Code-Intel to generate documentation and requirements that can be audited for accuracy.

- Generate requirements that are **verifiably grounded** in specific source code facts.
- Inspect the **grounding provenance** for any AI-generated claim to see which symbols and calls it was based on.
- Identify and flag **hallucinations** automatically via built-in validation passes.

## 7. Repository Health and Cleanup

Use Code-Intel to identify maintenance opportunities.

- Detect dead code and unused functions.
- Review dependency hotspots and risky areas.
- Generate follow-up work items from the structured analysis output.
