import re
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
from ..core.storage import VersionedStorage, get_db, engine, AsyncSessionLocal, EXTRACTOR_VERSION, MODEL
from ..core.models import Base
from ..core.dataflow import DataflowEngine
from ..core.rules import RuleEngine
from ..core.udf import LLMUDF
from ..core.git_handler import GitRepoHandler
from ..worker.tasks import queue, llm_queue, run_ingestion, generate_requirements_task

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
    # With Ollama grammar, we expect valid JSON directly.
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Fallback to finding the first JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        # Try json_repair as a last resort
        try:
            from json_repair import repair_json
            return json.loads(repair_json(text))
        except:
            pass
    
    return {"raw": text, "error": "Could not parse JSON"}

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # Handle schema versioning and deprecation
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        current_schema = await storage.get_schema_version()
        if current_schema != EXTRACTOR_VERSION:
            print(f"Schema version mismatch ({current_schema} != {EXTRACTOR_VERSION}). Deprecating old facts.")
            await storage.deprecate_old_extractor_facts()
            await storage.set_schema_version(EXTRACTOR_VERSION)
            await session.commit()

    async with engine.begin() as conn:
        # Create views for symbols and calls
        cascade = "CASCADE" if engine.dialect.name == "postgresql" else ""
        await conn.execute(text(f"DROP VIEW IF EXISTS current_symbols {cascade}"))
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
        await conn.execute(text(f"DROP VIEW IF EXISTS current_calls {cascade}"))
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
    commit_sha: Optional[str] = None
    symbol: Optional[str] = None
    depth: Optional[int] = 3

@app.post("/analyze")
async def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    from ..settings import USE_TEMPORAL
    version = req.version or str(int(datetime.utcnow().timestamp()))
    actual_path = req.repo_path
    temp_handler = None
    if is_git_url(req.repo_path):
        temp_handler = GitRepoHandler(req.repo_path, req.branch)
        actual_path = temp_handler.clone()
        background_tasks.add_task(temp_handler.cleanup)
    
    if USE_TEMPORAL:
        from ..worker.tasks import run_temporal_ingestion
        # Temporal is durable and handles its own queue
        background_tasks.add_task(run_temporal_ingestion, actual_path, version)
        return {"status": "temporal indexing started", "version": version, "job_id": f"ingest-{version}"}
    else:
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
    from ..settings import USE_BITEMPORAL
    
    storage = VersionedStorage(db)
    version = req.commit_sha or req.version or await storage.get_current_version()
    if not version:
        raise HTTPException(status_code=400, detail="No version or commit_sha found")

    # Use BiTemporalAdapter if enabled
    if USE_BITEMPORAL:
        from ..mcp.server import adapter as mcp_adapter, init_topological_stack
        await init_topological_stack()
        adapter = mcp_adapter

        if adapter:
            if req.rule in ("query_call_graph", "transitive_calls"):
                result = await adapter.get_calls(version, caller_fqn=req.symbol)
                return {"result": result}
            elif req.rule == "dead_code":
                all_symbols = await adapter.get_symbols(version, filters={"kind": "function"})
                all_calls = await adapter.get_calls(version)
                called_fqns = {c["to"] for c in all_calls}
                result = [s for s in all_symbols if s["fqn"] not in called_fqns]
                return {"result": result}
            elif req.rule == "impact":
                result = await adapter.get_transitive_dependencies(version, req.symbol, max_depth=req.depth or 3)
                return {"result": list(result)}
            elif req.rule == "predict_impact":
                from ..mcp import server as mcp_mod
                if mcp_mod.impact_predictor:
                    result = await mcp_mod.impact_predictor.predict_blast_radius(req.symbol, version)
                    return {"result": result}
                else:
                    raise HTTPException(status_code=503, detail="Impact predictor not initialized")
            elif req.rule == "verify_impact":
                from ..mcp import server as mcp_mod
                # Handle verify_impact via API (calls the same logic as MCP)
                if mcp_mod.impact_predictor:
                    impact = await mcp_mod.impact_predictor.predict_blast_radius(req.symbol, version)
                    test_files = impact.get("affected_tests", [])
                    
                    if not test_files:
                        return {"result": {"status": "warning", "message": "No relevant tests found.", "impact": impact}}

                    import subprocess
                    results = []
                    for test_file in test_files:
                        try:
                            process = subprocess.run(["uv", "run", "pytest", test_file], capture_output=True, text=True, timeout=60)
                            results.append({"file": test_file, "passed": process.returncode == 0, "stdout": process.stdout[-500:], "stderr": process.stderr[-500:]})
                        except Exception as e:
                            results.append({"file": test_file, "error": str(e)})

                    return {"result": {"status": "success" if all(r.get("passed", False) for r in results) else "failure", "test_results": results, "impact": impact}}
                else:
                    raise HTTPException(status_code=503, detail="Impact predictor not initialized")

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

    async def event_generator():
        full_response = ""
        # We'll collect the full response first, then extract first JSON
        async for token in udf.generate_requirements_stream(symbols, calls):
            full_response += token
            # yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'token': token, 'partial': full_response})}\n\n"

        # Parse and store traceability
        try:
            req_json = json.loads(full_response)
            cleaned = full_response
        except json.JSONDecodeError:
            # fallback: use extract_json
            req_json = extract_json(full_response)
            cleaned = json.dumps(req_json)
            if "error" in req_json:
                req_json = {"raw": full_response, "error": "JSON parse failed"}

        # Store provenance data
        grounded_in = [s["id"] for s in symbols if "id" in s] + [c["id"] for c in calls if "id" in c]
        is_verified, confidence = udf.validate_artifact(req_json, symbols, calls)

        await storage.insert_llm_artifact(
            artifact_type="requirement",
            value=cleaned,
            version=version,
            grounded_in=grounded_in,
            prompt=udf.handler.build_prompt(symbols, calls),
            model=MODEL,
            is_verified=is_verified,
            confidence=confidence
        )

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

