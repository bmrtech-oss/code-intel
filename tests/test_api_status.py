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

    # Test http://localhost origin
    response = client.get(
        "/status",
        headers={"Origin": "http://localhost", "Access-Control-Request-Method": "GET"}
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost"

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
    assert len(data["commits"]) == 0

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
        assert data["commits"] == [{"sha": "c1", "author": "Alice", "date": "2026-07-16T12:00:00Z", "message": ""}]

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


def test_get_graph_path_normalization_and_all_suffix_matching():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    mock_nodes_result = MagicMock()
    # Test path normalization on file field
    mock_nodes_result.mappings.return_value = [
        {"fqn": "starter_repo.plot_data.read_csv_data", "kind": "function", "file": "/tmp/codeintel_gn0t226s/starter_repo/plot_data.py"},
        {"fqn": "src.main.main", "kind": "function", "file": "/tmp/codeintel_4mtsyun5/src/main.py"}
    ]
    mock_edges_result = MagicMock()
    # Test unqualified/partially-qualified symbol matching to fully-qualified name
    mock_edges_result.mappings.return_value = [
        {"from_fqn": "read_csv_data", "to_fqn": "main"}
    ]

    mock_execute.side_effect = [mock_nodes_result, mock_edges_result]

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        # Test level=file path normalization and cross-run edge matching
        response = client.get("/graph?version=sha-123&level=file")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        # Prefix /tmp/codeintel_... should be stripped
        assert {n["id"] for n in data["nodes"]} == {"file:starter_repo/plot_data.py", "file:src/main.py"}
        assert len(data["edges"]) == 1
        assert data["edges"][0]["source"] == "file:starter_repo/plot_data.py"
        assert data["edges"][0]["target"] == "file:src/main.py"

        # Reset execute mock to test level=all suffix matching
        mock_execute.side_effect = [mock_nodes_result, mock_edges_result]
        response2 = client.get("/graph?version=sha-123&level=all")
        assert response2.status_code == 200
        data2 = response2.json()
        assert "nodes" in data2
        assert "edges" in data2
        # Edges should use resolved fully-qualified names
        assert len(data2["edges"]) == 1
        assert data2["edges"][0]["source"] == "starter_repo.plot_data.read_csv_data"
        assert data2["edges"][0]["target"] == "src.main.main"

    finally:
        app.dependency_overrides.clear()

def test_post_config_llm_test():
    client = TestClient(app)

    # Mock OllamaClient.generate to verify successful test response
    with patch("redis.Redis") as mock_redis, \
         patch("code_intel.core.udf.AsyncClient") as mock_ollama_client_class:

        mock_redis.return_value.get.return_value = None

        mock_ollama_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "success_test_token"
        mock_ollama_client.generate.return_value = mock_response
        mock_ollama_client_class.return_value = mock_ollama_client

        # We force LLM_PROVIDER as ollama
        with patch("code_intel.core.udf.LLM_PROVIDER", "ollama"):
            response = client.post("/config/llm/test", json={"session_id": "default"})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "success_test_token" in data["response"]

def test_open_editor():
    client = TestClient(app)

    # 1. Unsafe path should be rejected
    response = client.post("/api/open-editor", json={"file_path": "/etc/passwd"})
    assert response.status_code == 400
    assert "unauthorized" in response.json()["detail"].lower()

    # 2. Safe path (like current directory file) with mock startfile/run
    with patch("sys.platform", "win32"), patch("os.startfile", create=True) as mock_startfile:
        response = client.post("/api/open-editor", json={"file_path": "code_intel/api/server.py"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_startfile.assert_called_once_with("code_intel/api/server.py")


def test_find_references():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    async def mock_execute_fn(query, params=None):
        query_str = str(query)
        if "LIMIT 1" in query_str:
            mock_res = MagicMock()
            mock_res.scalar.return_value = None
            return mock_res
        elif "DISTINCT version" in query_str:
            mock_res = MagicMock()
            mock_res.mappings.return_value = []
            return mock_res
        elif "from_fqn" in query_str or "caller" in query_str:
            mock_res = MagicMock()
            # Mock .all() return value which yields rows as tuples
            mock_res.all.return_value = [("caller_1",)]
            return mock_res
        return MagicMock()

    mock_execute.side_effect = mock_execute_fn

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/api/references?symbol_id=target_sym&version=v1")
        assert response.status_code == 200
        data = response.json()
        assert data["references"] == ["caller_1"]

    finally:
        app.dependency_overrides.clear()

def test_get_version_status():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    # Mock DB queries:
    # 1. First execute call inside version-status check: graph_nodes check -> returns None (not analyzed)
    # 2. Second execute call inside version-status check: current_symbols check -> returns None (not analyzed)
    # 3. Third execute call inside find_best_version: LIMIT 1 -> returns None
    # 4. Fourth execute call inside find_best_version: SELECT DISTINCT version FROM graph_nodes -> returns [{"version": "fallback_sha"}]
    # 5. Fifth execute call: SELECT DISTINCT version FROM graph_nodes (has any analysis check) -> returns [{"version": "fallback_sha"}]
    mock_result_not_found = MagicMock()
    mock_result_not_found.scalar.return_value = None

    mock_result_distinct = MagicMock()
    mock_result_distinct.mappings.return_value = [
        {"version": "fallback_sha"}
    ]

    mock_execute.side_effect = [
        mock_result_not_found,
        mock_result_not_found,
        mock_result_not_found,
        mock_result_distinct,
        mock_result_distinct
    ]

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/repo/version-status?version=missing_sha")
        assert response.status_code == 200
        data = response.json()
        assert data["requested_version"] == "missing_sha"
        assert data["is_analyzed"] is False
        assert data["best_fallback_version"] == "fallback_sha"
        assert data["has_any_analysis"] is True

    finally:
        app.dependency_overrides.clear()


def test_tree_graph_response_headers():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    # Mock DB query for get_repo_tree: returns nodes on the first call (so no fallback is triggered)
    mock_result_tree = MagicMock()
    mock_result_tree.mappings.return_value = [
        {"fqn": "FQN1", "file": "src/main.py"}
    ]
    mock_execute.return_value = mock_result_tree

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/repo/tree?version=active_sha")
        assert response.status_code == 200
        assert response.headers.get("X-Version-Requested") == "active_sha"
        assert response.headers.get("X-Version-Resolved") == "active_sha"
        assert response.headers.get("X-Version-Fallback") == "false"

    finally:
        app.dependency_overrides.clear()

def test_find_best_version_fallback():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    async def mock_execute_fn(query, params=None):
        query_str = str(query)
        if "LIMIT 1" in query_str:
            mock_res = MagicMock()
            mock_res.scalar.return_value = None
            return mock_res
        elif "DISTINCT version" in query_str:
            mock_res = MagicMock()
            mock_res.mappings.return_value = [{"version": "existing_sha_999"}]
            return mock_res
        else:
            if params and params.get("v") == "existing_sha_999":
                mock_res = MagicMock()
                mock_res.mappings.return_value = [{"fqn": "FQN1", "file": "src/main.py"}]
                return mock_res
            else:
                mock_res = MagicMock()
                mock_res.mappings.return_value = []
                return mock_res

    mock_execute.side_effect = mock_execute_fn

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/repo/tree?version=missing_sha_111")
        assert response.status_code == 200
        data = response.json()

        # Verify it fallback and returns the tree content for "existing_sha_999"
        assert "src" in data
        assert data["src"]["children"]["main.py"]["symbols"] == ["FQN1"]

    finally:
        app.dependency_overrides.clear()

def test_resolve_version_and_analyze():
    client = TestClient(app)

    # 1. Test resolve_version with mocked Git ls-remote
    with patch("git.cmd.Git") as mock_git_class:
        mock_git = MagicMock()
        mock_git.ls_remote.return_value = "bc044fcc12eff6c92c4a248e78053eca7000bb5e\trefs/heads/main"
        mock_git_class.return_value = mock_git

        from code_intel.api.server import resolve_version
        sha = resolve_version("https://github.com/KenMwaura1/Fast-Api-example", "main")
        assert sha == "bc044fcc12eff6c92c4a248e78053eca7000bb5e"

    # 2. Test POST /analyze with remote Git URL
    with patch("code_intel.worker.tasks.queue.enqueue") as mock_enqueue, \
         patch("git.cmd.Git") as mock_git_class:

        mock_git = MagicMock()
        mock_git.ls_remote.return_value = "bc044fcc12eff6c92c4a248e78053eca7000bb5e\trefs/heads/main"
        mock_git_class.return_value = mock_git

        mock_job = MagicMock()
        mock_job.id = "test-job-id"
        mock_enqueue.return_value = mock_job

        payload = {
            "repo_path": "https://github.com/KenMwaura1/Fast-Api-example",
            "branch": "main"
        }
        response = client.post("/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexing started"
        assert data["version"] == "bc044fcc12eff6c92c4a248e78053eca7000bb5e"
        assert data["job_id"] == "test-job-id"

        # Verify that queue.enqueue was called with is_git_url=True and branch="main"
        from code_intel.worker.tasks import run_ingestion
        mock_enqueue.assert_called_once_with(
            run_ingestion,
            "https://github.com/KenMwaura1/Fast-Api-example",
            "bc044fcc12eff6c92c4a248e78053eca7000bb5e",
            is_git_url=True,
            branch="main",
            job_timeout=300
        )

    # 3. Test POST /analyze with custom timeout
    with patch("code_intel.worker.tasks.queue.enqueue") as mock_enqueue, \
         patch("git.cmd.Git") as mock_git_class:

        mock_git = MagicMock()
        mock_git.ls_remote.return_value = "bc044fcc12eff6c92c4a248e78053eca7000bb5e\trefs/heads/main"
        mock_git_class.return_value = mock_git

        mock_job = MagicMock()
        mock_job.id = "test-job-id"
        mock_enqueue.return_value = mock_job

        payload = {
            "repo_path": "https://github.com/KenMwaura1/Fast-Api-example",
            "branch": "main",
            "timeout": 600
        }
        response = client.post("/analyze", json=payload)
        assert response.status_code == 200

        from code_intel.worker.tasks import run_ingestion
        mock_enqueue.assert_called_once_with(
            run_ingestion,
            "https://github.com/KenMwaura1/Fast-Api-example",
            "bc044fcc12eff6c92c4a248e78053eca7000bb5e",
            is_git_url=True,
            branch="main",
            job_timeout=600
        )

def test_path_traversal_protection():
    client = TestClient(app)

    # Unsafe path should be rejected with 400
    response = client.get("/repo/branches-and-commits?repo_path=/etc/passwd")
    assert response.status_code == 400
    assert "unauthorized" in response.json()["detail"].lower()

    # Relative directory traversal should be rejected with 400
    response2 = client.get("/repo/branches-and-commits?repo_path=../../some_secret_file")
    assert response2.status_code == 400
    assert "unauthorized" in response2.json()["detail"].lower()

    # Safe path (like temporary directory) should be accepted and return 200
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        response3 = client.get(f"/repo/branches-and-commits?repo_path={tmpdir}")
        assert response3.status_code == 200

def test_get_graph_file_level():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    mock_nodes_result = MagicMock()
    mock_nodes_result.mappings.return_value = [
        {"fqn": "pkg.f1", "kind": "function", "file": "src/main.py"},
        {"fqn": "pkg.f2", "kind": "function", "file": "src/auth.py"}
    ]
    mock_edges_result = MagicMock()
    mock_edges_result.mappings.return_value = [
        {"from_fqn": "pkg.f1", "to_fqn": "pkg.f2"}
    ]

    mock_execute.side_effect = [mock_nodes_result, mock_edges_result]

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/graph?version=sha-123&level=file")
        assert response.status_code == 200
        data = response.json()

        # Should aggregate to files
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
        assert {n["id"] for n in data["nodes"]} == {"file:src/main.py", "file:src/auth.py"}
        assert len(data["edges"]) == 1
        assert data["edges"][0] == {"source": "file:src/main.py", "target": "file:src/auth.py", "type": "imports"}

    finally:
        app.dependency_overrides.clear()

def test_get_graph_all_level_with_focus():
    client = TestClient(app)

    mock_db = MagicMock()
    mock_execute = AsyncMock()
    mock_db.execute = mock_execute

    mock_nodes_result = MagicMock()
    mock_nodes_result.mappings.return_value = [
        {"fqn": "pkg.f1", "kind": "function", "file": "src/main.py"},
        {"fqn": "pkg.f2", "kind": "function", "file": "src/auth.py"},
        {"fqn": "pkg.f3", "kind": "function", "file": "src/db.py"}
    ]
    mock_edges_result = MagicMock()
    mock_edges_result.mappings.return_value = [
        {"from_fqn": "pkg.f1", "to_fqn": "pkg.f2"},
        {"from_fqn": "pkg.f2", "to_fqn": "pkg.f3"} # this shouldn't be included if focus is pkg.f1 and depth is 1
    ]

    mock_execute.side_effect = [mock_nodes_result, mock_edges_result]

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/graph?version=sha-123&level=all&focus_symbol=pkg.f1")
        assert response.status_code == 200
        data = response.json()

        # Only nodes and edges within radial depth 1 of pkg.f1
        assert "nodes" in data
        assert "edges" in data
        assert {n["id"] for n in data["nodes"]} == {"pkg.f1", "pkg.f2"}
        assert len(data["edges"]) == 1
        assert data["edges"][0] == {"source": "pkg.f1", "target": "pkg.f2", "type": "calls"}

    finally:
        app.dependency_overrides.clear()
