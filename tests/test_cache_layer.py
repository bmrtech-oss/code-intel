import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.cache.cdc_listener import CDCListener
from src.cache.cache_bootstrap import CacheBootstrap
from src.cache.memory_cache import MemoryCache
from src.storage.graph_engine import SimpleGraphEngine

@pytest.mark.asyncio
async def test_cdc_listener_poll():
    engine = AsyncMock()
    cache = AsyncMock()
    
    engine.get_current_branch_tip.side_effect = ["sha1", "sha2"]
    engine.get_delta.return_value = {"added_nodes": [], "removed_nodes": [], "added_edges": [], "removed_edges": [], "new_ancestry": ["sha2", "sha1"]}
    
    listener = CDCListener(engine, cache, poll_interval=0.1)
    
    # Run check_for_updates twice
    await listener.check_for_updates() # sha1
    assert listener.last_synced_sha == "sha1"
    
    await listener.check_for_updates() # sha2
    assert listener.last_synced_sha == "sha2"
    engine.get_delta.assert_called_with("sha1", "sha2")
    cache.apply_delta.assert_called_with(engine.get_delta.return_value, "sha2")

@pytest.mark.asyncio
async def test_cache_bootstrap_full_rebuild():
    engine = AsyncMock()
    cache = AsyncMock()
    
    cache.get_last_sync_marker.return_value = None
    engine.get_current_branch_tip.return_value = "sha1"
    engine.topological_lookback_query.return_value = ["sha1"]
    engine.query_nodes.return_value = [{"id": "n1"}]
    engine.query_edges.return_value = [{"from": "n1", "to": "n2"}]
    
    bootstrap = CacheBootstrap(engine, cache)
    await bootstrap.initialize_cache()
    
    assert bootstrap.rebuild_progress == 100.0
    cache.populate.assert_called_with([{"id": "n1"}], [{"from": "n1", "to": "n2"}], "sha1", ["sha1"])
    assert bootstrap.get_status_headers()["X-Cache-Status"] == "hit"

@pytest.mark.asyncio
async def test_xor_sync_logic():
    cache = MemoryCache()
    
    # Initial state
    initial_symbols = [{"id": "s1", "introduced_in": "sha1"}]
    initial_calls = [{"from": "s1", "to": "s2", "introduced_in": "sha1"}]
    await cache.populate(initial_symbols, initial_calls, "sha1", ["sha1"])
    
    # Delta from sha1 to sha2
    delta = {
        "added_nodes": [{"id": "s3", "introduced_in": "sha2"}],
        "removed_nodes": [{"id": "s1"}],
        "added_edges": [{"from": "s3", "to": "s2", "introduced_in": "sha2"}],
        "removed_edges": [{"from": "s1", "to": "s2"}],
        "new_ancestry": ["sha2", "sha1"]
    }
    
    await cache.apply_delta(delta, "sha2")
    
    assert len(cache.symbols) == 1
    assert cache.symbols[0]["id"] == "s3"
    assert len(cache.calls) == 1
    assert cache.calls[0]["from"] == "s3"
    assert cache.active_sha == "sha2"
    assert cache.ancestry_set == {"sha1", "sha2"}

@pytest.mark.asyncio
async def test_graph_engine_get_delta():
    # Mock data files not needed if we mock the internal methods
    engine = SimpleGraphEngine()
    
    engine.topological_lookback_query = AsyncMock(side_effect=lambda sha: ["sha1"] if sha == "sha1" else ["sha2", "sha1"])
    
    def mock_query_nodes(ancestry, node_type):
        if "sha2" in ancestry:
            return [{"id": "s1"}, {"id": "s2"}]
        return [{"id": "s1"}]
    
    def mock_query_edges(ancestry, edge_type):
        if "sha2" in ancestry:
            return [{"from": "s1", "to": "s2"}]
        return []

    engine.query_nodes = AsyncMock(side_effect=mock_query_nodes)
    engine.query_edges = AsyncMock(side_effect=mock_query_edges)
    
    delta = await engine.get_delta("sha1", "sha2")
    
    assert len(delta["added_nodes"]) == 1
    assert delta["added_nodes"][0]["id"] == "s2"
    assert len(delta["removed_nodes"]) == 0
    assert len(delta["added_edges"]) == 1
    assert delta["new_ancestry"] == ["sha2", "sha1"]
