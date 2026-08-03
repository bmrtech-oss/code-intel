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
        # Test Query Parameter Endpoint
        response = client.get("/api/graph/historical?repo_id=my_repo&commit_sha=v1")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["fqn"] == "pkg.f1"
        assert len(data["edges"]) == 1
        assert data["edges"][0]["from_fqn"] == "pkg.f1"

        # Re-mock side_effect for Path Parameter Endpoint
        mock_execute.side_effect = [mock_nodes_result, mock_edges_result]

        # Test Path Parameter Endpoint
        response_path = client.get("/api/graph/historical/my_repo/v1")
        assert response_path.status_code == 200
        data_path = response_path.json()
        assert "nodes" in data_path
        assert "edges" in data_path
        assert len(data_path["nodes"]) == 1
        assert data_path["nodes"][0]["fqn"] == "pkg.f1"

    finally:
        app.dependency_overrides.clear()

def test_get_commit_timeline_endpoint():
    client = TestClient(app)

    with patch("code_intel.services.git_service.GitService.get_commit_timeline") as mock_timeline:
        mock_timeline.return_value = [
            {"sha": "abc123def", "timestamp": 1700000000},
            {"sha": "ghi456jkl", "timestamp": 1700000060}
        ]

        response = client.get("/api/repo/my_repo_id/timeline")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["sha"] == "abc123def"
        assert data[0]["timestamp"] == 1700000000
        assert data[1]["sha"] == "ghi456jkl"
