import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from code_intel.api.server import app

def test_api_status_default():
    client = TestClient(app)
    # We patch os.path.exists and os.getenv to control the dynamic detection
    with patch("os.path.exists", return_value=False), patch.dict(os.environ, {"IS_DOCKER": "false"}):
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["version"] == "1.0.0"
        assert data["is_docker"] is False
        assert data["allowed_volumes"] == ["/repo", "/shared"]
        assert data["extractor_version"] == "1.0.0"

        # Also test GET /api/status
        response_api = client.get("/api/status")
        assert response_api.status_code == 200
        assert response_api.json() == data

def test_api_status_docker_env():
    client = TestClient(app)
    # Case 1: /.dockerenv exists
    with patch("os.path.exists", side_effect=lambda path: path == "/.dockerenv"), patch.dict(os.environ, {"IS_DOCKER": "false"}):
        response = client.get("/status")
        assert response.status_code == 200
        assert response.json()["is_docker"] is True

    # Case 2: IS_DOCKER environment variable is true
    with patch("os.path.exists", return_value=False), patch.dict(os.environ, {"IS_DOCKER": "true"}):
        response = client.get("/status")
        assert response.status_code == 200
        assert response.json()["is_docker"] is True

def test_api_status_cors():
    client = TestClient(app)

    # Test tauri://localhost origin
    response = client.get(
        "/status",
        headers={"Origin": "tauri://localhost", "Access-Control-Request-Method": "GET"}
    )
    assert response.headers.get("access-control-allow-origin") == "tauri://localhost"

    # Test http://tauri.localhost origin
    response = client.get(
        "/status",
        headers={"Origin": "http://tauri.localhost", "Access-Control-Request-Method": "GET"}
    )
    assert response.headers.get("access-control-allow-origin") == "http://tauri.localhost"
