import os
import tempfile
from pathlib import Path
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Dict, Any, Optional
from code_intel.core.storage import get_db
from code_intel.core.models import ModuleAnalysis, AnalysisVersion

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

class AnalysisService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    async def create_draft(self, module_path: str, extracted_json: Dict[str, Any], git_sha: str) -> ModuleAnalysis:
        """
        Creates a new ModuleAnalysis record in DRAFT status,
        and initializes its first AnalysisVersion (version 1).
        """
        try:
            # 1. Instantiate master ModuleAnalysis
            ma = ModuleAnalysis(
                module_path=module_path,
                status="DRAFT"
            )
            self.db.add(ma)
            await self.db.flush() # Populate ma.id

            # 2. Instantiate first AnalysisVersion snapshot
            av = AnalysisVersion(
                module_analysis_id=ma.id,
                git_commit_sha=git_sha,
                version_num=1,
                business_rules=extracted_json.get("business_rules", []),
                edge_cases=extracted_json.get("edge_cases", []),
                data_transformations=extracted_json.get("data_transformations", []),
                side_effects=extracted_json.get("side_effects", [])
            )
            self.db.add(av)
            await self.db.commit()

            # Refresh to load relations
            await self.db.refresh(ma)
            return ma
        except Exception:
            await self.db.rollback()
            raise

    async def update_draft(self, analysis_id: int, new_json: Dict[str, Any]) -> ModuleAnalysis:
        """
        Updates the JSON snapshots of the most recent draft version.
        Only permitted if the ModuleAnalysis is in DRAFT status.
        """
        try:
            # 1. Fetch ModuleAnalysis
            result = await self.db.execute(
                select(ModuleAnalysis).where(ModuleAnalysis.id == analysis_id)
            )
            ma = result.scalar_one_or_none()
            if not ma:
                raise ValueError("ModuleAnalysis not found")
            if ma.status != "DRAFT":
                raise ValueError("Only analyses in DRAFT status can be updated")

            # 2. Query the latest AnalysisVersion
            av_result = await self.db.execute(
                select(AnalysisVersion)
                .where(AnalysisVersion.module_analysis_id == analysis_id)
                .order_by(desc(AnalysisVersion.version_num))
                .limit(1)
            )
            av = av_result.scalar_one_or_none()
            if not av:
                raise ValueError("AnalysisVersion snapshot not found")

            # 3. Overwrite JSON snapshots
            av.business_rules = new_json.get("business_rules", av.business_rules)
            av.edge_cases = new_json.get("edge_cases", av.edge_cases)
            av.data_transformations = new_json.get("data_transformations", av.data_transformations)
            av.side_effects = new_json.get("side_effects", av.side_effects)

            await self.db.commit()
            await self.db.refresh(ma)
            return ma
        except Exception:
            await self.db.rollback()
            raise

    async def promote_to_review(self, analysis_id: int) -> ModuleAnalysis:
        """
        Promotes the draft to REVIEWED status, creating a new frozen AnalysisVersion snapshot.
        """
        try:
            # 1. Fetch ModuleAnalysis
            result = await self.db.execute(
                select(ModuleAnalysis).where(ModuleAnalysis.id == analysis_id)
            )
            ma = result.scalar_one_or_none()
            if not ma:
                raise ValueError("ModuleAnalysis not found")

            # 2. Update Status
            ma.status = "REVIEWED"

            # 3. Fetch latest active AnalysisVersion values
            av_result = await self.db.execute(
                select(AnalysisVersion)
                .where(AnalysisVersion.module_analysis_id == analysis_id)
                .order_by(desc(AnalysisVersion.version_num))
                .limit(1)
            )
            latest_av = av_result.scalar_one_or_none()
            if not latest_av:
                raise ValueError("No active snapshots exist for this analysis")

            # 4. Create new version snapshot with incremented version number
            new_av = AnalysisVersion(
                module_analysis_id=ma.id,
                git_commit_sha=latest_av.git_commit_sha,
                version_num=latest_av.version_num + 1,
                business_rules=latest_av.business_rules,
                edge_cases=latest_av.edge_cases,
                data_transformations=latest_av.data_transformations,
                side_effects=latest_av.side_effects
            )
            self.db.add(new_av)

            await self.db.commit()
            await self.db.refresh(ma)
            return ma
        except Exception:
            await self.db.rollback()
            raise

    async def get_version_history(self, analysis_id: int) -> List[AnalysisVersion]:
        """
        Returns all historical snapshots for the given ModuleAnalysis ordered by version number ascending.
        """
        result = await self.db.execute(
            select(AnalysisVersion)
            .where(AnalysisVersion.module_analysis_id == analysis_id)
            .order_by(AnalysisVersion.version_num.asc())
        )
        return list(result.scalars().all())

    async def link_to_new_module(self, analysis_id: int, new_file_path: str) -> ModuleAnalysis:
        """
        Updates the target module path of a ModuleAnalysis record, verifying safety.
        """
        # 1. Validate safety
        if not is_safe_path(new_file_path):
            raise ValueError("Unauthorized or unsafe new file path")

        try:
            result = await self.db.execute(
                select(ModuleAnalysis).where(ModuleAnalysis.id == analysis_id)
            )
            ma = result.scalar_one_or_none()
            if not ma:
                raise ValueError("ModuleAnalysis not found")

            ma.module_path = new_file_path
            await self.db.commit()
            await self.db.refresh(ma)
            return ma
        except Exception:
            await self.db.rollback()
            raise
