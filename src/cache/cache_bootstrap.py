import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

class CacheBootstrap:
    """
    Handles cold-start cache rebuilding from the graph store.
    """
    def __init__(self, engine_client: Any, cache_layer: Any):
        self.engine_client = engine_client
        self.cache_layer = cache_layer
        self.is_rebuilding = False
        self.rebuild_progress = 0.0

    async def initialize_cache(self):
        last_sync = await self.cache_layer.get_last_sync_marker()
        if not last_sync:
            logger.info("Cache is empty. Starting full rebuild.")
            await self.full_rebuild()
        else:
            logger.info(f"Cache found. Last sync: {last_sync}")

    async def full_rebuild(self):
        self.is_rebuilding = True
        self.rebuild_progress = 0.0
        start_time = time.time()
        
        try:
            current_sha = await self.engine_client.get_current_branch_tip()
            # Fetch all active symbols and calls for the current tip
            # In a real scenario, this would be paginated
            logger.info(f"Fetching all data for {current_sha}...")
            
            # Simulated progress
            ancestry = await self.engine_client.topological_lookback_query(current_sha)
            symbols = await self.engine_client.query_nodes(ancestry=ancestry, node_type="DefNode")
            self.rebuild_progress = 50.0
            logger.info(f"Loaded {len(symbols)} symbols. (50%)")
            
            calls = await self.engine_client.query_edges(ancestry=ancestry, edge_type="CALLS")
            self.rebuild_progress = 100.0
            logger.info(f"Loaded {len(calls)} calls. (100%)")
            
            await self.cache_layer.populate(symbols, calls, current_sha, ancestry)
            
            duration = time.time() - start_time
            logger.info(f"Cache rebuild complete in {duration:.2f}s for SHA {current_sha}")
        finally:
            self.is_rebuilding = False

    def get_status_headers(self) -> dict:
        if self.is_rebuilding:
            return {"X-Cache-Status": "stale", "X-Cache-Rebuild-Progress": f"{self.rebuild_progress}%"}
        return {"X-Cache-Status": "hit"}
