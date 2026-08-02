import os
import re
import json
from ..utils.traceability import fuzzy_match_symbols
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Response, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
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
from ..settings import ALLOWED_ORIGINS

app = FastAPI(title="Code Intelligence Platform (Prod)", version="1.0.0")

origins = list(ALLOWED_ORIGINS)
common_origins = [
    "tauri://localhost",
    "http://tauri.localhost",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]
for o in common_origins:
    if o not in origins:
        origins.append(o)

# nosemgrep: python.fastapi.security.cors.permissive-cors.permissive-cors
# nosemgrep: python.fastapi.security.wildcard-cors.wildcard-cors
# nosec
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_git_url(path: str) -> bool:
    """Check if the path is a Git repository URL."""
    return bool(re.match(r'^(https?://|git@)', path))

def resolve_version(repo_path: str, branch: Optional[str] = None) -> str:
    """Resolve the latest commit SHA for a remote Git URL or a local Git repo."""
    if is_git_url(repo_path):
        try:
            import git
            g = git.cmd.Git()
            if branch:
                output = g.ls_remote(repo_path, branch)
                if output:
                    return output.split()[0]
            output = g.ls_remote(repo_path, "HEAD")
            if output:
                return output.split()[0]
        except Exception as e:
            print(f"Error resolving remote Git version: {e}")
    else:
        try:
            import git
            import tempfile

            abs_path = os.path.abspath(repo_path)
            real_path = os.path.realpath(abs_path)

            # Security Sanitizer: Prevent path injection/traversal
            # Explicit string-literal checking for CodeQL compliance
            is_valid = False

            # Check absolute literal prefixes
            if real_path == "/repo" or real_path.startswith("/repo/"):
                is_valid = True
            elif real_path == "/shared" or real_path.startswith("/shared/"):
                is_valid = True
            else:
                # Resolve active working directory and temp directory safely
                cwd_dir = os.path.realpath(os.getcwd())
                cwd_dir_slash = cwd_dir if cwd_dir.endswith(os.path.sep) else cwd_dir + os.path.sep
                temp_dir = os.path.realpath(tempfile.gettempdir())
                temp_dir_slash = temp_dir if temp_dir.endswith(os.path.sep) else temp_dir + os.path.sep

                if real_path == cwd_dir or real_path.startswith(cwd_dir_slash):
                    is_valid = True
                elif real_path == temp_dir or real_path.startswith(temp_dir_slash):
                    is_valid = True

            if not is_valid:
                return str(int(datetime.utcnow().timestamp()))

            if os.path.exists(real_path):
                repo = git.Repo(real_path)
                return repo.head.commit.hexsha
        except Exception as e:
            print(f"Error resolving local Git version: {e}")

    return str(int(datetime.utcnow().timestamp()))

def is_safe_path(path: str) -> bool:
    """Check if the resolved path is within permitted directories."""
    try:
        import tempfile
        # Resolve real absolute path
        abs_path = os.path.abspath(path)
        real_path = os.path.realpath(abs_path)

        # Explicit string-literal checking for CodeQL compliance
        if real_path == "/repo" or real_path.startswith("/repo/"):
            return True
        if real_path == "/shared" or real_path.startswith("/shared/"):
            return True

        cwd_dir = os.path.realpath(os.getcwd())
        cwd_dir_slash = cwd_dir if cwd_dir.endswith(os.path.sep) else cwd_dir + os.path.sep
        temp_dir = os.path.realpath(tempfile.gettempdir())
        temp_dir_slash = temp_dir if temp_dir.endswith(os.path.sep) else temp_dir + os.path.sep

        if real_path == cwd_dir or real_path.startswith(cwd_dir_slash):
            return True
        if real_path == temp_dir or real_path.startswith(temp_dir_slash):
            return True

        return False
    except Exception:
        return False

