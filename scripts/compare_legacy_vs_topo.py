import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.core.storage import VersionedStorage
from src.storage.bitemporal_adapter import BiTemporalAdapter
from src.storage.graph_engine import SimpleGraphEngine

async def run_comparison():
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///test_legacy.db")
    engine = create_async_engine(DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    client = SimpleGraphEngine()
    adapter = BiTemporalAdapter(client)
    
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        
        for version in ["v1", "v2"]:
            print(f"--- Comparison for version {version} ---")
            
            # Compare Symbols
            legacy_symbols = await storage.execute_query("SELECT * FROM facts WHERE version = :v AND entity_type = 'symbol' AND attribute = 'name'", {"v": version})
            legacy_names = sorted([s["value"] for s in legacy_symbols])
            
            topo_symbols = await adapter.get_symbols(version)
            topo_names = sorted([s["fqn"] for s in topo_symbols])
            
            print(f"Legacy Symbols: {legacy_names}")
            print(f"Topological Symbols: {topo_names}")
            assert legacy_names == topo_names, f"Symbol mismatch for {version}!"

            # Compare Calls
            legacy_calls = await storage.execute_query("SELECT * FROM facts WHERE version = :v AND entity_type = 'call' AND attribute = 'caller'", {"v": version})
            legacy_call_count = len(legacy_calls)
            
            topo_calls = await adapter.get_calls(version)
            topo_call_count = len(topo_calls)
            
            print(f"Legacy Calls Count: {legacy_call_count}")
            print(f"Topological Calls Count: {topo_call_count}")
            assert legacy_call_count == topo_call_count, f"Call mismatch for {version}!"
        
        print("Comparison successful! Results match exactly.")

if __name__ == "__main__":
    asyncio.run(run_comparison())
