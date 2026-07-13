import os
import asyncio
from redis import Redis
from rq import Queue
from temporalio import workflow, activity
from temporalio.client import Client
from datetime import timedelta
from ..core.storage import VersionedStorage, AsyncSessionLocal
from ..core.ingestion import IngestionPipeline

redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379)
queue = Queue("ingestion", connection=redis_conn)
llm_queue = Queue("llm", connection=redis_conn)

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

async def _generate_requirements_task(version: str):
    from ..core.udf import LLMUDF
    import json
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        
        # Fetch fact IDs and metadata for grounding
        symbols = await storage.execute_query("""
            SELECT f.id, s.symbol_id, s.version, s.name, s.kind, s.file, s.line
            FROM current_symbols s
            JOIN facts f ON s.symbol_id = f.entity_id AND s.version = f.version AND f.attribute = 'kind'
            WHERE s.version = :v AND f.valid_to IS NULL
        """, {"v": version})
        calls = await storage.execute_query("""
            SELECT f.id, c.call_id, c.version, c.caller, c.callee, c.confidence
            FROM current_calls c
            JOIN facts f ON c.call_id = f.entity_id AND c.version = f.version AND f.attribute = 'callee'
            WHERE c.version = :v AND f.valid_to IS NULL
        """, {"v": version})
        
        udf = LLMUDF()
        response = await udf.generate_requirements(symbols, calls)
        req_json = response["result"]
        provenance = response["provenance"]

        # Store LLM Artifact
        await storage.insert_llm_artifact(
            artifact_type="requirement",
            value=json.dumps(req_json),
            version=version,
            grounded_in=provenance["grounded_in"],
            prompt=provenance["prompt"],
            model=provenance["model"],
            is_verified=provenance["is_verified"],
            confidence=provenance["confidence"]
        )

        if "tasks" in req_json and isinstance(req_json["tasks"], list):
            from ..utils.traceability import fuzzy_match_symbols
            for task in req_json["tasks"]:
                trace_list = task.get("traceability", [])
                if not trace_list:
                    trace_list = fuzzy_match_symbols(task.get("text", ""), symbols)
                
                for symbol_id in trace_list:
                    epic = req_json.get("epic", "UNKNOWN")
                    req_id = f"{epic[:20]}_{task.get('text', 'TASK')[:20]}".replace(" ", "_")
                    await session.execute(
                        text("""
                            INSERT INTO requirement_traceability (requirement_id, symbol_id, confidence)
                            VALUES (:rid, :sid, 1.0)
                            ON CONFLICT (requirement_id, symbol_id) DO NOTHING
                        """),
                        {"rid": req_id, "sid": symbol_id}
                    )
            await session.commit()
        
        return {
            "requirements": req_json,
            "provenance": provenance
        }

def generate_requirements_task(version: str):
    return asyncio.run(_generate_requirements_task(version))

# --- Temporal Implementation ---

@activity.defn
async def walk_files_activity(root_path: str) -> list[str]:
    file_list = []
    for dirpath, _, filenames in os.walk(root_path):
        for fname in filenames:
            file_list.append(os.path.join(dirpath, fname))
    return file_list

@activity.defn
async def parse_file_activity(file_path: str, version: str):
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        pipeline = IngestionPipeline(storage)
        await pipeline.parse_file(file_path, version)
        await session.commit()

@workflow.defn
class IngestionWorkflow:
    @workflow.run
    async def run(self, repo_path: str, version: str):
        # 1. Walk Files
        files = await workflow.execute_activity(
            walk_files_activity,
            repo_path,
            start_to_close_timeout=timedelta(minutes=5)
        )
        
        # 2. Parallel Parsing (with retries and checkpointing)
        # For very large repos, we'd chunk these
        results = []
        for file_path in files:
            results.append(workflow.execute_activity(
                parse_file_activity,
                args=[file_path, version],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=workflow.RetryPolicy(maximum_attempts=3)
            ))
        
        await asyncio.gather(*results)
        return {"status": "completed", "files_processed": len(files)}

async def run_temporal_ingestion(repo_path: str, version: str):
    client = await Client.connect("temporal:7233")
    await client.execute_workflow(
        IngestionWorkflow.run,
        args=[repo_path, version],
        id=f"ingest-{version}",
        task_queue="ingestion-queue"
    )