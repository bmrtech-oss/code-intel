# ADR 001: Unified Data Plane Architecture

## Status
Accepted

## Context
Code-Intel needs to store and query code structure (symbols, calls, data flows) across thousands of repository versions (commits). Traditional relational schemas or pure graph databases often struggle with either the bi-temporal nature of Git or the scale of cross-version analysis.

## Decision
We adopt a **Unified Data Plane** based on a topological Git-DAG schema.

1. **Relational Fact Store**: Use PostgreSQL (with pgvector) as the source of truth for "Facts" (symbols, edges).
2. **Topological Visibility**: Every fact is tagged with `introduced_in`, `modified_in`, and `deleted_in`.
3. **Write Model vs. Read Model**:
   - Write Model: Append-only relational facts.
   - Read Model: Optimized graph index for fast traversal.
4. **O(1) commit ancestry filtering**: Using bitset-based visibility logic to filter facts based on the Git DAG.

## Consequences
- **Positive**: Extremely fast historical queries; native support for branches/merges; consistent data model for AI and static analysis.
- **Negative**: Higher storage overhead due to versioned records; complexity in maintaining the read-model sync.
