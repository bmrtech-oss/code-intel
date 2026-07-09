import asyncio
import sys
from sqlalchemy import text
from src.core.storage import VersionedStorage, AsyncSessionLocal

async def rebuild_all_versions():
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        # Get all versions from facts
        res = await session.execute(text("SELECT DISTINCT version FROM facts"))
        versions = [row[0] for row in res.all()]
        
        print(f"Found {len(versions)} versions to rebuild.")
        for v in versions:
            print(f"Rebuilding index for version: {v}")
            await storage.rebuild_read_model(v)
        
        await session.commit()
        print("Done.")

async def rebuild_specific_version(version: str):
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        print(f"Rebuilding index for version: {version}")
        await storage.rebuild_read_model(version)
        await session.commit()
        print("Done.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(rebuild_specific_version(sys.argv[1]))
    else:
        asyncio.run(rebuild_all_versions())
