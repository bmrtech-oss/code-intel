import os
import pytest
import importlib
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

@pytest.mark.asyncio
async def test_module_analysis_lifecycle_persistence(tmp_path):
    # Set the DATABASE_URL environment variable to a sqlite db
    db_file = tmp_path / "test_lifecycle.db"
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

        from code_intel.core.models import Base, ModuleAnalysis, AnalysisVersion

        # Create an async engine and tables
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        # Create sessionmaker
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # 1. Insert a ModuleAnalysis and an AnalysisVersion snapshot
        async with async_session() as session:
            ma = ModuleAnalysis(
                module_path="code_intel/api/server.py",
                status="DRAFT"
            )
            session.add(ma)
            await session.flush() # populated id

            av = AnalysisVersion(
                module_analysis_id=ma.id,
                git_commit_sha="commit_sha_1234567890",
                version_num=1,
                business_rules={"rule1": "invariant validation", "rule2": "path check"},
                edge_cases={"empty_input": "return null", "null_bytes": "raise exception"},
                data_transformations={"input": "bytes", "output": "JSON"},
                side_effects={"logging": "emits diagnostic logs"}
            )
            session.add(av)
            await session.commit()

        # 2. Query back and verify persistence & JSON structures
        async with async_session() as session:
            # Query ModuleAnalysis and verify relations
            result_ma = await session.execute(
                select(ModuleAnalysis).where(ModuleAnalysis.module_path == "code_intel/api/server.py")
            )
            retrieved_ma = result_ma.scalar_one()
            assert retrieved_ma.status == "DRAFT"

            # Query AnalysisVersion
            result_av = await session.execute(
                select(AnalysisVersion).where(AnalysisVersion.module_analysis_id == retrieved_ma.id)
            )
            retrieved_av = result_av.scalar_one()
            assert retrieved_av.git_commit_sha == "commit_sha_1234567890"
            assert retrieved_av.version_num == 1
            assert retrieved_av.business_rules == {"rule1": "invariant validation", "rule2": "path check"}
            assert retrieved_av.edge_cases == {"empty_input": "return null", "null_bytes": "raise exception"}
            assert retrieved_av.data_transformations == {"input": "bytes", "output": "JSON"}
            assert retrieved_av.side_effects == {"logging": "emits diagnostic logs"}

        # 3. Test cascade deletion
        async with async_session() as session:
            # Delete ModuleAnalysis
            result_ma = await session.execute(
                select(ModuleAnalysis).where(ModuleAnalysis.module_path == "code_intel/api/server.py")
            )
            retrieved_ma = result_ma.scalar_one()
            await session.delete(retrieved_ma)
            await session.commit()

        # Verify that AnalysisVersion is cascade-deleted automatically
        async with async_session() as session:
            result_av_check = await session.execute(
                select(AnalysisVersion).where(AnalysisVersion.git_commit_sha == "commit_sha_1234567890")
            )
            deleted_av = result_av_check.scalar_one_or_none()
            assert deleted_av is None

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
