from typing import List, Dict, Any, Optional, Set
from prometheus_client import Summary, Counter

# Prometheus Metrics
ADAPTER_LOOKUP_TIME = Summary('adapter_lookup_seconds', 'Time spent in adapter lookups', ['method'])
ADAPTER_CACHE_HIT = Counter('adapter_cache_hits_total', 'Number of cache hits in adapter', ['method'])
ADAPTER_CACHE_MISS = Counter('adapter_cache_misses_total', 'Number of cache misses in adapter', ['method'])
ADAPTER_ERROR_COUNT = Counter('adapter_errors_total', 'Number of adapter errors', ['method'])

class BiTemporalAdapter:
    """
    Adapter for graph-native topological lookups.
    Integrates an optimized memory cache for active workspace state.
    """
    def __init__(self, engine_client: Any, cache_layer: Optional[Any] = None):
        self.engine_client = engine_client
        self.cache_layer = cache_layer
        self._ancestry_cache: Dict[str, Set[str]] = {}

    async def _get_ancestry(self, commit_sha: str) -> List[str]:
        return await self.engine_client.topological_lookback_query(commit_sha)

    @ADAPTER_LOOKUP_TIME.labels(method='get_symbols').time()
    async def get_symbols(self, commit_sha: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            # Check cache first if it's the active branch tip
            if self.cache_layer:
                active_sha = await self.cache_layer.get_active_sha()
                if commit_sha == active_sha:
                    ADAPTER_CACHE_HIT.labels(method='get_symbols').inc()
                    return await self.cache_layer.get_symbols(filters)

            ADAPTER_CACHE_MISS.labels(method='get_symbols').inc()
            ancestry = await self._get_ancestry(commit_sha)
            # Delegate filtering to the engine client
            return await self.engine_client.query_nodes(
                ancestry=ancestry,
                node_type="DefNode",
                filters=filters
            )
        except Exception:
            ADAPTER_ERROR_COUNT.labels(method='get_symbols').inc()
            raise

    @ADAPTER_LOOKUP_TIME.labels(method='get_calls').time()
    async def get_calls(self, commit_sha: str, caller_fqn: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            # Check cache first
            if self.cache_layer:
                active_sha = await self.cache_layer.get_active_sha()
                if commit_sha == active_sha:
                    ADAPTER_CACHE_HIT.labels(method='get_calls').inc()
                    return await self.cache_layer.get_calls(caller_fqn)

            ADAPTER_CACHE_MISS.labels(method='get_calls').inc()
            ancestry = await self._get_ancestry(commit_sha)
            filters = {"from": caller_fqn} if caller_fqn else None
            return await self.engine_client.query_edges(
                ancestry=ancestry,
                edge_type="CALLS",
                filters=filters
            )
        except Exception:
            ADAPTER_ERROR_COUNT.labels(method='get_calls').inc()
            raise

    async def get_transitive_dependencies(self, commit_sha: str, start_fqn: str, max_depth: int = 5) -> Set[str]:
        ancestry = await self._get_ancestry(commit_sha)
        # Ideally, use a native graph traversal if supported by the engine
        if hasattr(self.engine_client, "transitive_traversal"):
            return await self.engine_client.transitive_traversal(
                ancestry=ancestry,
                start_node=start_fqn,
                edge_type="CALLS",
                max_depth=max_depth
            )
        
        # Fallback to BFS but using engine-side filtering per step
        dependencies = set()
        to_visit = [(start_fqn, 0)]
        visited = set()

        while to_visit:
            curr_fqn, depth = to_visit.pop(0)
            if curr_fqn in visited or depth >= max_depth:
                continue
            visited.add(curr_fqn)
            
            calls = await self.get_calls(commit_sha, caller_fqn=curr_fqn)
            for call in calls:
                callee = call.get("to")
                if callee:
                    dependencies.add(callee)
                    to_visit.append((callee, depth + 1))
                    
        return dependencies
