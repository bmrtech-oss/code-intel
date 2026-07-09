import pytest
from unittest.mock import AsyncMock
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
    engine.get_ancestry_mask.return_value = 0b11
    
    listener = CDCListener(engine, cache, poll_interval=0.1)
    
    # Run check_for_updates twice
    await listener.check_for_updates() # sha1
    assert listener.last_synced_sha == "sha1"
    
    await listener.check_for_updates() # sha2
    assert listener.last_synced_sha == "sha2"
    engine.get_delta.assert_called_with("sha1", "sha2")
    cache.apply_delta.assert_called_with(engine.get_delta.return_value, "sha2", new_mask=0b11)

@pytest.mark.asyncio
async def test_cache_bootstrap_full_rebuild():
    engine = AsyncMock()
    cache = AsyncMock()
    
    cache.get_last_sync_marker.return_value = None
    engine.get_current_branch_tip.return_value = "sha1"
    engine.topological_lookback_query.return_value = ["sha1"]
    engine.query_nodes.return_value = [{"id": "n1"}]
    engine.query_edges.return_value = [{"from": "n1", "to": "n2"}]
    engine.get_ancestry_mask.return_value = 0b1
    
    bootstrap = CacheBootstrap(engine, cache)
    await bootstrap.initialize_cache()
    
    assert bootstrap.rebuild_progress == 100.0
    cache.populate.assert_called_with([{"id": "n1"}], [{"from": "n1", "to": "n2"}], "sha1", ["sha1"], mask=0b1)
    assert bootstrap.get_status_headers()["X-Cache-Status"] == "hit"

@pytest.mark.asyncio
async def test_bitset_sync_logic():
    cache = MemoryCache()
    
    # Initial state
    initial_symbols = [{"id": "s1", "introduced_in": "sha1", "_intro_bit": 1, "_del_bit": 0}]
    initial_calls = [{"from": "s1", "to": "s2", "introduced_in": "sha1", "_intro_bit": 1, "_del_bit": 0}]
    await cache.populate(initial_symbols, initial_calls, "sha1", ["sha1"], mask=0b1)
    
    # Delta from sha1 to sha2
    delta = {
        "added_nodes": [{"id": "s3", "introduced_in": "sha2", "_intro_bit": 2, "_del_bit": 0}],
        "removed_nodes": [{"id": "s1"}],
        "added_edges": [{"from": "s3", "to": "s2", "introduced_in": "sha2", "_intro_bit": 2, "_del_bit": 0}],
        "removed_edges": [{"from": "s1", "to": "s2"}],
        "new_ancestry": ["sha2", "sha1"]
    }
    
    await cache.apply_delta(delta, "sha2", new_mask=0b11)
    
    assert len(cache.symbols) == 1
    assert cache.symbols[0]["id"] == "s3"
    assert len(cache.calls) == 1
    assert cache.calls[0]["from"] == "s3"
    assert cache.active_sha == "sha2"
    assert cache.ancestry_mask == 0b11

    # Verify visibility
    visible_symbols = await cache.get_symbols()
    assert len(visible_symbols) == 1
    assert visible_symbols[0]["id"] == "s3"

@pytest.mark.asyncio
async def test_graph_engine_bitset_visibility():
    # Construct topological state with commits
    commits = [
        {"sha": "v2", "parents": ["v1"]},
        {"sha": "v1", "parents": []}
    ]
    nodes = [
        {"id": "s1", "introduced_in": "v1", "deleted_in": "v2"},
        {"id": "s2", "introduced_in": "v2", "deleted_in": None}
    ]
    
    import json
    import os
    with open("commits.jsonl", "w") as f:
        for c in commits: f.write(json.dumps(c) + "\n")
    with open("nodes.jsonl", "w") as f:
        for n in nodes: f.write(json.dumps(n) + "\n")
    
    engine = SimpleGraphEngine(data_dir=".")
    
    # Test v1 visibility
    mask_v1 = await engine.get_ancestry_mask("v1")
    nodes_v1 = await engine.query_nodes(mask=mask_v1)
    assert len(nodes_v1) == 1
    assert nodes_v1[0]["id"] == "s1"
    
    # Test v2 visibility
    mask_v2 = await engine.get_ancestry_mask("v2")
    nodes_v2 = await engine.query_nodes(mask=mask_v2)
    assert len(nodes_v2) == 1
    assert nodes_v2[0]["id"] == "s2"
    
    os.remove("commits.jsonl")
    os.remove("nodes.jsonl")
