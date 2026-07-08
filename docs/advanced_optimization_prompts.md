# Advanced Optimization Prompts (The Final 0.5)

These prompts are designed to be used with an AI assistant to implement the remaining high-scale optimizations and enterprise features for the Code-Intel platform.

---

### 1. High-Performance "True Delta" Calculation
**Goal**: Optimize Graph Engine to Cache synchronization.
**Prompt**:
> **Context**: We want to optimize the synchronization between our Graph Engine and the Memory Cache. Currently, `get_delta` returns the full visibility set, which is inefficient.
> **Task**:
> 1. Refactor `SimpleGraphEngine.get_delta` in `src/storage/graph_engine.py` to calculate the symmetric difference (XOR) between the ancestry sets of `from_sha` and `to_sha`.
> 2. `Delta_Nodes = {n | n.introduced_in \in (Ancestry_To - Ancestry_From) OR n.deleted_in \in (Ancestry_To - Ancestry_From)}`.
> 3. Update `MemoryCache.apply_delta` in `src/cache/memory_cache.py` to use this delta for in-place updates instead of full list replacement.

---

### 2. Multi-Repo Parser Extension (TypeScript & Go)
**Goal**: Enable cross-repository dependency tracking.
**Prompt**:
> **Context**: We need to track dependencies across microservices.
> **Task**:
> 1. Update `src/lang/ts_handler.py` and `src/lang/go_handler.py` to detect non-local imports.
> 2. In TypeScript, identify imports not starting with `./` or `../`. In Go, identify non-standard library imports.
> 3. Emit `cross_repo_import` facts: `await self.storage.insert_fact("cross_repo_import", f"{caller}->{module_name}", "module", module_name, self.version)`.
> 4. Ensure these are correctly mapped to `IMPORTS_FROM` edges in the topological exporter.

---

### 3. Bitset-Based Ancestry Optimization
**Goal**: Sub-millisecond visibility checks at massive scale (>10k commits).
**Prompt**:
> **Context**: String-based ancestry sets become slow for very large repositories.
> **Task**:
> 1. Refactor `src/storage/graph_engine.py` to map every commit SHA to a unique integer bit index.
> 2. Represent commit ancestry as a large integer bitmask.
> 3. Refactor visibility filtering to use bitwise AND operations: `(node.introduced_bit & target_ancestry_mask) != 0 AND (node.deleted_bit & target_ancestry_mask) == 0`.
