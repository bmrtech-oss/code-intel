from .storage import VersionedStorage

class DataflowEngine:
    def __init__(self, storage: VersionedStorage):
        self.storage = storage

    async def transitive_calls(self, version: str):
        query = """
        WITH RECURSIVE closure(caller, callee) AS (
            SELECT caller, callee FROM current_calls WHERE version = :v
            UNION ALL
            SELECT c.caller, calls.callee
            FROM closure c
            JOIN current_calls calls ON c.callee = calls.caller AND calls.version = :v
        )
        SELECT * FROM closure
        """
        return await self.storage.execute_query(query, {"v": version})

    async def dead_code(self, version: str):
        closures = await self.transitive_calls(version)
        called = set(row["callee"] for row in closures)
        if not called:
            query = "SELECT symbol_id, name, kind, file FROM current_symbols WHERE version = :v AND kind = 'function'"
            return await self.storage.execute_query(query, {"v": version})
        placeholders = ','.join(f":c{i}" for i in range(len(called)))
        params = {"v": version}
        params.update({f"c{i}": c for i, c in enumerate(called)})
        query = f"""
        SELECT symbol_id, name, kind, file FROM current_symbols
        WHERE version = :v AND kind = 'function' AND symbol_id NOT IN ({placeholders})
        """
        return await self.storage.execute_query(query, params)

    async def impact_analysis(self, symbol: str, version: str, depth: int = 3):
        query = """
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
        return await self.storage.execute_query(query, {"v": version, "sym": symbol, "depth": depth})
