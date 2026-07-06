import json
import os
import redis.asyncio as redis
from typing import List, Optional, Dict

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

class WorkspaceManager:
    def __init__(self, host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = REDIS_DB):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    async def set_session(self, workspace_id: str, branch: str, sha: str, ancestors: List[str]):
        """
        Stores workspace session data in Redis.
        """
        data = {
            "current_branch": branch,
            "current_sha": sha,
            "ancestor_shas": ancestors
        }
        await self.redis.set(f"workspace:{workspace_id}", json.dumps(data))
        # Also set a global "active" workspace pointer if needed, or just use a fixed ID
        await self.redis.set("workspace:active_id", workspace_id)

    async def get_session(self, workspace_id: Optional[str] = None) -> Optional[Dict]:
        """
        Retrieves workspace session data from Redis.
        If workspace_id is None, retrieves the active workspace.
        """
        if workspace_id is None:
            workspace_id = await self.redis.get("workspace:active_id")
        
        if not workspace_id:
            return None
        
        data = await self.redis.get(f"workspace:{workspace_id}")
        if data:
            return json.loads(data)
        return None

    async def get_active_sha(self) -> Optional[str]:
        """
        Helper to get the current SHA of the active workspace.
        """
        session = await self.get_session()
        if session:
            return session.get("current_sha")
        return None

    async def close(self):
        await self.redis.close()
