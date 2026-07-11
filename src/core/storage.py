import os
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .models import Fact, DerivedFact, LLMArtifact, GraphNode, GraphEdge
from ..settings import LLM_MODEL, DATABASE_URL

EXTRACTOR_VERSION = "1.0.0"
MODEL = LLM_MODEL

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class VersionedStorage:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_fact(self, entity_type: str, entity_id: str, attribute: str, value: str, version: str):
        from ..settings import READ_MODEL_STRICT_SYNC
        
        fact = Fact(
            entity_type=entity_type,
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            version=version,
            extractor_version=EXTRACTOR_VERSION,
            valid_from=datetime.utcnow(),
            valid_to=None
        )
        
        # Identify facts being superseded to trigger invalidation
        expired_result = await self.session.execute(
            text("UPDATE facts SET valid_to = :now WHERE entity_type = :et AND entity_id = :ei AND attribute = :attr AND valid_to IS NULL RETURNING id"),
            {"now": datetime.utcnow(), "et": entity_type, "ei": entity_id, "attr": attribute}
        )
        expired_ids = [row[0] for row in expired_result.all()]
        
        self.session.add(fact)
        await self.session.flush() # Ensure fact has ID
        
        for fid in expired_ids:
            await self.invalidate_dependents(fid)

        if READ_MODEL_STRICT_SYNC:
            await self.refresh_read_model(entity_type, entity_id, version)

    async def refresh_read_model(self, entity_type: str, entity_id: str, version: str):
        """Transactional refresh of the read model for a specific entity"""
        if entity_type == "symbol":
            # Fetch latest symbol attributes
            res = await self.session.execute(text("""
                SELECT 
                    MAX(CASE WHEN attribute = 'name' THEN value END) as name,
                    MAX(CASE WHEN attribute = 'kind' THEN value END) as kind,
                    MAX(CASE WHEN attribute = 'file' THEN value END) as file,
                    MAX(id) as id
                FROM facts WHERE entity_type='symbol' AND entity_id = :ei AND version = :v AND valid_to IS NULL
            """), {"ei": entity_id, "v": version})
            row = res.fetchone()
            if row and row[0]:
                gn = GraphNode(id=row[3], fqn=row[0], kind=row[1], file=row[2], version=version, introduced_in=version)
                await self.session.merge(gn)
        elif entity_type == "call":
             res = await self.session.execute(text("""
                SELECT 
                    MAX(CASE WHEN attribute = 'caller' THEN value END) as caller,
                    MAX(CASE WHEN attribute = 'callee' THEN value END) as callee,
                    MAX(CASE WHEN attribute = 'confidence' THEN value END) as confidence,
                    MAX(id) as id
                FROM facts WHERE entity_type='call' AND entity_id = :ei AND version = :v AND valid_to IS NULL
            """), {"ei": entity_id, "v": version})
             row = res.fetchone()
             if row and row[0]:
                ge = GraphEdge(id=row[3], from_fqn=row[0], to_fqn=row[1], confidence=float(row[2] or 1.0), edge_type="CALLS", version=version, introduced_in=version)
                await self.session.merge(ge)

    async def rebuild_read_model(self, version: str):
        """Bulk refresh of the graph index for a specific version"""
        # Clear existing entries for this version
        await self.session.execute(text("DELETE FROM graph_nodes WHERE version = :v"), {"v": version})
        await self.session.execute(text("DELETE FROM graph_edges WHERE version = :v"), {"v": version})

        # Insert symbols
        await self.session.execute(text("""
            INSERT INTO graph_nodes (id, fqn, kind, file, version, introduced_in)
            SELECT MAX(id), 
                   MAX(CASE WHEN attribute = 'name' THEN value END),
                   MAX(CASE WHEN attribute = 'kind' THEN value END),
                   MAX(CASE WHEN attribute = 'file' THEN value END),
                   version, version
            FROM facts WHERE entity_type='symbol' AND version = :v AND valid_to IS NULL
            GROUP BY entity_id, version
        """), {"v": version})

        # Insert calls
        await self.session.execute(text("""
            INSERT INTO graph_edges (id, from_fqn, to_fqn, confidence, edge_type, version, introduced_in)
            SELECT MAX(id),
                   MAX(CASE WHEN attribute = 'caller' THEN value END),
                   MAX(CASE WHEN attribute = 'callee' THEN value END),
                   CAST(MAX(CASE WHEN attribute = 'confidence' THEN value END) AS FLOAT),
                   'CALLS', version, version
            FROM facts WHERE entity_type='call' AND version = :v AND valid_to IS NULL
            GROUP BY entity_id, version
        """), {"v": version})

    async def invalidate_dependents(self, fact_id: int, is_derived: bool = False):
        """
        Mark derived facts that depend on this fact as stale.
        Recursive walk if a derived fact depends on another derived fact.
        """
        column = "depends_on_derived" if is_derived else "depends_on"
        query = text(f"UPDATE derived_facts SET is_stale = TRUE WHERE :fid = ANY({column}) AND is_stale = FALSE RETURNING id")
        result = await self.session.execute(query, {"fid": fact_id})
        stale_ids = [row[0] for row in result.all()]
        
        for sid in stale_ids:
            await self.invalidate_dependents(sid, is_derived=True)

    async def insert_derived_fact(self, fact_type: str, entity_id: Optional[str], value: str, version: str, depends_on: List[int], depends_on_derived: List[int] = None):
        df = DerivedFact(
            fact_type=fact_type,
            entity_id=entity_id,
            value=value,
            version=version,
            extractor_version=EXTRACTOR_VERSION,
            depends_on=depends_on,
            depends_on_derived=depends_on_derived or [],
            is_stale=False,
            last_validated=datetime.utcnow()
        )
        self.session.add(df)

    async def get_derived_fact(self, fact_type: str, version: str, entity_id: Optional[str] = None) -> Optional[DerivedFact]:
        query = "SELECT * FROM derived_facts WHERE fact_type = :ft AND version = :v AND is_stale = FALSE"
        params = {"ft": fact_type, "v": version}
        if entity_id:
            query += " AND entity_id = :ei"
            params["ei"] = entity_id
        query += " LIMIT 1"
        
        result = await self.session.execute(text(query), params)
        row = result.fetchone()
        return row

    async def get_dependents(self, fact_id: int, is_derived: bool = False) -> List[Dict]:
        """
        Query the invalidation graph: "what depends on this fact?"
        """
        column = "depends_on_derived" if is_derived else "depends_on"
        query = text(f"SELECT id, fact_type, entity_id, is_stale FROM derived_facts WHERE :fid = ANY({column})")
        result = await self.session.execute(query, {"fid": fact_id})
        return [dict(row) for row in result.mappings().all()]

    async def insert_llm_artifact(self, artifact_type: str, value: str, version: str, grounded_in: List[int], prompt: str, model: str, entity_id: Optional[str] = None, is_verified: bool = True, confidence: float = 1.0):
        artifact = LLMArtifact(
            artifact_type=artifact_type,
            entity_id=entity_id,
            value=value,
            version=version,
            grounded_in=grounded_in,
            generation_prompt=prompt,
            model_version=model,
            is_verified=is_verified,
            confidence=confidence
        )
        self.session.add(artifact)

    async def get_artifacts_by_fact(self, fact_id: int) -> List[Dict]:
        """
        Query provenance: "what artifacts were generated from this fact?"
        """
        query = text("SELECT id, artifact_type, entity_id, is_verified FROM llm_artifacts WHERE :fid = ANY(grounded_in)")
        result = await self.session.execute(query, {"fid": fact_id})
        return [dict(row) for row in result.mappings().all()]

    async def insert_symbol(self, file: str, name: str, kind: str, line: int, version: str):
        print(f"Inserting symbol: {name} in {file} with version {version}")
        entity_id = f"{kind}:{name}"
        await self.insert_fact("symbol", entity_id, "file", file, version)
        await self.insert_fact("symbol", entity_id, "name", name, version)
        await self.insert_fact("symbol", entity_id, "kind", kind, version)
        await self.insert_fact("symbol", entity_id, "line", str(line), version)

    async def insert_call(self, caller: str, callee: str, confidence: float, version: str):
        entity_id = f"call:{caller}->{callee}"
        await self.insert_fact("call", entity_id, "caller", caller, version)
        await self.insert_fact("call", entity_id, "callee", callee, version)
        await self.insert_fact("call", entity_id, "confidence", str(confidence), version)

    async def resolve_symbol_id(self, fqn: str) -> Optional[int]:
        """
        Global Deduplication: Find the original Fact ID for a symbol FQN.
        Checks across all versions to find the most recent introduction.
        """
        query = """
            SELECT id FROM facts 
            WHERE entity_type = 'symbol' AND attribute = 'name' AND value = :fqn
            AND valid_to IS NULL
            ORDER BY id DESC LIMIT 1
        """
        result = await self.session.execute(text(query), {"fqn": fqn})
        return result.scalar()

    async def insert_cross_repo_import(self, caller: str, module: str, version: str, target_repo: str = "unknown", target_sha: str = "unknown"):
        entity_id = f"cross_repo_import:{caller}->{module}"
        await self.insert_fact("cross_repo_import", entity_id, "caller", caller, version)
        await self.insert_fact("cross_repo_import", entity_id, "module", module, version)
        await self.insert_fact("cross_repo_import", entity_id, "target_repo", target_repo, version)
        await self.insert_fact("cross_repo_import", entity_id, "target_sha", target_sha, version)
        await self.insert_fact("cross_repo_import", entity_id, "resolved_at", datetime.utcnow().isoformat(), version)
        
        # Deduplication Pass
        source_id = await self.resolve_symbol_id(module)
        if source_id:
            await self.insert_fact("cross_repo_import", entity_id, "source_fact_id", str(source_id), version)

    async def get_schema_version(self) -> Optional[str]:
        result = await self.session.execute(text("SELECT value FROM version_metadata WHERE key = 'schema_version'"))
        return result.scalar()

    async def set_schema_version(self, version: str):
        await self.session.execute(
            text("INSERT INTO version_metadata (key, value) VALUES ('schema_version', :v) ON CONFLICT (key) DO UPDATE SET value = :v"),
            {"v": version}
        )

    async def deprecate_old_extractor_facts(self):
        """
        Mark derived facts from older extractors as stale.
        For base facts, we could add a 'deprecated' flag if needed.
        """
        await self.session.execute(
            text("UPDATE derived_facts SET is_stale = TRUE WHERE extractor_version < :ev"),
            {"ev": EXTRACTOR_VERSION}
        )

    async def get_current_version(self) -> Optional[str]:
        result = await self.session.execute(text("SELECT MAX(version) FROM facts"))
        return result.scalar()

    async def execute_query(self, query: str, params: dict) -> List[Dict]:
        result = await self.session.execute(text(query), params)
        return [dict(row) for row in result.mappings().all()]

    async def semantic_search(self, query_vector: List[float], version: str, limit: int = 5) -> List[Dict]:
        query = """
        SELECT entity_id, attribute, value, version, (embedding <=> :qv) as distance
        FROM facts
        WHERE version = :v AND embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT :limit
        """
        result = await self.session.execute(text(query), {"qv": str(query_vector), "v": version, "limit": limit})
        return [dict(row) for row in result.mappings().all()]