@app.post("/requirements", status_code=202)
async def requirements(version: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    storage = VersionedStorage(db)
    version = version or await storage.get_current_version()
    if not version:
        raise HTTPException(status_code=400, detail="No version found")
    
    job = llm_queue.enqueue(generate_requirements_task, version)
    return {"job_id": job.id, "status": "pending"}

@app.get("/requirements/status/{job_id}")
async def requirements_status(job_id: str):
    job = llm_queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.is_finished:
        return {"status": "completed", "result": job.result}
    elif job.is_failed:
        return {"status": "failed", "error": str(job.exc_info)}
    else:
        return {"status": job.get_status()}

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

@app.get("/search")
async def search(q: str, limit: int = 5):
    from ..mcp import server as mcp_server
    await mcp_server.init_topological_stack()
    if mcp_server.semantic_search_engine:
        results = await mcp_server.semantic_search_engine.search(q, limit)
        return {"results": results}
    else:
        raise HTTPException(status_code=503, detail="Semantic search engine not initialized")

@app.get("/analytics/predict-impact")
async def predict_impact(symbol: str, commit_sha: Optional[str] = None):
    from ..mcp import server as mcp_server
    await mcp_server.init_topological_stack()
    version = commit_sha
    if not version:
        # Get active SHA
        from ..mcp.server import workspace_manager
        version = await workspace_manager.get_active_sha()
    
    if not version:
        raise HTTPException(status_code=400, detail="No commit_sha available")

    if mcp_server.impact_predictor:
        result = await mcp_server.impact_predictor.predict_blast_radius(symbol, version)
        return result
    else:
        raise HTTPException(status_code=503, detail="Impact predictor not initialized")

@app.get("/debug/dependents/{fact_id}")
async def get_dependents(fact_id: int, is_derived: bool = False, db: AsyncSession = Depends(get_db)):
    storage = VersionedStorage(db)
    result = await storage.get_dependents(fact_id, is_derived)
    return {"fact_id": fact_id, "dependents": result}

@app.get("/debug/provenance/{fact_id}")
async def get_provenance(fact_id: int, db: AsyncSession = Depends(get_db)):
    storage = VersionedStorage(db)
    result = await storage.get_artifacts_by_fact(fact_id)
    return {"fact_id": fact_id, "artifacts": result}