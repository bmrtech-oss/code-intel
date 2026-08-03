import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from code_intel.api.server import app

def test_extract_structured_path_traversal():
    client = TestClient(app)

    # 1. Unsafe path should be rejected immediately
    response = client.post(
        "/api/extract/structured",
        json={"file_path": "/etc/passwd"}
    )
    assert response.status_code == 400
    assert "unsafe" in response.json()["detail"].lower()

    # 2. Relative directory traversal should be rejected
    response2 = client.post(
        "/api/extract/structured",
        json={"file_path": "../../etc/passwd"}
    )
    assert response2.status_code == 400
    assert "unsafe" in response2.json()["detail"].lower()


def test_extract_structured_file_not_found():
    client = TestClient(app)

    # A safe but non-existent file should return 404
    response = client.post(
        "/api/extract/structured",
        json={"file_path": "code_intel/api/nonexistent_file.py"}
    )
    assert response.status_code == 404
    assert "file not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_structured_success():
    client = TestClient(app)

    # Target a real, safe file that exists
    safe_file_path = "code_intel/api/server.py"

    # Mock the LLM call generate_structured
    mock_udf_instance = MagicMock()
    mock_udf_instance.generate_structured = AsyncMock()
    mock_udf_instance.generate_structured.return_value = {
        "business_rules": ["Valid CORS policy only", "Input validation is strict"],
        "edge_cases": ["Special characters in paths", "Unquoted path decoding"],
        "data_transformations": ["Decodes url encoded repo ids", "Resolves full path names"],
        "side_effects": ["Launches subprocesses synchronously", "Reads files from filesystem"]
    }

    with patch("code_intel.api.routes.extraction.LLMUDF", return_value=mock_udf_instance):
        response = client.post(
            "/api/extract/structured",
            json={"file_path": safe_file_path}
        )
        assert response.status_code == 200
        data = response.json()
        assert "business_rules" in data
        assert "edge_cases" in data
        assert len(data["business_rules"]) == 2
        assert data["business_rules"][0] == "Valid CORS policy only"

        # Verify mock called
        mock_udf_instance.generate_structured.assert_called_once()