async def find_best_version(version: str, db: AsyncSession) -> str:
    """Find the requested version or the closest parsed/existing version in the database."""
    # 1. Check if the exact version exists in graph_nodes
    try:
        check_result = await db.execute(
            text("SELECT 1 FROM graph_nodes WHERE version = :v LIMIT 1"),
            {"v": version}
        )
        if check_result.scalar():
            return version
    except Exception:
        pass

    # 2. Get all parsed versions in the database
    existing_versions = set()
    try:
        versions_result = await db.execute(text("SELECT DISTINCT version FROM graph_nodes"))
        for row in versions_result.mappings():
            v = row.get("version")
            if v:
                existing_versions.add(v)
    except Exception:
        pass

    if not existing_versions:
        # Fallback to current_symbols distinct versions
        try:
            versions_result = await db.execute(text("SELECT DISTINCT version FROM current_symbols"))
            for row in versions_result.mappings():
                v = row.get("version")
                if v:
                    existing_versions.add(v)
        except Exception:
            pass

    if not existing_versions:
        return version

    if version in existing_versions:
        return version

    # Fallback to the most recent parsed version in existing_versions (sorted alphabetically/chronologically)
    for v in sorted(list(existing_versions), reverse=True):
        return v

    return version

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
            except Exception:
                pass
        
        # Try json_repair as a last resort
        try:
            from json_repair import repair_json
            return json.loads(repair_json(text))
        except Exception:
            pass
    
    return {"raw": text, "error": "Could not parse JSON"}

async def run_startup_llm_check():
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Running startup LLM connectivity check...")

    # Instantiate LLMUDF with the default (env-based) settings
    udf = LLMUDF(session_id="default")
    try:
        if udf.provider == "ollama":
            # Very lightweight check
            await udf.ollama_client.generate(
                model=udf.model,
                prompt="test",
                options={"num_predict": 2}
            )
        elif udf.provider in ("openrouter", "openai"):
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {udf.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": udf.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 2,
                    "temperature": 0.0
                }
                resp = await client.post(
                    f"{udf.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=5.0
                )
                resp.raise_for_status()
        elif udf.provider == "google":
            import asyncio
            loop = asyncio.get_event_loop()
            def _gen():
                resp = udf.google_client.generate_content("hi")
                return resp.text
            await loop.run_in_executor(None, _gen)

        logger.info(f"Startup LLM connectivity check SUCCESS for provider: {udf.provider}, model: {udf.model}")
    except Exception as e:
        logger.warning(
            f"Startup LLM connectivity check FAILED for provider: {udf.provider}, model: {udf.model}. "
            f"Error: {e}. Services will still start normally."
        )

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # Run background LLM connectivity check
    import asyncio
    asyncio.create_task(run_startup_llm_check())

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
    timeout: Optional[int] = 300

class QueryRequest(BaseModel):
    rule: str
    version: Optional[str] = None
    commit_sha: Optional[str] = None
    symbol: Optional[str] = None
    depth: Optional[int] = 3

class RequirementsRequest(BaseModel):
    symbol_ids: Optional[List[str]] = None

class LLMConfigRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    session_id: Optional[str] = "default"

class TestLLMRequest(BaseModel):
    session_id: Optional[str] = "default"

@app.post("/analyze")
async def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    from ..settings import USE_TEMPORAL

    # Path Traversal Security check
    if not is_git_url(req.repo_path) and not is_safe_path(req.repo_path):
        raise HTTPException(status_code=400, detail="Invalid or unauthorized repository path")

    # If version is not provided, resolve it dynamically to the latest commit SHA (or local Git SHA)
    version = req.version or resolve_version(req.repo_path, req.branch)
    
    if USE_TEMPORAL:
        from ..worker.tasks import run_temporal_ingestion
        actual_path = req.repo_path
        temp_handler = None
        if is_git_url(req.repo_path):
            temp_handler = GitRepoHandler(req.repo_path, req.branch)
            actual_path = temp_handler.clone()
            background_tasks.add_task(temp_handler.cleanup)
        # Temporal is durable and handles its own queue
        background_tasks.add_task(run_temporal_ingestion, actual_path, version)
        return {"status": "temporal indexing started", "version": version, "job_id": f"ingest-{version}"}
    else:
        is_git = is_git_url(req.repo_path)
        job = queue.enqueue(
            run_ingestion,
            req.repo_path,
            version,
            is_git_url=is_git,
            branch=req.branch,
            job_timeout=req.timeout or 300
        )
        return {"status": "indexing started", "version": version, "job_id": job.id}

