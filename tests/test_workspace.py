import pytest
from code_intel.core.workspace import WorkspaceManager

# Skip tests if Redis is not available
REDIS_AVAILABLE = False # Default to False, will try to check

@pytest.mark.asyncio
async def test_workspace_manager():
    # Note: This test requires a running Redis instance.
    # In a real CI environment, we'd use a mock or a service.
    # For now, we'll try to connect and skip if it fails.
    wm = WorkspaceManager()
    try:
        await wm.redis.ping()
    except Exception:
        pytest.skip("Redis not available")

    workspace_id = "test-workspace"
    branch = "main"
    sha = "abc123def"
    ancestors = ["feat1", "base"]

    await wm.set_session(workspace_id, branch, sha, ancestors)
    
    session = await wm.get_session(workspace_id)
    assert session["current_branch"] == branch
    assert session["current_sha"] == sha
    assert session["ancestor_shas"] == ancestors

    active_sha = await wm.get_active_sha()
    assert active_sha == sha

    await wm.close()
