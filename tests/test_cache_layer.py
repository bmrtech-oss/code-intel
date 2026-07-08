import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.cache.cdc_listener import CDCListener
from src.cache.cache_bootstrap import CacheBootstrap

@pytest.mark.asyncio
async def test_cdc_listener_poll():
    engine = AsyncMock()
    cache = AsyncMock()

    engine.get_current_branch_tip.side_effect = ["sha1", "sha2"]
    engine.get_delta.return_value = {"added_nodes": [], "added_edges": [], "new_ancestry": ["sha2"]}
    engine.topological_lookback_query.return_value = ["sha1"]

    listener = CDCListener(engine, cache, poll_interval=0.1)

    # Run check_for_updates twice
    await listener.check_for_updates() # sha1
    assert listener.last_synced_sha == "sha1"

    await listener.check_for_updates() # sha2
    assert listener.last_synced_sha == "sha2"
    engine.get_delta.assert_called_with("sha1", "sha2")
    cache.apply_delta.assert_called_with(
        {"added_nodes": [], "added_edges": [], "new_ancestry": ["sha2"]},
        "sha2",
        ["sha2"]
    )

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
