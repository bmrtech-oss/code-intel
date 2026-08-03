import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from code_intel.core.udf import LLMUDF

router = APIRouter()

class ForensicExtractionResponse(BaseModel):
    business_rules: List[str]
    edge_cases: List[str]
    data_transformations: List[str]
    side_effects: List[str]

class StructuredExtractionRequest(BaseModel):
    file_path: str
    prompt_override: Optional[str] = None
    session_id: Optional[str] = "default"

def is_safe_path(path: str) -> bool:
    """Return True when the resolved path stays under an allowed root directory."""
    try:
        if not path or "\x00" in path:
            return False

        # Canonicalize user input before constructing a Path object.
        normalized_input = os.path.normpath(os.path.expanduser(path))
        candidate = Path(os.path.abspath(normalized_input)).resolve(strict=False)
        app_temp_root = (Path(tempfile.gettempdir()) / "code_intel").resolve(strict=False)
        allowed_roots = [
            Path("/repo").resolve(strict=False),
            Path("/shared").resolve(strict=False),
            app_temp_root,
            Path(os.path.realpath(os.getcwd())).resolve(strict=False),
            Path(os.path.realpath(tempfile.gettempdir())).resolve(strict=False),
        ]

        for root in allowed_roots:
            try:
                candidate.relative_to(root)
                return True
            except ValueError:
                continue

        return False
    except Exception:
        return False

@router.post("/structured")
async def extract_structured(req: StructuredExtractionRequest):
    """
    Takes a file_path and runs a specialized Forensic Analyst extraction against the LLM,
    returning validated JSON containing business_rules, edge_cases, data_transformations, and side_effects.
    """
    # 1. Path Traversal Security check
    if not is_safe_path(req.file_path):
        raise HTTPException(status_code=400, detail="Unauthorized or unsafe file path")

    # 2. Check file existence
    resolved_path = os.path.abspath(os.path.expanduser(req.file_path))
    if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
        raise HTTPException(status_code=404, detail="File not found")

    # 3. Read file content
    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            code_content = f.read()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read file: {e.__class__.__name__}"
        )

    # 4. Format system prompt template
    if req.prompt_override:
        prompt = req.prompt_override.replace("{{code}}", code_content)
    else:
        template_path = os.path.join("prompts", "forensic_system.txt")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template = f.read()
            prompt = template.replace("{{code}}", code_content)
        except Exception:
            # Fallback inline template if prompt file cannot be loaded
            prompt = f"Analyze the following code and output JSON containing exactly business_rules, edge_cases, data_transformations, side_effects.\n\nCode:\n{code_content}"

    # 5. Invoke LLM and extract structure
    udf = LLMUDF(session_id=req.session_id or "default")
    try:
        result = await udf.generate_structured(prompt, ForensicExtractionResponse)
        if "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM Generation failed: {e.__class__.__name__}"
        )
