import pytest
import asyncio
from src.storage.bitemporal_adapter import BiTemporalAdapter

class MockEngine:
    def __init__(self, commits, nodes, edges):
        self.commits = commits
        self.nodes = nodes
        self.edges = edges

    async def get_ancestry_mask(self, sha):
        masks = {"c1": 0b1, "c2": 0b11}
        return masks.get(sha, 0)

    async def topological_lookback_query(self, sha):
        ancestry = []
        commit_map = {c["sha"]: c for c in self.commits}
        curr = commit_map.get(sha)
        while curr:
            ancestry.append(curr["sha"])
            parents = curr.get("parents", [])
            if not parents: break
            curr = commit_map.get(parents[0])
        return ancestry

    async def query_nodes(self, ancestry=None, node_type=None, filters=None, mask=None):
        sha_to_bit = {"c1": 0, "c2": 1}
        results = []
        for n in self.nodes:
            intro_bit = 1 << sha_to_bit[n["introduced_in"]]
            del_bit = 1 << sha_to_bit[n["deleted_in"]] if n.get("deleted_in") else 0
            if (intro_bit & mask) != 0 and (del_bit & mask) == 0:
                match = True
                if filters:
                    for k, v in filters.items():
                        if n.get(k) != v: match = False; break
                if match: results.append(n)
        return results

    async def query_edges(self, ancestry=None, edge_type=None, filters=None, mask=None):
        sha_to_bit = {"c1": 0, "c2": 1}
        results = []
        for e in self.edges:
            intro_bit = 1 << sha_to_bit[e["introduced_in"]]
            del_bit = 1 << sha_to_bit[e["deleted_in"]] if e.get("deleted_in") else 0
            if (intro_bit & mask) != 0 and (del_bit & mask) == 0:
                match = True
                if filters:
                    for k, v in filters.items():
                        if e.get(k) != v: match = False; break
                if match: results.append(e)
        return results

@pytest.mark.asyncio
async def test_bitemporal_adapter_visibility():
    commits = [
        {"sha": "c2", "parents": ["c1"]},
        {"sha": "c1", "parents": []}
    ]
    nodes = [
        {"id": "f1", "fqn": "pkg.f1", "introduced_in": "c1", "deleted_in": None},
        {"id": "f2", "fqn": "pkg.f2", "introduced_in": "c2", "deleted_in": None},
        {"id": "f3", "fqn": "pkg.f3", "introduced_in": "c1", "deleted_in": "c2"}
    ]
    edges = [
        {"from": "pkg.f1", "to": "pkg.f3", "introduced_in": "c1", "deleted_in": "c2"}
    ]
    
    engine = MockEngine(commits, nodes, edges)
    adapter = BiTemporalAdapter(engine)
    
    # Test visibility at c1
    symbols_c1 = await adapter.get_symbols("c1")
    symbol_ids_c1 = {s["id"] for s in symbols_c1}
    assert "f1" in symbol_ids_c1
    assert "f3" in symbol_ids_c1
    assert "f2" not in symbol_ids_c1
    
    calls_c1 = await adapter.get_calls("c1")
    assert len(calls_c1) == 1
    
    # Test visibility at c2
    symbols_c2 = await adapter.get_symbols("c2")
    symbol_ids_c2 = {s["id"] for s in symbols_c2}
    assert "f1" in symbol_ids_c2
    assert "f2" in symbol_ids_c2
    assert "f3" not in symbol_ids_c2 # f3 was deleted in c2
    
    calls_c2 = await adapter.get_calls("c2")
    assert len(calls_c2) == 0 # call to f3 was deleted in c2

@pytest.mark.asyncio
async def test_transitive_dependencies():
    commits = [{"sha": "c1", "parents": []}]
    nodes = [
        {"id": "a", "fqn": "a", "introduced_in": "c1"},
        {"id": "b", "fqn": "b", "introduced_in": "c1"},
        {"id": "c", "fqn": "c", "introduced_in": "c1"}
    ]
    edges = [
        {"from": "a", "to": "b", "introduced_in": "c1"},
        {"from": "b", "to": "c", "introduced_in": "c1"}
    ]
    engine = MockEngine(commits, nodes, edges)
    adapter = BiTemporalAdapter(engine)
    
    deps = await adapter.get_transitive_dependencies("c1", "a")
    assert deps == {"b", "c"}
