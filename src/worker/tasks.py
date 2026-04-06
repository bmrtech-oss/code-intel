import os
import asyncio
from redis import Redis
from rq import Queue
from ..core.storage import VersionedStorage, AsyncSessionLocal
from ..core.ingestion import IngestionPipeline

redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379)
queue = Queue("ingestion", connection=redis_conn)

async def _run_ingestion(repo_path: str, version: str):
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        pipeline = IngestionPipeline(storage)
        await pipeline.walk_and_parse(repo_path, version)
        await session.commit()

# def run_ingestion(repo_path: str, version: str):
#     asyncio.run(_run_ingestion(repo_path, version))

def run_ingestion(repo_path: str, version: str, is_git_url: bool = False, branch: str = None):
    actual_path = repo_path
    temp_handler = None
    try:
        if is_git_url:
            from ..core.git_handler import GitRepoHandler
            temp_handler = GitRepoHandler(repo_path, branch)
            actual_path = temp_handler.clone()
        # ... run ingestion on actual_path ...
        asyncio.run(_run_ingestion(actual_path, version))
    finally:
        if temp_handler:
            temp_handler.cleanup()