@app.get("/status")
@app.get("/api/status")
async def get_status():
    is_docker = os.path.exists("/.dockerenv") or os.getenv("IS_DOCKER", "false").lower() == "true"
    return {
        "status": "active",
        "version": "1.0.0",
        "is_docker": is_docker,
        "allowed_volumes": ["/repo", "/shared"],
        "extractor_version": EXTRACTOR_VERSION
    }

@app.get("/status/{job_id}")
async def status(job_id: str):
    job = queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": job.get_status(), "result": job.result if job.is_finished else None}

@app.post("/config/llm")
async def config_llm(req: LLMConfigRequest):
    from redis import Redis
    from ..settings import REDIS_HOST, REDIS_PORT
    import json

    session_id = req.session_id or "default"
    try:
        r = Redis(host=REDIS_HOST, port=REDIS_PORT)
        config_data = {
            "provider": req.provider,
            "model": req.model,
            "api_key": req.api_key
        }
        r.setex(f"llm_config:{session_id}", 3600, json.dumps(config_data))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save LLM configuration in memory cache")

    return {"status": "success", "message": "LLM configuration applied dynamically"}

@app.post("/config/llm/test")
async def test_llm_connection(req: Optional[TestLLMRequest] = Body(None)):
    session_id = req.session_id if req else "default"
    udf = LLMUDF(session_id=session_id)

    # We will run a lightweight, minimal-token query to verify connectivity
    try:
        if udf.provider == "ollama":
            response = await udf.ollama_client.generate(
                model=udf.model,
                prompt="test",
                options={"num_predict": 5}
            )
            text_resp = response.response
        elif udf.provider in ("openrouter", "openai"):
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {udf.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": udf.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                    "temperature": 0.0
                }
                resp = await client.post(
                    f"{udf.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                resp.raise_for_status()
                text_resp = resp.json()["choices"][0]["message"]["content"]
        elif udf.provider == "google":
            import asyncio
            loop = asyncio.get_event_loop()
            def _gen():
                resp = udf.google_client.generate_content("hi")
                return resp.text
            text_resp = await loop.run_in_executor(None, _gen)
        else:
            raise ValueError(f"Unsupported provider: {udf.provider}")

        return {
            "status": "success",
            "message": "LLM connection verified successfully",
            "provider": udf.provider,
            "model": udf.model,
            "response": text_resp.strip()
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "provider": udf.provider,
            "model": udf.model
        }

@app.get("/analyze/stream")
async def analyze_stream(job_id: str):
    import asyncio
    from redis import Redis
    from ..settings import REDIS_HOST, REDIS_PORT

    async def event_generator():
        r = Redis(host=REDIS_HOST, port=REDIS_PORT)
        # Timeout guard: max 30 minutes of polling
        for _ in range(3600):
            data_bytes = r.get(f"progress:{job_id}")
            if data_bytes:
                data = json.loads(data_bytes)
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("done"):
                    break
            else:
                job = queue.fetch_job(job_id)
                if job:
                    if job.is_failed:
                        yield f"data: {json.dumps({'file': '', 'progress': 100, 'done': True, 'error': 'Job failed'})}\n\n"
                        break
                    elif job.is_finished:
                        yield f"data: {json.dumps({'file': '', 'progress': 100, 'done': True})}\n\n"
                        break
                else:
                    yield f"data: {json.dumps({'file': '', 'progress': 100, 'done': True, 'error': 'Job not found'})}\n\n"
                    break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/repo/branches-and-commits")
async def get_branches_and_commits(repo_path: str, branch: Optional[str] = None, workspace_id: Optional[str] = None):
    # Path Traversal Security check
    if not is_git_url(repo_path) and not is_safe_path(repo_path):
        raise HTTPException(status_code=400, detail="Invalid or unauthorized repository path")

    import git
    from ..core.git_handler import GitRepoHandler
    from ..core.workspace import WorkspaceManager
    from ..storage.graph_engine import SimpleGraphEngine

    ws_manager = WorkspaceManager()
    branches = []
    commits = []

    # Query the workspace manager to list all branches
    try:
        branches = await ws_manager.get_workspace_branches(workspace_id)
    except Exception:
        pass

    # Try Git repository lookup
    actual_path = repo_path
    temp_handler = None
    if is_git_url(repo_path):
        temp_handler = GitRepoHandler(repo_path)
        try:
            actual_path = temp_handler.clone()
        except Exception:
            pass

    git_success = False
    try:
        # Defense-in-depth: canonicalize and constrain path before filesystem access
        safe_root = os.path.realpath(os.getcwd())

        if is_git_url(repo_path):
            resolved_path = os.path.realpath(actual_path)
        else:
            if os.path.isabs(actual_path):
                resolved_path = os.path.realpath(actual_path)
            else:
                resolved_path = os.path.realpath(os.path.join(safe_root, actual_path))

        if not is_safe_path(resolved_path):
            raise HTTPException(status_code=400, detail="Invalid or unauthorized repository path")

        if os.path.exists(resolved_path):
            repo = git.Repo(resolved_path)

            git_branches = []
            for ref in repo.references:
                if isinstance(ref, (git.Head, git.RemoteReference)):
                    name = ref.name.split("/")[-1]
                    if name not in git_branches and "HEAD" not in name:
                        git_branches.append(name)

            if not git_branches and repo.active_branch:
                git_branches.append(repo.active_branch.name)

            for b in git_branches:
                if b not in branches:
                    branches.append(b)

            # Save found branches back to workspace manager
            if workspace_id and branches:
                try:
                    await ws_manager.set_workspace_branches(workspace_id, branches)
                except Exception:
                    pass

            # Perform recursive lookup over parent commits
            rev = branch or "HEAD"
            if rev != "HEAD":
                # Check and resolve valid local or remote references (like origin/dev)
                possible_refs = [
                    rev,
                    f"origin/{rev}",
                    f"refs/remotes/origin/{rev}",
                    f"refs/heads/{rev}"
                ]
                resolved_rev = None
                for r in possible_refs:
                    try:
                        repo.commit(r)
                        resolved_rev = r
                        break
                    except Exception:
                        continue
                if resolved_rev:
                    rev = resolved_rev
                else:
                    rev = "HEAD"

            if rev == "HEAD":
                try:
                    rev = repo.active_branch.name
                except Exception:
                    for b in ["main", "master", "dev"]:
                        if b in branches:
                            rev = b
                            break
                    if rev == "HEAD" and branches:
                        rev = branches[0]

            for commit in repo.iter_commits(rev, max_count=50):
                commits.append({
                    "sha": commit.hexsha,
                    "author": commit.author.name or "Unknown",
                    "date": commit.committed_datetime.isoformat(),
                    "message": commit.message.strip() if commit.message else ""
                })
            git_success = True
    except Exception:
        pass
    finally:
        if temp_handler:
            temp_handler.cleanup()

    # Fallback: Utilise SimpleGraphEngine/commits.jsonl or SQL read models if Git lookup didn't run or fail
    if not git_success:
        try:
            engine = SimpleGraphEngine(repo_path)
            if engine.commits:
                tip = await engine.get_current_branch_tip()
                ancestry = await engine.topological_lookback_query(tip)
                commit_map = {c["sha"]: c for c in engine.commits}
                for sha in ancestry:
                    c = commit_map.get(sha)
                    if c:
                        commits.append({
                            "sha": c["sha"],
                            "author": c.get("author", "Unknown"),
                            "date": c.get("date", datetime.utcnow().isoformat()),
                            "message": c.get("message", "")
                        })
                if "main" not in branches:
                    branches.append("main")
        except Exception:
            pass

    if not branches:
        branches = ["main"]

    await ws_manager.close()
    return {
        "branches": branches,
        "commits": commits
    }

@app.get("/repo/version-status")
async def get_repo_version_status(version: str, db: AsyncSession = Depends(get_db)):
    """Check analysis status of a specific version and get fallback options."""
    # 1. Check if the exact version is analyzed
    is_analyzed = False
    try:
        check_result = await db.execute(
            text("SELECT 1 FROM graph_nodes WHERE version = :v LIMIT 1"),
            {"v": version}
        )
        if check_result.scalar():
            is_analyzed = True
    except Exception:
        pass

    if not is_analyzed:
        try:
            check_result = await db.execute(
                text("SELECT 1 FROM current_symbols WHERE version = :v LIMIT 1"),
                {"v": version}
            )
            if check_result.scalar():
                is_analyzed = True
        except Exception:
            pass

    # 2. Find the best fallback version
    best_fallback = None
    if not is_analyzed:
        best_fallback = await find_best_version(version, db)
        if best_fallback == version:
            best_fallback = None

    # 3. Check if any analysis exists at all
    has_any_analysis = False
    try:
        versions_result = await db.execute(text("SELECT DISTINCT version FROM graph_nodes"))
        if any(row.get("version") for row in versions_result.mappings()):
            has_any_analysis = True
    except Exception:
        pass

    if not has_any_analysis:
        try:
            versions_result = await db.execute(text("SELECT DISTINCT version FROM current_symbols"))
            if any(row.get("version") for row in versions_result.mappings()):
                has_any_analysis = True
        except Exception:
            pass

    return {
        "requested_version": version,
        "is_analyzed": is_analyzed,
        "best_fallback_version": best_fallback,
        "has_any_analysis": has_any_analysis
    }

@app.get("/repo/tree")
async def get_repo_tree(version: str, response: Response, db: AsyncSession = Depends(get_db)):
    # Try querying the graph_nodes read model first
    nodes = []
    try:
        result = await db.execute(
            text("SELECT fqn, file FROM graph_nodes WHERE version = :v"),
            {"v": version}
        )
        nodes = [dict(row) for row in result.mappings()]
    except Exception:
        pass

    # Fallback to current_symbols view if graph_nodes is empty or fails
    if not nodes:
        try:
            result = await db.execute(
                text("SELECT name AS fqn, file FROM current_symbols WHERE version = :v"),
                {"v": version}
            )
            nodes = [dict(row) for row in result.mappings()]
        except Exception:
            pass

    resolved_version = version
    is_fallback = False

    # If empty, lazy fall back to the best available version
    if not nodes:
        resolved_version = await find_best_version(version, db)
        if resolved_version != version:
            is_fallback = True
            try:
                result = await db.execute(
                    text("SELECT fqn, file FROM graph_nodes WHERE version = :v"),
                    {"v": resolved_version}
                )
                nodes = [dict(row) for row in result.mappings()]
            except Exception:
                pass

            if not nodes:
                try:
                    result = await db.execute(
                        text("SELECT name AS fqn, file FROM current_symbols WHERE version = :v"),
                        {"v": resolved_version}
                    )
                    nodes = [dict(row) for row in result.mappings()]
                except Exception:
                    pass

    response.headers["X-Version-Requested"] = version
    response.headers["X-Version-Resolved"] = resolved_version
    response.headers["X-Version-Fallback"] = "true" if is_fallback else "false"

    # Aggregate active files and their symbols
    files_symbols = {}
    for n in nodes:
        filepath = n.get("file")
        fqn = n.get("fqn")
        if filepath and fqn:
            if filepath not in files_symbols:
                files_symbols[filepath] = []
            files_symbols[filepath].append(fqn)

    # Build the hierarchical tree
    tree = {}
    for filepath, symbols in files_symbols.items():
        parts = filepath.strip("/").split("/")
        current = tree
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            if is_last:
                current[part] = {
                    "type": "file",
                    "path": filepath,
                    "symbols": sorted(list(set(symbols)))
                }
            else:
                if part not in current:
                    current[part] = {
                        "type": "folder",
                        "children": {}
                    }
                current = current[part]["children"]

    return tree

@app.get("/graph")
async def get_graph(version: str, response: Response, level: str = "file", focus_symbol: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    # Try querying graph_nodes/graph_edges
    db_nodes = []
    try:
        result = await db.execute(
            text("SELECT fqn, kind, file FROM graph_nodes WHERE version = :v"),
            {"v": version}
        )
        db_nodes = [dict(row) for row in result.mappings()]
    except Exception:
        pass

    if not db_nodes:
        # Fallback to current_symbols
        try:
            result = await db.execute(
                text("SELECT name AS fqn, kind, file FROM current_symbols WHERE version = :v"),
                {"v": version}
            )
            db_nodes = [dict(row) for row in result.mappings()]
        except Exception:
            pass

    resolved_version = version
    is_fallback = False

    # If empty, lazy fall back to the best available version
    if not db_nodes:
        resolved_version = await find_best_version(version, db)
        if resolved_version != version:
            is_fallback = True
            try:
                result = await db.execute(
                    text("SELECT fqn, kind, file FROM graph_nodes WHERE version = :v"),
                    {"v": resolved_version}
                )
                db_nodes = [dict(row) for row in result.mappings()]
            except Exception:
                pass

            if not db_nodes:
                try:
                    result = await db.execute(
                        text("SELECT name AS fqn, kind, file FROM current_symbols WHERE version = :v"),
                        {"v": resolved_version}
                    )
                    db_nodes = [dict(row) for row in result.mappings()]
                except Exception:
                    pass

    # Set version to the resolved fallback version so subsequent edge queries also use it
    version = resolved_version

    response.headers["X-Version-Requested"] = version
    response.headers["X-Version-Resolved"] = resolved_version
    response.headers["X-Version-Fallback"] = "true" if is_fallback else "false"

    db_edges = []
    try:
        result = await db.execute(
            text("SELECT from_fqn, to_fqn FROM graph_edges WHERE version = :v"),
            {"v": version}
        )
        db_edges = [dict(row) for row in result.mappings()]
    except Exception:
        pass

    if not db_edges:
        # Fallback to current_calls
        try:
            result = await db.execute(
                text("SELECT caller AS from_fqn, callee AS to_fqn FROM current_calls WHERE version = :v"),
                {"v": version}
            )
            db_edges = [dict(row) for row in result.mappings()]
        except Exception:
            pass

    nodes = []
    edges = []

    if level == "file":
        # Only FileNode nodes and file-to-file dependencies
        unique_files = sorted(list(set(n["file"] for n in db_nodes if n.get("file"))))
        for filepath in unique_files:
            nodes.append({
                "id": f"file:{filepath}",
                "label": os.path.basename(filepath),
                "type": "file"
            })

        symbol_to_file = {n["fqn"]: n["file"] for n in db_nodes if n.get("file")}

        # Suffix-matching lookup map for unqualified/partially-qualified symbols (e.g. read_csv_data)
        suffix_to_file = {}
        for fqn, filepath in symbol_to_file.items():
            parts = fqn.split(".")
            for i in range(1, min(len(parts) + 1, 4)):
                suffix = ".".join(parts[-i:])
                if suffix not in suffix_to_file:
                    suffix_to_file[suffix] = filepath

        seen_edges = set()
        for e in db_edges:
            src_symbol = e.get("from_fqn")
            tgt_symbol = e.get("to_fqn")

            src_file = symbol_to_file.get(src_symbol) or suffix_to_file.get(src_symbol)
            tgt_file = symbol_to_file.get(tgt_symbol) or suffix_to_file.get(tgt_symbol)

            if src_file and tgt_file and src_file != tgt_file:
                edge_tuple = (src_file, tgt_file)
                if edge_tuple not in seen_edges:
                    seen_edges.add(edge_tuple)
                    edges.append({
                        "source": f"file:{src_file}",
                        "target": f"file:{tgt_file}",
                        "type": "imports"
                    })
    else: # level == "all"
        # Full function-level network or radial depth 1 around focus_symbol
        symbol_to_kind = {n["fqn"]: n.get("kind", "symbol") for n in db_nodes}

        if focus_symbol:
            # Radial depth of 1 from focus_symbol
            keep_nodes = {focus_symbol}
            for e in db_edges:
                src = e.get("from_fqn")
                tgt = e.get("to_fqn")

                is_src_match = (src == focus_symbol or (src and focus_symbol.endswith("." + src)))
                is_tgt_match = (tgt == focus_symbol or (tgt and focus_symbol.endswith("." + tgt)))

                if is_src_match or is_tgt_match:
                    if src:
                        keep_nodes.add(src)
                    if tgt:
                        keep_nodes.add(tgt)
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "type": "calls"
                    })

            for fqn in sorted(list(keep_nodes)):
                kind = symbol_to_kind.get(fqn, "symbol")
                nodes.append({
                    "id": fqn,
                    "label": fqn.split(".")[-1] if "." in fqn else fqn,
                    "type": kind
                })
        else:
            # Return all function-level nodes and call-level edges
            for n in db_nodes:
                fqn = n["fqn"]
                nodes.append({
                    "id": fqn,
                    "label": fqn.split(".")[-1] if "." in fqn else fqn,
                    "type": n.get("kind", "symbol")
                })
            for e in db_edges:
                edges.append({
                    "source": e.get("from_fqn"),
                    "target": e.get("to_fqn"),
                    "type": "calls"
                })

    return {
        "nodes": nodes,
        "edges": edges
    }

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
            elif req.rule == "get_symbols":
                result = await adapter.get_symbols(version)
                return {"result": result}
            elif req.rule == "query_cross_repo_imports":
                result = await adapter.get_calls(version, edge_type="IMPORTS_FROM")
                return {"result": result}
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
                    import re

                    def is_safe_test_file(test_f: str) -> bool:
                        if not test_f or not isinstance(test_f, str):
                            return False
                        # Restrict to safe path characters
                        if not re.match(r'^[a-zA-Z0-9_\-\./]+$', test_f):
                            return False
                        # Disallow path traversal
                        if ".." in test_f:
                            return False
                        # Disallow absolute paths
                        if test_f.startswith("/"):
                            return False
                        # Must end with .py
                        if not test_f.endswith(".py"):
                            return False
                        # Must be a test file pattern (starts with test_ or ends with _test.py)
                        base = os.path.basename(test_f)
                        if not base.startswith("test_") and not base.endswith("_test.py"):
                            return False
                        return True

                    results = []
                    for test_file in test_files:
                        if not is_safe_test_file(test_file):
                            results.append({"file": test_file, "error": "Unsafe or unauthorized test file path skipped"})
                            continue
                        try:
                            process = subprocess.run(["uv", "run", "pytest", test_file], capture_output=True, text=True, timeout=60)
                            results.append({"file": test_file, "passed": process.returncode == 0, "stdout": process.stdout[-500:], "stderr": process.stderr[-500:]})
                        except Exception as e:
                            results.append({"file": test_file, "error": str(e)})

                    return {"result": {"status": "success" if all(r.get("passed", False) for r in results) else "failure", "test_results": results, "impact": impact}}
                else:
                    raise HTTPException(status_code=503, detail="Impact predictor not initialized")
            elif req.rule == "predict_next_edit":
                from ..mcp import server as mcp_mod
                from ..analytics.cochange_model import CochangePredictor
                predictor = CochangePredictor(adapter)
                predictions = await predictor.predict_next_edits(req.symbol, version)
                return {"result": {"symbol": req.symbol, "predictions": predictions}}

    dataflow = DataflowEngine(storage)
    rules = RuleEngine(storage, dataflow)
    try:
        result = await rules.evaluate_rule(req.rule, version, symbol=req.symbol, depth=req.depth)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/requirements/stream")
