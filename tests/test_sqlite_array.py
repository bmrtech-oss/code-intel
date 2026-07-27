import sys
import os
import pytest
import importlib
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.mark.asyncio
async def test_sqlite_array_serialization(tmp_path):
    # Set the DATABASE_URL environment variable to a sqlite db
    db_file = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # Backup existing environment variable
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url

    try:
        # Reload settings and models modules to apply the SQLite fallback path
        import code_intel.settings
        importlib.reload(code_intel.settings)

        import code_intel.core.models
        importlib.reload(code_intel.core.models)

        # Verify that ARRAY is our custom SQLiteArray under sqlite environment
        from code_intel.core.models import ARRAY, Base, DerivedFact

        # Create an async engine and tables
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            # Drop tables if they exist and create them
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        # Create sessionmaker
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Insert a DerivedFact with array fields
        async with async_session() as session:
            df = DerivedFact(
                fact_type="test_type",
                entity_id="test_entity",
                value="test_val",
                version="v1",
                extractor_version="1.0.0",
                depends_on=[101, 102, 103],
                depends_on_derived=[201, 202]
            )
            session.add(df)
            await session.commit()

        # Query it back and assert
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(DerivedFact).where(DerivedFact.fact_type == "test_type"))
            retrieved = result.scalar_one()

            assert retrieved.depends_on == [101, 102, 103]
            assert retrieved.depends_on_derived == [201, 202]

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
