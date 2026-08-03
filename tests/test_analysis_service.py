import os
import pytest
import importlib
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from code_intel.services.analysis_service import AnalysisService

@pytest.mark.asyncio
async def test_analysis_service_workflow(tmp_path):
    # Set the DATABASE_URL environment variable to a sqlite db
    db_file = tmp_path / "test_service.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # Backup existing environment variable
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url

    try:
        # Reload settings and models modules to apply settings
        import code_intel.settings
        importlib.reload(code_intel.settings)

        import code_intel.core.models
        importlib.reload(code_intel.core.models)

        from code_intel.core.models import Base

        # Create an async engine and tables
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        # Create sessionmaker
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            service = AnalysisService(session)

            # 1. Test create_draft
            extracted_json = {
                "business_rules": ["rule A"],
                "edge_cases": ["case A"],
                "data_transformations": ["trans A"],
                "side_effects": ["side A"]
            }
            ma = await service.create_draft("code_intel/api/server.py", extracted_json, "commit123")
            ma_id = ma.id
            assert ma_id is not None
            assert ma.status == "DRAFT"
            assert ma.module_path == "code_intel/api/server.py"

            # 2. Verify initial version exists
            history = await service.get_version_history(ma_id)
            assert len(history) == 1
            assert history[0].version_num == 1
            assert history[0].business_rules == ["rule A"]

            # 3. Test update_draft
            new_json = {
                "business_rules": ["rule A", "rule B"],
                "edge_cases": ["case A", "case B"]
            }
            ma = await service.update_draft(ma_id, new_json)

            # Verify update applied to current version (no new version created)
            history2 = await service.get_version_history(ma_id)
            assert len(history2) == 1
            assert history2[0].version_num == 1
            assert history2[0].business_rules == ["rule A", "rule B"]
            assert history2[0].edge_cases == ["case A", "case B"]

            # 4. Test promote_to_review
            ma = await service.promote_to_review(ma_id)
            assert ma.status == "REVIEWED"

            # Verify that promote created a new frozen snapshot version
            history3 = await service.get_version_history(ma_id)
            assert len(history3) == 2
            assert history3[0].version_num == 1
            assert history3[1].version_num == 2
            assert history3[1].business_rules == ["rule A", "rule B"]

            # 5. Test update_draft on non-DRAFT (should fail)
            with pytest.raises(ValueError, match="Only analyses in DRAFT status can be updated"):
                await service.update_draft(ma_id, {"business_rules": ["rule C"]})

            # 6. Test link_to_new_module (Success)
            ma = await service.link_to_new_module(ma_id, "code_intel/core/models.py")
            assert ma.module_path == "code_intel/core/models.py"

            # 7. Test link_to_new_module (Failure/Path Traversal)
            with pytest.raises(ValueError, match="Unauthorized or unsafe new file path"):
                await service.link_to_new_module(ma_id, "/etc/passwd")

        await engine.dispose()

    finally:
        # Restore environment and reload modules back to original state
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        import code_intel.settings
        importlib.reload(code_intel.settings)
        import code_intel.core.models
        importlib.reload(code_intel.core.models)
