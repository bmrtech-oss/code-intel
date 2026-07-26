import os
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from code_intel.api.server import app
from code_intel.core.storage import get_db

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

def test_analyze_stream_redis_data():
    client = TestClient(app)

    mock_redis = MagicMock()
    mock_redis.get.side_effect = [
        b'{"file": "main.py", "progress": 42, "done": false}',
        b'{"file": "other.py", "progress": 100, "done": true}'
    ]

    with patch("redis.Redis", return_value=mock_redis):
        response = client.get("/analyze/stream?job_id=test-job-id")
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/event-stream")

        lines = [line for line in response.iter_lines() if line]
        assert len(lines) == 2
        assert '{"file": "main.py", "progress": 42, "done": false}' in lines[0]
        assert '{"file": "other.py", "progress": 100, "done": true}' in lines[1]

def test_analyze_stream_job_not_found():
    client = TestClient(app)

    mock_redis = MagicMock()
    mock_redis.get.return_value = None

    with patch("redis.Redis", return_value=mock_redis), patch("code_intel.worker.tasks.queue.fetch_job", return_value=None):
        response = client.get("/analyze/stream?job_id=non-existent-job")
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/event-stream")

        lines = [line for line in response.iter_lines() if line]
        assert len(lines) == 1
        assert "Job not found" in lines[0]

def test_post_config_llm_and_udf_sync():
    client = TestClient(app)

    # We will mock Redis to capture setex/get calls
    stored_configs = {}

    def mock_setex(key, ttl, value):
        stored_configs[key] = value

    def mock_get(key):
        return stored_configs.get(key)

    mock_redis = MagicMock()
    mock_redis.setex.side_effect = mock_setex
    mock_redis.get.side_effect = mock_get

    with patch("redis.Redis", return_value=mock_redis):
        # 1. POST the dynamic configuration
        payload = {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "sk-proj-test-123456",
            "session_id": "session-xyz"
        }
        response = client.post("/config/llm", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify it was stored under correct key and with TTL
        mock_redis.setex.assert_called_once()

        # 2. Initialize LLMUDF and verify it loads correct config
        from code_intel.core.udf import LLMUDF
        udf = LLMUDF(session_id="session-xyz")
        assert udf.provider == "openai"
        assert udf.model == "gpt-4"
        assert udf.api_key == "sk-proj-test-123456"

        # 3. Initialize LLMUDF with different session_id, should fallback to defaults
        udf_fallback = LLMUDF(session_id="other-session")
        # should match defaults from settings
        from code_intel.settings import LLM_PROVIDER, LLM_MODEL, LLM_API_KEY
        assert udf_fallback.provider == LLM_PROVIDER.lower()
        assert udf_fallback.model == LLM_MODEL
        assert udf_fallback.api_key == LLM_API_KEY

def test_get_branches_and_commits_fallback():
    client = TestClient(app)

    # Test fallback mode when git lookup fails/doesn't exist
    response = client.get("/repo/branches-and-commits?repo_path=nonexistent_path")
    assert response.status_code == 200
    data = response.json()
    assert "branches" in data
    assert "commits" in data
    assert len(data["branches"]) > 0
    assert len(data["commits"]) > 0
    assert data["commits"][0]["sha"] == "a7b8c9"

def test_get_branches_and_commits_simple_graph_fallback():
    client = TestClient(app)

    # Mock SimpleGraphEngine to return custom commits
    mock_engine = MagicMock()
    mock_engine.commits = [{"sha": "c1", "author": "Alice", "date": "2026-07-16T12:00:00Z"}]
    # Needs async methods
    async def async_get_current_branch_tip():
        return "c1"
    async def async_topological_lookback_query(tip):
        return ["c1"]
    mock_engine.get_current_branch_tip.side_effect = async_get_current_branch_tip
    mock_engine.topological_lookback_query.side_effect = async_topological_lookback_query

    with patch("code_intel.storage.graph_engine.SimpleGraphEngine", return_value=mock_engine):
        response = client.get("/repo/branches-and-commits?repo_path=some_jsonl_path")
        assert response.status_code == 200
        data = response.json()
        assert data["branches"] == ["main"]
        assert data["commits"] == [{"sha": "c1", "author": "Alice", "date": "2026-07-16T12:00:00Z"}]

def test_get_repo_tree():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    mock_result = MagicMock()
    mock_result.mappings.return_value = [
        {"fqn": "FQN1", "file": "src/main.py"},
        {"fqn": "FQN2", "file": "src/main.py"},
        {"fqn": "FQN3", "file": "src/api/auth.py"},
        {"fqn": "FQN4", "file": "tests/test_api.py"}
    ]

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        mock_execute.return_value = mock_result

        response = client.get("/repo/tree?version=sha-123")
        assert response.status_code == 200
        data = response.json()

        assert "src" in data
        assert data["src"]["type"] == "folder"
        assert "main.py" in data["src"]["children"]
        assert data["src"]["children"]["main.py"]["type"] == "file"
        assert data["src"]["children"]["main.py"]["path"] == "src/main.py"
        assert data["src"]["children"]["main.py"]["symbols"] == ["FQN1", "FQN2"]

        assert "api" in data["src"]["children"]
        assert data["src"]["children"]["api"]["type"] == "folder"
        assert "auth.py" in data["src"]["children"]["api"]["children"]
        assert data["src"]["children"]["api"]["children"]["auth.py"]["symbols"] == ["FQN3"]

        assert "tests" in data
        assert data["tests"]["type"] == "folder"
        assert "test_api.py" in data["tests"]["children"]
        assert data["tests"]["children"]["test_api.py"]["symbols"] == ["FQN4"]

    finally:
        app.dependency_overrides.clear()
