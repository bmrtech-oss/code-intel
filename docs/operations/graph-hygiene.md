# Graph Hygiene & Maintenance Runbook

## Overview
As a bi-temporal system, Code-Intel accumulates "Facts" over time. To maintain "World-Class" performance, regular hygiene is required.

## 1. Monitoring Node/Edge Bloat
Query the total count of facts and graph nodes regularly:
```sql
SELECT count(*) FROM facts;
SELECT count(*) FROM graph_nodes;
```

## 2. Orphaned Symbols
Identify symbols that are marked as `deleted_in` across all active branches but still exist in the relational store.
```sql
-- Placeholder for cleanup script
-- uv run python scripts/cleanup_orphans.py
```

## 3. Vector Index Rebuilding (pgvector)
If semantic search latency exceeds 200ms, rebuild the IVFFlat or HNSW index:
```sql
REINDEX INDEX fact_embeddings_idx;
```

## 4. Cache Eviction (Redis)
The `WorkspaceManager` uses Redis for the Git-DAG cache. In case of memory pressure:
```bash
redis-cli FLUSHDB
# This will force a re-load from the relational store on the next request.
```

## 5. RAG Signal-to-Noise Ratio
Evaluate the quality of retrieved facts using `promptfoo` and the `docs/slm_evaluation_harness.md`.
