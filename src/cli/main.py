import typer
import uvicorn
import asyncio
import re
from typing import Optional
from ..core.storage import VersionedStorage, AsyncSessionLocal
from ..core.ingestion import IngestionPipeline
from ..core.git_handler import GitRepoHandler
from ..api.server import app as fastapi_app

app = typer.Typer()

def is_git_url(path: str) -> bool:
    """Check if the path is a Git repository URL."""
    return bool(re.match(r'^(https?://|git@)', path))

@app.command()
def analyze(
    repo_path: str,
    version: Optional[str] = None,
    branch: Optional[str] = None,
    depth: Optional[int] = None,
    no_cleanup: bool = False
):
    """Index a local directory or a remote Git repository."""
    temp_repo = None
    try:
        if is_git_url(repo_path):
            typer.echo(f"Cloning Git repository: {repo_path}")
            handler = GitRepoHandler(repo_path, branch, depth)
            actual_path = handler.clone()
            temp_repo = handler
            typer.echo(f"Cloned to {actual_path}")
        else:
            actual_path = repo_path
            handler = None

        typer.echo(f"Analyzing {actual_path}...")
        if version is None:
            import time
            version = str(int(time.time()))

        async def _run():
            async with AsyncSessionLocal() as session:
                storage = VersionedStorage(session)
                pipeline = IngestionPipeline(storage)
                await pipeline.walk_and_parse(actual_path, version)
                await session.commit()
                typer.echo(f"Indexed with version {version}")

        asyncio.run(_run())

    finally:
        if temp_repo and not no_cleanup:
            temp_repo.cleanup()
            typer.echo("Cleaned up temporary clone.")

@app.command()
def trace(requirement_id: str):
    """Show source code symbols linked to a requirement."""
    import httpx
    resp = httpx.get(f"http://localhost:8000/trace/{requirement_id}")
    if resp.status_code == 200:
        data = resp.json()
        typer.echo(f"Requirement: {data['requirement_id']}")
        for sym in data['symbols']:
            typer.echo(f"  {sym['symbol_id']} - {sym['file']}")
    else:
        typer.echo("Requirement not found.")

@app.command()
def query(
    rule: str, 
    version: Optional[str] = None, 
    commit: Optional[str] = None,
    symbol: Optional[str] = None, 
    depth: int = 3
):
    """Run an analysis rule (use API for full results)."""
    import httpx
    commit_sha = commit or version
    typer.echo(f"Running rule '{rule}' for commit {commit_sha}...")
    
    payload = {
        "rule": rule,
        "commit_sha": commit_sha,
        "symbol": symbol,
        "depth": depth
    }
    
    try:
        import json
        resp = httpx.post("http://localhost:8000/query", json=payload)
        if resp.status_code == 200:
            typer.echo(json.dumps(resp.json(), indent=2))
        else:
            typer.echo(f"Error: {resp.text}")
    except Exception as e:
        typer.echo(f"Failed to connect to API: {e}")

@app.command()
def requirements(version: Optional[str] = None):
    """Generate requirements (use API for full output)."""
    typer.echo("Generating requirements...")
    typer.echo("Use the API endpoint /requirements for JSON output")

@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000):
    """Start the REST API server."""
    uvicorn.run(fastapi_app, host=host, port=port)

@app.command()
def mcp():
    """Start the MCP server for Claude Code."""
    from ..mcp.server import main as mcp_main
    asyncio.run(mcp_main())

def get_claude_config_path() -> Optional[str]:
    import os
    from pathlib import Path
    import platform
    
    system = platform.system()
    if system == "Darwin":
        return str(Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    elif system == "Linux":
        return str(Path.home() / ".config" / "Claude" / "claude_desktop_config.json")
    elif system == "Windows":
        return str(Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json")
    return None

def safe_merge_json(config_path: str, mcp_config: dict):
    import json
    from pathlib import Path
    
    path = Path(config_path)
    if path.exists():
        with open(path, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    if "mcpServers" not in data:
        data["mcpServers"] = {}
    
    data["mcpServers"]["code-intel"] = mcp_config

    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w") as f:
        json.dump(data, f, indent=2)
    temp_path.replace(path)

@app.command()
def setup_claude():
    """Configure Claude Desktop to use Code-Intel MCP."""
    import os
    config_path = get_claude_config_path()
    if not config_path:
        typer.echo("Unsupported OS for auto-setup.")
        return

    mcp_config = {
        "command": "code-intel-mcp",
        "env": {
            "DATABASE_URL": os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/codeintel"),
            "USE_BITEMPORAL": "true"
        }
    }
    
    safe_merge_json(config_path, mcp_config)
    typer.echo(f"✅ Code-Intel MCP added to Claude Desktop at {config_path}")

@app.command()
def setup_cursor():
    """Add .cursorrules to the current directory."""
    from pathlib import Path
    import json
    
    rules = {
        "instruction": "You are an expert developer with access to Code-Intel, a topological code intelligence platform.",
        "api_endpoint": "http://localhost:8000",
        "rules": [
            "When asked about code structure, use the Code-Intel MCP tools or API.",
            "Always check for dead code using 'query_dead_code' before proposing deletions.",
            "Use 'predict_impact' to assess the blast radius of your proposed changes.",
            "Verify your requirements against the code using the 'trace' endpoint."
        ]
    }
    
    cursor_dir = Path(".cursor")
    cursor_dir.mkdir(exist_ok=True)
    
    rules_path = Path(".cursorrules")
    with open(rules_path, "w") as f:
        json.dump(rules, f, indent=2)
    
    typer.echo("✅ .cursorrules added to the current directory!")

if __name__ == "__main__":
    app()