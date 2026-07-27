import os
import pytest
import importlib
from unittest.mock import MagicMock, patch

from code_intel.core.dataflow import DataflowEngine, ProductionGraphEngine, LocalGraphEngine

class MockStorage:
    def __init__(self):
        self.facts = []
        self.derived_facts = []

    async def get_derived_fact(self, fact_type, version, entity_id=None):
        return None

    async def execute_query(self, query, params):
        # Mock queries returning symbols and edges
        if "graph_nodes" in query:
            return [{"fqn": "A", "kind": "function", "file": "a.py", "version": "v1"}]
        if "graph_edges" in query:
            return [{"from_fqn": "A", "to_fqn": "B", "confidence": 1.0, "version": "v1"}]
        if "current_symbols" in query:
            return [{"symbol_id": "A", "name": "A", "kind": "function", "file": "a.py"}]
        return []

    async def insert_derived_fact(self, *args, **kwargs):
        pass

    async def rebuild_read_model(self, version):
        pass

def test_engine_factory_selection():
    storage = MockStorage()

    # Test fallback/production default
    with patch.dict(os.environ, {"GRAPH_ENGINE": "production"}):
        import code_intel.settings
        importlib.reload(code_intel.settings)
        engine = DataflowEngine(storage)
        assert isinstance(engine.engine, ProductionGraphEngine)

    # Test local
    with patch.dict(os.environ, {"GRAPH_ENGINE": "local"}):
        import code_intel.settings
        importlib.reload(code_intel.settings)
        # Mock graphqlite to avoid runtime extension error if not supported on host python
        with patch("code_intel.core.dataflow.GRAPHQLITE_AVAILABLE", True):
            with patch("code_intel.core.dataflow.graphqlite") as mock_graphqlite:
                mock_graphqlite.Graph.return_value = MagicMock()
                engine = DataflowEngine(storage)
                assert isinstance(engine.engine, LocalGraphEngine)

@pytest.mark.asyncio
async def test_local_graph_engine_cypher_queries():
    storage = MockStorage()
    with patch("code_intel.core.dataflow.GRAPHQLITE_AVAILABLE", True):
        with patch("code_intel.core.dataflow.graphqlite") as mock_graphqlite:
            mock_graph = MagicMock()
            mock_graphqlite.Graph.return_value = mock_graph

            # Setup mock query results for transitive calls
            mock_graph.query.return_value = [
                {"caller": "A", "callee": "B"}
            ]

            engine = LocalGraphEngine(storage)

            # Test transitive calls
            res = await engine.transitive_calls("v1")
            assert len(res) == 1
            assert res[0]["caller"] == "A"
            assert res[0]["callee"] == "B"

            # Verify the Cypher query executed
            mock_graph.query.assert_any_call(
                "MATCH (caller)-[:CALLS*]->(callee) RETURN DISTINCT caller.id AS caller, callee.id AS callee"
            )

@pytest.mark.asyncio
async def test_local_graph_engine_impact_analysis():
    storage = MockStorage()
    with patch("code_intel.core.dataflow.GRAPHQLITE_AVAILABLE", True):
        with patch("code_intel.core.dataflow.graphqlite") as mock_graphqlite:
            mock_graph = MagicMock()
            mock_graphqlite.Graph.return_value = mock_graph

            mock_graph.query.return_value = [
                {"caller": "B", "depth": 1},
                {"caller": "C", "depth": 2}
            ]

            engine = LocalGraphEngine(storage)
            res = await engine.impact_analysis("A", "v1", depth=3)

            assert len(res) == 2
            assert res[0]["caller"] == "B"
            assert res[0]["depth"] == 1
            assert res[1]["caller"] == "C"
            assert res[1]["depth"] == 2

            mock_graph.query.assert_any_call(
                "MATCH p = (callee {id: $sym})<-[:CALLS*1..$depth]-(caller) RETURN caller.id AS caller, length(p) AS depth",
                {"sym": "A", "depth": 3}
            )

@pytest.mark.asyncio
async def test_local_graph_engine_rebuild():
    storage = MockStorage()
    with patch("code_intel.core.dataflow.GRAPHQLITE_AVAILABLE", True):
        with patch("code_intel.core.dataflow.graphqlite") as mock_graphqlite:
            mock_graph = MagicMock()
            mock_graphqlite.Graph.return_value = mock_graph

            engine = LocalGraphEngine(storage)
            await engine.rebuild_graph("v1")

            # Verify upsert node and edge called
            mock_graph.upsert_node.assert_called_once_with(
                node_id="A",
                label="Symbol",
                properties={"kind": "function", "file": "a.py", "version": "v1"}
            )
            mock_graph.upsert_edge.assert_called_once_with(
                source_id="A",
                target_id="B",
                rel_type="CALLS",
                properties={"confidence": 1.0, "version": "v1"}
            )