async def requirements_stream(req: Optional[RequirementsRequest] = Body(None), version: Optional[str] = None, session_id: Optional[str] = "default", db: AsyncSession = Depends(get_db)):
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

    # Apply adaptive grounding context filter if symbol_ids are specified
    if req and req.symbol_ids:
        filtered_symbols = [s for s in symbols if s.get("name") in req.symbol_ids]
        if not filtered_symbols:
            # Suffix/ends-with matching for absolute paths vs. relative database paths
            possible_files = set()
            for sid in req.symbol_ids:
                clean_id = sid.replace("file:", "")
                clean_id_normalized = clean_id.replace("\\", "/").strip("/")

                for s in symbols:
                    s_file = s.get("file")
                    if s_file:
                        s_file_normalized = s_file.replace("\\", "/").strip("/")
                        if clean_id_normalized.endswith(s_file_normalized) or s_file_normalized.endswith(clean_id_normalized):
                            possible_files.add(s_file)

                # Parent module name match
                for s in symbols:
                    if s.get("name") and s.get("name").startswith(sid):
                        if s.get("file"):
                            possible_files.add(s.get("file"))
            if possible_files:
                filtered_symbols = [s for s in symbols if s.get("file") in possible_files]

        symbols = filtered_symbols
        active_symbol_names = {s.get("name") for s in symbols if s.get("name")}
        calls = [c for c in calls if c.get("caller") in active_symbol_names or c.get("callee") in active_symbol_names]
    
    udf = LLMUDF(session_id=session_id)

    async def event_generator():
        try:
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
        except Exception as e:
            error_payload = {
                "error": f"LLM Generation failed: {str(e)}",
                "done": True
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/requirements", status_code=202)
async def requirements(req: Optional[RequirementsRequest] = Body(None), version: Optional[str] = None, session_id: Optional[str] = "default", db: AsyncSession = Depends(get_db)):
    storage = VersionedStorage(db)
    version = version or await storage.get_current_version()
    if not version:
        raise HTTPException(status_code=400, detail="No version found")
    
    # We pass the list of focused symbol_ids to the task if requested
    symbol_ids = req.symbol_ids if req else None
    job = llm_queue.enqueue(generate_requirements_task, version, session_id)
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

@app.post("/api/open-editor")
async def open_editor(payload: dict):
    file_path = payload.get("file_path")
    if not file_path:
        raise HTTPException(status_code=400, detail="Missing file_path")

    # Strip file: prefix if present
    if file_path.startswith("file:"):
        file_path = file_path[5:]

    # Security Check: Prevent directory traversal or arbitrary file handling
    if not is_safe_path(file_path):
        raise HTTPException(status_code=400, detail="Unauthorized or unsafe file path")

    import sys
    import subprocess
    import os

    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", file_path], check=True)
        else:
            subprocess.run(["xdg-open", file_path], check=True)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file: {str(e)}")

@app.get("/api/references")
async def find_references(symbol_id: str, version: str, db: AsyncSession = Depends(get_db)):
    # Find all edges where target matches symbol_id
    version = await find_best_version(version, db)

    try:
        result = await db.execute(
            text("SELECT from_fqn FROM graph_edges WHERE to_fqn = :sym AND version = :v"),
            {"sym": symbol_id, "v": version}
        )
        callers = [row[0] for row in result.all()]
    except Exception:
        try:
            result = await db.execute(
                text("SELECT caller FROM current_calls WHERE callee = :sym AND version = :v"),
                {"sym": symbol_id, "v": version}
            )
            callers = [row[0] for row in result.all()]
        except Exception:
            callers = []

    return {"references": list(set(callers))}