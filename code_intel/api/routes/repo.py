import urllib.parse
from fastapi import APIRouter, Depends, HTTPException
from code_intel.services.git_service import GitService

router = APIRouter()

@router.get("/{repo_id}/timeline")
def get_timeline(repo_id: str, service: GitService = Depends()):
    """
    Expose chronological git log timeline (commits and timestamps) for a given repository.
    FastAPI handles standard synchronous route handlers in a threadpool to prevent blocking the event loop.
    """
    try:
        decoded_repo_id = urllib.parse.unquote(repo_id)
        return service.get_commit_timeline(decoded_repo_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )
