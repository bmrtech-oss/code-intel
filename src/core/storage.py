from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from .models import Fact, Symbol
from typing import Optional, List, Dict
import os
from datetime import datetime
from .models import Fact
from typing import Optional, List, Dict

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/codeintel")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class VersionedStorage:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_fact(self, entity_type: str, entity_id: str, attribute: str, value: str, version: str):
        fact = Fact(
            entity_type=entity_type,
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            version=version,
            valid_from=datetime.utcnow(),
            valid_to=None
        )
        # Expire previous fact
        await self.session.execute(
            text("UPDATE facts SET valid_to = :now WHERE entity_type = :et AND entity_id = :ei AND attribute = :attr AND valid_to IS NULL"),
            {"now": datetime.utcnow(), "et": entity_type, "ei": entity_id, "attr": attribute}
        )
        self.session.add(fact)

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
