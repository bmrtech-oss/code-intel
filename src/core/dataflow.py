import json
from .storage import VersionedStorage

class DataflowEngine:
    def __init__(self, storage: VersionedStorage):
        self.storage = storage

    async def transitive_calls(self, version: str):
        cached = await self.storage.get_derived_fact("transitive_calls", version)
        if cached:
            return json.loads(cached.value)

        # Get dependency IDs (facts table has the actual IDs, views don't)
        dep_query = "SELECT id FROM facts WHERE entity_type='call' AND attribute='callee' AND version = :v AND valid_to IS NULL"
        deps = await self.storage.execute_query(dep_query, {"v": version})
        dep_ids = [d["id"] for d in deps]

        # Use Optimized Read Model (graph_edges)
        query = """
        WITH RECURSIVE closure(caller, callee) AS (
            SELECT from_fqn, to_fqn FROM graph_edges WHERE version = :v
            UNION ALL
            SELECT c.caller, e.to_fqn
            FROM closure c
            JOIN graph_edges e ON c.callee = e.from_fqn AND e.version = :v
        )
        SELECT * FROM closure
        """
        try:
            result = await self.storage.execute_query(query, {"v": version})
        except:
            # Fallback to write model views
            query_fb = """
            WITH RECURSIVE closure(caller, callee) AS (
                SELECT caller, callee FROM current_calls WHERE version = :v
                UNION ALL
                SELECT c.caller, calls.callee
                FROM closure c
                JOIN current_calls calls ON c.callee = calls.caller AND calls.version = :v
            )
            SELECT * FROM closure
            """
            result = await self.storage.execute_query(query_fb, {"v": version})
            
        await self.storage.insert_derived_fact("transitive_calls", None, json.dumps(result), version, dep_ids)
        return result

    async def dead_code(self, version: str):
        cached = await self.storage.get_derived_fact("dead_code", version)
        if cached:
            return json.loads(cached.value)

        # Dead code depends on transitive calls
        # We need the ID of the transitive_calls derived fact
        await self.transitive_calls(version)
        tc_fact = await self.storage.get_derived_fact("transitive_calls", version)
        
        # Also depends on symbols
        dep_query = "SELECT id FROM facts WHERE entity_type='symbol' AND attribute='kind' AND version = :v AND valid_to IS NULL"
        deps = await self.storage.execute_query(dep_query, {"v": version})
        dep_ids = [d["id"] for d in deps]

        closures = await self.transitive_calls(version)
        called = set(row["callee"] for row in closures)
        if not called:
            query = "SELECT symbol_id, name, kind, file FROM current_symbols WHERE version = :v AND kind = 'function'"
            result = await self.storage.execute_query(query, {"v": version})
        else:
            placeholders = ','.join(f":c{i}" for i in range(len(called)))
            params = {"v": version}
            params.update({f"c{i}": c for i, c in enumerate(called)})
            query = f"""
            SELECT symbol_id, name, kind, file FROM current_symbols
            WHERE version = :v AND kind = 'function' AND symbol_id NOT IN ({placeholders})
            """
            result = await self.storage.execute_query(query, params)
        
        await self.storage.insert_derived_fact("dead_code", None, json.dumps(result), version, dep_ids, depends_on_derived=[tc_fact.id])
        return result

    async def impact_analysis(self, symbol: str, version: str, depth: int = 3):
        fact_type = f"impact_analysis_d{depth}"
        cached = await self.storage.get_derived_fact(fact_type, version, entity_id=symbol)
        if cached:
            return json.loads(cached.value)

        # Depends on calls
        dep_query = "SELECT id FROM facts WHERE entity_type='call' AND attribute='callee' AND version = :v AND valid_to IS NULL"
        deps = await self.storage.execute_query(dep_query, {"v": version})
        dep_ids = [d["id"] for d in deps]

        # Use Optimized Read Model
        query = """
        WITH RECURSIVE callers(callee, caller, depth) AS (
            SELECT to_fqn, from_fqn, 1 FROM graph_edges WHERE version = :v AND to_fqn = :sym
            UNION ALL
            SELECT c.callee, e.from_fqn, c.depth + 1
            FROM callers c
            JOIN graph_edges e ON c.caller = e.to_fqn AND e.version = :v
            WHERE c.depth < :depth
        )
        SELECT DISTINCT caller, depth FROM callers ORDER BY depth
        """
        try:
            result = await self.storage.execute_query(query, {"v": version, "sym": symbol, "depth": depth})
        except:
            # Fallback
            query_fb = """
            WITH RECURSIVE callers(callee, caller, depth) AS (
                SELECT callee, caller, 1 FROM current_calls WHERE version = :v AND callee = :sym
                UNION ALL
                SELECT c.callee, calls.caller, c.depth + 1
                FROM callers c
                JOIN current_calls calls ON c.caller = calls.callee AND calls.version = :v
                WHERE c.depth < :depth
            )
            SELECT DISTINCT caller, depth FROM callers ORDER BY depth
            """
            result = await self.storage.execute_query(query_fb, {"v": version, "sym": symbol, "depth": depth})
            
        await self.storage.insert_derived_fact(fact_type, symbol, json.dumps(result), version, dep_ids)
        return result
