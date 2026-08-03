from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from code_intel.api.server import app
from code_intel.core.storage import get_db

def test_get_historical_graph_success():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    mock_nodes_result = MagicMock()
    mock_nodes_result.mappings.return_value = [
        {
            "id": 1,
            "fqn": "pkg.f1",
            "kind": "function",
            "file": "src/main.py",
            "version": "v1",
            "introduced_in": "v1",
            "deleted_in": None,
            "valid_from_sha": "v1",
            "valid_to_sha": None
        }
    ]
    mock_edges_result = MagicMock()
    mock_edges_result.mappings.return_value = [
        {
            "id": 101,
            "from_fqn": "pkg.f1",
            "to_fqn": "pkg.f2",
            "edge_type": "CALLS",
            "version": "v1",
            "confidence": 1.0,
            "introduced_in": "v1",
            "deleted_in": None,
            "valid_from_sha": "v1",
            "valid_to_sha": None
        }
    ]

    mock_execute.side_effect = [mock_nodes_result, mock_edges_result]

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/graph/historical?repo_id=my_repo&commit_sha=v1")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["fqn"] == "pkg.f1"
        assert len(data["edges"]) == 1
        assert data["edges"][0]["from_fqn"] == "pkg.f1"

    finally:
        app.dependency_overrides.clear()
