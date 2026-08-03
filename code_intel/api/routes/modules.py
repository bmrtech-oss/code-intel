from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from code_intel.services.analysis_service import AnalysisService

router = APIRouter()

# --- Pydantic Schemas ---

class CreateDraftRequest(BaseModel):
    module_path: str
    extracted_json: dict
    git_sha: str

class UpdateDraftRequest(BaseModel):
    new_json: dict

class LinkModuleRequest(BaseModel):
    new_file_path: str

class AnalysisVersionSchema(BaseModel):
    id: int
    module_analysis_id: int
    git_commit_sha: str
    version_num: int
    business_rules: List[str]
    edge_cases: List[str]
    data_transformations: List[str]
    side_effects: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ModuleAnalysisSchema(BaseModel):
    id: int
    module_path: str
    status: str
    created_at: datetime
    updated_at: datetime
    versions: List[AnalysisVersionSchema] = []

    class Config:
        from_attributes = True

class DashboardModuleItem(BaseModel):
    id: int
    module_path: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.post("/draft", response_model=ModuleAnalysisSchema)
async def create_draft(
    req: CreateDraftRequest,
    service: AnalysisService = Depends()
):
    """
    Create a new ModuleAnalysis draft with its initial snapshot version.
    """
    try:
        ma = await service.create_draft(req.module_path, req.extracted_json, req.git_sha)
        return ma
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )

@router.put("/{id}/draft", response_model=ModuleAnalysisSchema)
async def update_draft(
    id: int,
    req: UpdateDraftRequest,
    service: AnalysisService = Depends()
):
    """
    Overwrites/updates the JSON snapshot of the active draft.
    """
    try:
        ma = await service.update_draft(id, req.new_json)
        return ma
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )

@router.patch("/{id}/status", response_model=ModuleAnalysisSchema)
async def promote_status(
    id: int,
    service: AnalysisService = Depends()
):
    """
    Promote active draft to REVIEWED status, generating a new frozen history snapshot.
    """
    try:
        ma = await service.promote_to_review(id)
        return ma
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )

@router.get("/{id}/history", response_model=List[AnalysisVersionSchema])
async def get_history(
    id: int,
    service: AnalysisService = Depends()
):
    """
    Retrieve full version snapshot history list for a module analysis.
    """
    try:
        history = await service.get_version_history(id)
        return history
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )

@router.patch("/{id}/link", response_model=ModuleAnalysisSchema)
async def link_module(
    id: int,
    req: LinkModuleRequest,
    service: AnalysisService = Depends()
):
    """
    Links a module analysis to a different safe file path.
    """
    try:
        ma = await service.link_to_new_module(id, req.new_file_path)
        return ma
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )

@router.get("/dashboard", response_model=List[DashboardModuleItem])
async def get_dashboard(
    service: AnalysisService = Depends()
):
    """
    List all modules with current statuses to populate the Tauri heatmap dashboard.
    """
    try:
        analyses = await service.get_all_analyses()
        return analyses
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}"
        )
