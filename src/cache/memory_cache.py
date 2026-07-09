import logging
from typing import Dict, List, Any, Optional, Set
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Prometheus Metrics
CACHE_QUERY_TOTAL = Counter('cache_queries_total', 'Total number of cache queries', ['method'])

class MemoryCache:
    """
    High-performance in-memory cache for the current state of the codebase.
    Optimized for sub-millisecond lookups using set-based ancestry filtering.
    """
    def __init__(self):
        self.active_sha: Optional[str] = None
        self.symbols: List[Dict[str, Any]] = []
        self.calls: List[Dict[str, Any]] = []
        self.ancestry_set: Set[str] = set()
        self.last_sync_marker: Optional[str] = None

    async def get_active_sha(self) -> Optional[str]:
        return self.active_sha

    async def get_last_sync_marker(self) -> Optional[str]:
        return self.last_sync_marker

    async def populate(self, symbols: List[Dict[str, Any]], calls: List[Dict[str, Any]], sha: str, ancestry: List[str]):
        self.symbols = symbols
        self.calls = calls
        self.active_sha = sha
        self.ancestry_set = set(ancestry)
        self.last_sync_marker = sha
        logger.info(f"Cache populated for SHA {sha} with {len(symbols)} symbols and {len(calls)} calls.")

    async def apply_delta(self, delta: Dict[str, Any], new_sha: str):
        """
        Applies a True Delta (XOR) to the cache.
        """
        added_nodes = delta.get("added_nodes", [])
        removed_nodes = delta.get("removed_nodes", [])
        added_edges = delta.get("added_edges", [])
        removed_edges = delta.get("removed_edges", [])
        new_ancestry = delta.get("new_ancestry", [])

        # Incremental Node Update
        if removed_nodes:
            removed_ids = {n["id"] for n in removed_nodes if "id" in n}
            self.symbols = [n for n in self.symbols if n.get("id") not in removed_ids]
        
        self.symbols.extend(added_nodes)

        # Incremental Edge Update
        def edge_key(e):
            return (e.get("from"), e.get("to"), e.get("type"))

        if removed_edges:
            removed_keys = {edge_key(e) for e in removed_edges}
            self.calls = [e for e in self.calls if edge_key(e) not in removed_keys]
        
        self.calls.extend(added_edges)

        self.active_sha = new_sha
        self.ancestry_set = set(new_ancestry)
        self.last_sync_marker = new_sha
        
        logger.info(f"Cache delta applied for {new_sha}: +{len(added_nodes)}/-{len(removed_nodes)} nodes, +{len(added_edges)}/-{len(removed_edges)} edges.")

    async def get_symbols(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        CACHE_QUERY_TOTAL.labels(method='get_symbols').inc()
        # O(1) visibility check using pre-filtered active state
        # In a full implementation, the cache would only store nodes visible in the current ancestry.
        results = []
        for s in self.symbols:
            if s.get("introduced_in") in self.ancestry_set:
                deleted_in = s.get("deleted_in")
                if deleted_in is None or deleted_in not in self.ancestry_set:
                    match = True
                    if filters:
                        for k, v in filters.items():
                            if s.get(k) != v: match = False; break
                    if match: results.append(s)
        return results

    async def get_calls(self, caller_fqn: Optional[str] = None, edge_type: Optional[str] = "CALLS") -> List[Dict[str, Any]]:
        CACHE_QUERY_TOTAL.labels(method='get_calls').inc()
        results = []
        for c in self.calls:
            if c.get("introduced_in") in self.ancestry_set:
                deleted_in = c.get("deleted_in")
                if deleted_in is None or deleted_in not in self.ancestry_set:
                    if edge_type and c.get("type", "CALLS") != edge_type:
                        continue
                    if caller_fqn and c.get("from") != caller_fqn:
                        continue
                    results.append(c)
        return results
