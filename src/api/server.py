import re
import uuid
import json
from ..utils.traceability import fuzzy_match_symbols
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.storage import VersionedStorage, get_db, engine
from ..core.models import Base
from ..core.dataflow import DataflowEngine
from ..core.rules import RuleEngine
from ..core.udf import LLMUDF
from ..core.git_handler import GitRepoHandler
from ..worker.tasks import queue, run_ingestion

app = FastAPI(title="Code Intelligence Platform (Prod)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_git_url(path: str) -> bool:
    """Check if the path is a Git repository URL."""
    return bool(re.match(r'^(https?://|git@)', path))

def extract_json(text: str):
    # Try to parse as is
    try:
        return json.loads(text)
    except:
        pass
    # Remove markdown fences
    cleaned = re.sub(r'^```json\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except:
        pass
    # Find the outermost JSON object/array
    brace_count = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if brace_count == 0:
                start = i
            brace_count += 1
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0 and start is not None:
                candidate = text[start:i+1]
                try:
                    return json.loads(candidate)
                except:
                    continue
    # Fallback: return raw text
    return {"raw": text, "error": "Could not parse JSON", "truncated": True}

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Create views for symbols and calls
        await conn.execute(text("DROP VIEW IF EXISTS current_symbols CASCADE"))
        await conn.execute(text("""
            CREATE VIEW current_symbols AS
            SELECT 
                entity_id AS symbol_id,
                version,
                MAX(CASE WHEN attribute = 'name' THEN value END) AS name,
                MAX(CASE WHEN attribute = 'kind' THEN value END) AS kind,
                MAX(CASE WHEN attribute = 'file' THEN value END) AS file,
                MAX(CASE WHEN attribute = 'line' THEN value END) AS line
            FROM facts
            WHERE entity_type = 'symbol' AND valid_to IS NULL
            GROUP BY entity_id, version
        """))
        await conn.execute(text("DROP VIEW IF EXISTS current_calls CASCADE"))
        await conn.execute(text("""
            CREATE VIEW current_calls AS
            SELECT 
                entity_id AS call_id,
                version,
                MAX(CASE WHEN attribute = 'caller' THEN value END) AS caller,
                MAX(CASE WHEN attribute = 'callee' THEN value END) AS callee,
                MAX(CASE WHEN attribute = 'confidence' THEN value END) AS confidence
            FROM facts
            WHERE entity_type = 'call' AND valid_to IS NULL
            GROUP BY entity_id, version
        """))

class AnalyzeRequest(BaseModel):
    repo_path: str
    version: Optional[str] = None
    branch: Optional[str] = None

class QueryRequest(BaseModel):
    rule: str
    version: Optional[str] = None
    symbol: Optional[str] = None
    depth: Optional[int] = 3

@app.post("/analyze")
async def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    version = req.version or str(int(datetime.utcnow().timestamp()))
    storage = VersionedStorage(db)
    actual_path = req.repo_path
    temp_handler = None
    if is_git_url(req.repo_path):
        temp_handler = GitRepoHandler(req.repo_path, req.branch)
        actual_path = temp_handler.clone()
        background_tasks.add_task(temp_handler.cleanup)
    job = queue.enqueue(run_ingestion, actual_path, version)
    return {"status": "indexing started", "version": version, "job_id": job.id}

@app.get("/status/{job_id}")
async def status(job_id: str):
    job = queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": job.get_status(), "result": job.result if job.is_finished else None}

@app.post("/query")
async def query(req: QueryRequest, db: AsyncSession = Depends(get_db)):
    storage = VersionedStorage(db)
    version = req.version or await storage.get_current_version()
    if not version:
        raise HTTPException(status_code=400, detail="No version found")
    dataflow = DataflowEngine(storage)
    rules = RuleEngine(storage, dataflow)
    try:
        result = await rules.evaluate_rule(req.rule, version, symbol=req.symbol, depth=req.depth)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/requirements/stream")
async def requirements_stream(version: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    storage = VersionedStorage(db)
    version = version or await storage.get_current_version()
    if not version:
        raise HTTPException(status_code=400, detail="No version found")
    symbols = await storage.execute_query("SELECT * FROM current_symbols WHERE version = :v", {"v": version})
    calls = await storage.execute_query("SELECT * FROM current_calls WHERE version = :v", {"v": version})
    udf = LLMUDF()

    async def event_generator():
        full_response = ""
        # We'll collect the full response first, then extract first JSON
        async for token in udf.generate_requirements_stream(symbols, calls):
            full_response += token
            # yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'token': token, 'partial': full_response})}\n\n"

        # ---- NEW: extract only the first complete JSON object ----
        def extract_first_json(text: str) -> str:
            brace_count = 0
            start = None
            for i, ch in enumerate(text):
                if ch == '{':
                    if brace_count == 0:
                        start = i
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0 and start is not None:
                        return text[start:i+1]
            return None

        json_part = extract_first_json(full_response)
        if json_part:
            cleaned = json_part
        else:
            cleaned = full_response

        # Parse and store traceability
        try:
            req_json = json.loads(cleaned)
        except json.JSONDecodeError:
            # fallback: use extract_json
            req_json = extract_json(cleaned)
            if "error" in req_json:
                req_json = {"raw": full_response, "error": "JSON parse failed"}

        traceability_stored = False
        if "tasks" in req_json and isinstance(req_json["tasks"], list):
            for task in req_json["tasks"]:
                trace_list = task.get("traceability", [])
                if not trace_list:
                    trace_list = fuzzy_match_symbols(task.get("text", ""), symbols)
                for symbol_id in trace_list:
                    epic = req_json.get("epic", "UNKNOWN")
                    req_id = f"{epic[:20]}_{task.get('text', 'TASK')[:20]}".replace(" ", "_")
                    await db.execute(
                        text("""
                            INSERT INTO requirement_traceability (requirement_id, symbol_id, confidence)
                            VALUES (:rid, :sid, 1.0)
                            ON CONFLICT (requirement_id, symbol_id) DO NOTHING
                        """),
                        {"rid": req_id, "sid": symbol_id}
                    )
                traceability_stored = True
            await db.commit()

        yield f"data: {json.dumps({'done': True, 'traceability_stored': traceability_stored})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/requirements")
async def requirements(version: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    storage = VersionedStorage(db)
    version = version or await storage.get_current_version()
    if not version:
        raise HTTPException(status_code=400, detail="No version found")
    symbols = await storage.execute_query("SELECT * FROM current_symbols WHERE version = :v", {"v": version})
    calls = await storage.execute_query("SELECT * FROM current_calls WHERE version = :v", {"v": version})
    udf = LLMUDF()
    req_text = await udf.generate_requirements(symbols, calls)

    req_json = extract_json(req_text)

    if "tasks" in req_json and isinstance(req_json["tasks"], list):
        for task in req_json["tasks"]:
            if "traceability" in task and isinstance(task["traceability"], list):
                for symbol_id in task["traceability"]:
                    epic = req_json.get("epic", "UNKNOWN")
                    req_id = f"{epic[:20]}_{task.get('text', 'TASK')[:20]}".replace(" ", "_")
                    await db.execute(
                        text("""
                            INSERT INTO requirement_traceability (requirement_id, symbol_id, confidence)
                            VALUES (:rid, :sid, 1.0)
                            ON CONFLICT (requirement_id, symbol_id) DO NOTHING
                        """),
                        {"rid": req_id, "sid": symbol_id}
                    )
        await db.commit()

    return {"requirements": req_json}

@app.get("/trace/{requirement_id}")
async def get_traceability(requirement_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT DISTINCT s.symbol_id, s.name, s.kind, s.file
            FROM requirement_traceability rt
            JOIN current_symbols s ON rt.symbol_id = s.symbol_id
            WHERE rt.requirement_id = :rid
        """),
        {"rid": requirement_id}
    )
    symbols = [dict(row) for row in result.mappings()]
    return {"requirement_id": requirement_id, "symbols": symbols}