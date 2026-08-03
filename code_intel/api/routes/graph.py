from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from code_intel.core.storage import get_db
from code_intel.services.graph_service import GraphService

router = APIRouter()

@router.get("/graph/historical")
async def get_historical_graph(
    repo_id: str = Query(..., description="Repository ID or path"),
    commit_sha: str = Query(..., description="Commit SHA to fetch the graph state at"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch the code graph state (nodes and edges) as it existed at a specific Git commit SHA.
    """
    service = GraphService(db)
    try:
        result = await service.get_graph_at_commit(repo_id, commit_sha)
        return result
    except Exception as e:
        # To prevent information exposure (CWE-209), return a sanitized error message
        # while keeping the details if needed, or simply return a safe HTTP exception.
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )
