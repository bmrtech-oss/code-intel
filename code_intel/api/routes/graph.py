from fastapi import APIRouter, Depends, HTTPException, Query
from code_intel.services.graph_service import GraphService

router = APIRouter()

@router.get("/historical/{repo_id}/{commit_sha}")
async def get_historical_graph(
    repo_id: str,
    commit_sha: str,
    service: GraphService = Depends()
):
    """
    Fetch the code graph state (nodes and edges) as it existed at a specific Git commit SHA (path-based parameters).
    """
    try:
        result = await service.get_graph_at_commit(repo_id, commit_sha)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )

@router.get("/historical")
async def get_historical_graph_query(
    repo_id: str = Query(..., description="Repository ID or path"),
    commit_sha: str = Query(..., description="Commit SHA to fetch the graph state at"),
    service: GraphService = Depends()
):
    """
    Fetch the code graph state (nodes and edges) as it existed at a specific Git commit SHA (query parameters).
    """
    try:
        result = await service.get_graph_at_commit(repo_id, commit_sha)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )
