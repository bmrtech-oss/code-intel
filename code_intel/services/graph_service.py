from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any

class GraphService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_graph_at_commit(self, repo_id: str, commit_sha: str) -> Dict[str, Any]:
        """
        Returns the graph nodes and edges that were VALID (valid_from <= commit_sha <= valid_to)
        for the given commit SHA. If no specific valid_to, treat as HEAD.
        """
        nodes_result = await self.db.execute(
            text("""
                SELECT id, fqn, kind, file, version, introduced_in, deleted_in, valid_from_sha, valid_to_sha
                FROM graph_nodes
                WHERE valid_from_sha <= :sha AND (valid_to_sha IS NULL OR valid_to_sha >= :sha)
            """),
            {"sha": commit_sha}
        )
        nodes = [dict(row) for row in nodes_result.mappings()]

        edges_result = await self.db.execute(
            text("""
                SELECT id, from_fqn, to_fqn, edge_type, version, confidence, introduced_in, deleted_in, valid_from_sha, valid_to_sha
                FROM graph_edges
                WHERE valid_from_sha <= :sha AND (valid_to_sha IS NULL OR valid_to_sha >= :sha)
            """),
            {"sha": commit_sha}
        )
        edges = [dict(row) for row in edges_result.mappings()]

        return {
            "nodes": nodes,
            "edges": edges
        }
