import httpx
from typing import Optional, Dict, Any

class CodeIntelClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    async def analyze(self, repo_path: str, version: Optional[str] = None, branch: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/analyze",
                json={"repo_path": repo_path, "version": version, "branch": branch}
            )
            resp.raise_for_status()
            return resp.json()

    async def query(self, rule: str, symbol: Optional[str] = None, commit_sha: Optional[str] = None, depth: int = 3) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/query",
                json={"rule": rule, "symbol": symbol, "commit_sha": commit_sha, "depth": depth}
            )
            resp.raise_for_status()
            return resp.json()

    async def generate_requirements(self, version: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/requirements",
                params={"version": version} if version else {}
            )
            resp.raise_for_status()
            return resp.json()

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/requirements/status/{job_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_traceability(self, requirement_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/trace/{requirement_id}")
            resp.raise_for_status()
            return resp.json()

    async def semantic_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/search", params={"q": query, "limit": limit})
            resp.raise_for_status()
            return resp.json()
