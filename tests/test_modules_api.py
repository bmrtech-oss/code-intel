import os
import pytest
import importlib
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from code_intel.api.server import app
from code_intel.core.storage import get_db

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    # Set the DATABASE_URL environment variable to a sqlite db
    db_file = tmp_path / "test_api_modules.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # Backup existing environment variable
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url

    # Reload settings and models modules to apply settings
    import code_intel.settings
    importlib.reload(code_intel.settings)

    import code_intel.core.models
    importlib.reload(code_intel.core.models)

    yield db_url

    # Restore environment and reload modules back to original state
    if old_db_url is not None:
        os.environ["DATABASE_URL"] = old_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    import code_intel.settings
    importlib.reload(code_intel.settings)
    import code_intel.core.models
    importlib.reload(code_intel.core.models)

@pytest.mark.asyncio
async def test_modules_api_integration(setup_test_db):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from code_intel.core.models import Base

    # Create an async engine and tables for local test session
    engine = create_async_engine(setup_test_db)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Create sessionmaker
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with async_session() as session:
            yield session

    # Override database dependency in FastAPI app
    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        # 1. POST /api/modules/draft -> Create Draft
        payload = {
            "module_path": "code_intel/api/server.py",
            "extracted_json": {
                "business_rules": ["rule 1"],
                "edge_cases": ["case 1"],
                "data_transformations": ["trans 1"],
                "side_effects": ["side 1"]
            },
            "git_sha": "sha_001"
        }
        response = client.post("/api/modules/draft", json=payload)
        assert response.status_code == 200
        data = response.json()
        ma_id = data["id"]
        assert data["module_path"] == "code_intel/api/server.py"
        assert data["status"] == "DRAFT"

        # 2. PUT /api/modules/{id}/draft -> Update Draft
        update_payload = {
            "new_json": {
                "business_rules": ["rule 1", "rule 2"],
                "edge_cases": ["case 1", "case 2"]
            }
        }
        update_resp = client.put(f"/api/modules/{ma_id}/draft", json=update_payload)
        assert update_resp.status_code == 200

        # 3. GET /api/modules/{id}/history -> Retrieve History
        history_resp = client.get(f"/api/modules/{ma_id}/history")
        assert history_resp.status_code == 200
        history_data = history_resp.json()
        assert len(history_data) == 1
        assert history_data[0]["version_num"] == 1
        assert history_data[0]["business_rules"] == ["rule 1", "rule 2"]

        # 4. PATCH /api/modules/{id}/status -> Promote draft to REVIEWED
        promote_resp = client.patch(f"/api/modules/{ma_id}/status")
        assert promote_resp.status_code == 200
        promote_data = promote_resp.json()
        assert promote_data["status"] == "REVIEWED"

        # Verify that a second version snapshot is created in history
        history_resp2 = client.get(f"/api/modules/{ma_id}/history")
        assert history_resp2.status_code == 200
        history_data2 = history_resp2.json()
        assert len(history_data2) == 2
        assert history_data2[0]["version_num"] == 1
        assert history_data2[1]["version_num"] == 2
        assert history_data2[1]["business_rules"] == ["rule 1", "rule 2"]

        # Attempt to update draft when in REVIEWED (should fail with 400 ValueError)
        fail_update = client.put(f"/api/modules/{ma_id}/draft", json=update_payload)
        assert fail_update.status_code == 400
        assert "DRAFT" in fail_update.json()["detail"]

        # 5. PATCH /api/modules/{id}/link -> Link module safely
        link_payload = {
            "new_file_path": "code_intel/core/models.py"
        }
        link_resp = client.patch(f"/api/modules/{ma_id}/link", json=link_payload)
        assert link_resp.status_code == 200
        assert link_resp.json()["module_path"] == "code_intel/core/models.py"

        # Attempt to link using unsafe traversal path (should fail with 400)
        unsafe_link_payload = {
            "new_file_path": "/etc/passwd"
        }
        unsafe_link_resp = client.patch(f"/api/modules/{ma_id}/link", json=unsafe_link_payload)
        assert unsafe_link_resp.status_code == 400
        assert "unsafe" in unsafe_link_resp.json()["detail"].lower()

        # 6. GET /api/modules/dashboard -> Heatmap Dashboard
        dashboard_resp = client.get("/api/modules/dashboard")
        assert dashboard_resp.status_code == 200
        dashboard_data = dashboard_resp.json()
        assert len(dashboard_data) == 1
        assert dashboard_data[0]["module_path"] == "code_intel/core/models.py"
        assert dashboard_data[0]["status"] == "REVIEWED"

    finally:
        # Clear dependencies override and dispose
        app.dependency_overrides.clear()
        await engine.dispose()
