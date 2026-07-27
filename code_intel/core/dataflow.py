import abc
import json
import asyncio
from typing import List, Dict, Any
from .storage import VersionedStorage

try:
    import graphqlite
    GRAPHQLITE_AVAILABLE = True
    GRAPHQLITE_IMPORT_ERROR = None
except Exception as e:
    graphqlite = None
    GRAPHQLITE_AVAILABLE = False
    GRAPHQLITE_IMPORT_ERROR = str(e)

class BaseGraphEngine(abc.ABC):
    @abc.abstractmethod
    async def transitive_calls(self, version: str) -> List[Dict[str, Any]]:
        """Compute the transitive closure of calls for the given version."""
        pass

    @abc.abstractmethod
    async def dead_code(self, version: str) -> List[Dict[str, Any]]:
        """Identify dead code (functions never called directly or transitively)."""
        pass

    @abc.abstractmethod
    async def impact_analysis(self, symbol: str, version: str, depth: int = 3) -> List[Dict[str, Any]]:
        """Find all symbols transitively calling the target symbol up to a given depth."""
        pass

    @abc.abstractmethod
    async def rebuild_graph(self, version: str) -> None:
        """Sync/rebuild the graph structure from database facts."""
        pass

class ProductionGraphEngine(BaseGraphEngine):
    def __init__(self, storage: VersionedStorage):
        self.storage = storage

    async def transitive_calls(self, version: str) -> List[Dict[str, Any]]:
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

    async def dead_code(self, version: str) -> List[Dict[str, Any]]:
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

    async def impact_analysis(self, symbol: str, version: str, depth: int = 3) -> List[Dict[str, Any]]:
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

    async def rebuild_graph(self, version: str) -> None:
        await self.storage.rebuild_read_model(version)

class LocalGraphEngine(BaseGraphEngine):
    def __init__(self, storage: VersionedStorage):
        self.storage = storage
        if not GRAPHQLITE_AVAILABLE:
            raise RuntimeError(
                f"GraphQLite is not available: {GRAPHQLITE_IMPORT_ERROR or 'Import failed'}. "
                "Please ensure that the 'graphqlite' package is installed and SQLite extension loading is supported by your Python runtime."
            )
        try:
            import os
            from ..settings import GRAPHQLITE_DB_PATH
            db_dir = os.path.dirname(GRAPHQLITE_DB_PATH)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self.g = graphqlite.Graph(GRAPHQLITE_DB_PATH)
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize GraphQLite Graph at {GRAPHQLITE_DB_PATH or 'None'}: {e}. "
                "This may be because your Python runtime's sqlite3 module does not support extension loading."
            )

    async def transitive_calls(self, version: str) -> List[Dict[str, Any]]:
        cached = await self.storage.get_derived_fact("transitive_calls", version)
        if cached:
            return json.loads(cached.value)

        dep_query = "SELECT id FROM facts WHERE entity_type='call' AND attribute='callee' AND version = :v AND valid_to IS NULL"
        deps = await self.storage.execute_query(dep_query, {"v": version})
        dep_ids = [d["id"] for d in deps]

        def _query_transitive():
            results = self.g.query(
                "MATCH (caller)-[:CALLS*]->(callee) "
                "RETURN DISTINCT caller.id AS caller, callee.id AS callee"
            )
            return results

        results = await asyncio.to_thread(_query_transitive)
        await self.storage.insert_derived_fact("transitive_calls", None, json.dumps(results), version, dep_ids)
        return results

    async def dead_code(self, version: str) -> List[Dict[str, Any]]:
        cached = await self.storage.get_derived_fact("dead_code", version)
        if cached:
            return json.loads(cached.value)

        await self.transitive_calls(version)
        tc_fact = await self.storage.get_derived_fact("transitive_calls", version)

        dep_query = "SELECT id FROM facts WHERE entity_type='symbol' AND attribute='kind' AND version = :v AND valid_to IS NULL"
        deps = await self.storage.execute_query(dep_query, {"v": version})
        dep_ids = [d["id"] for d in deps]

        query = "SELECT symbol_id, name, kind, file FROM current_symbols WHERE version = :v AND kind = 'function'"
        all_functions = await self.storage.execute_query(query, {"v": version})

        closures = await self.transitive_calls(version)
        called = set(row["callee"] for row in closures)

        result = [f for f in all_functions if f["symbol_id"] not in called]

        await self.storage.insert_derived_fact("dead_code", None, json.dumps(result), version, dep_ids, depends_on_derived=[tc_fact.id])
        return result

    async def impact_analysis(self, symbol: str, version: str, depth: int = 3) -> List[Dict[str, Any]]:
        fact_type = f"impact_analysis_d{depth}"
        cached = await self.storage.get_derived_fact(fact_type, version, entity_id=symbol)
        if cached:
            return json.loads(cached.value)

        dep_query = "SELECT id FROM facts WHERE entity_type='call' AND attribute='callee' AND version = :v AND valid_to IS NULL"
        deps = await self.storage.execute_query(dep_query, {"v": version})
        dep_ids = [d["id"] for d in deps]

        def _query_impact():
            results = self.g.query(
                "MATCH p = (callee {id: $sym})<-[:CALLS*1..$depth]-(caller) "
                "RETURN caller.id AS caller, length(p) AS depth",
                {"sym": symbol, "depth": depth}
            )
            return results

        results = await asyncio.to_thread(_query_impact)

        caller_depths = {}
        for row in results:
            c = row["caller"]
            d = row["depth"]
            if c not in caller_depths or d < caller_depths[c]:
                caller_depths[c] = d

        formatted = [{"caller": c, "depth": d} for c, d in sorted(caller_depths.items(), key=lambda x: x[1])]

        await self.storage.insert_derived_fact(fact_type, symbol, json.dumps(formatted), version, dep_ids)
        return formatted

    async def rebuild_graph(self, version: str) -> None:
        await self.storage.rebuild_read_model(version)

        nodes = await self.storage.execute_query(
            "SELECT fqn, kind, file, version FROM graph_nodes WHERE version = :v",
            {"v": version}
        )
        edges = await self.storage.execute_query(
            "SELECT from_fqn, to_fqn, confidence, version FROM graph_edges WHERE version = :v",
            {"v": version}
        )

        def _sync():
            try:
                self.g.query("MATCH (n) DETACH DELETE n")
            except Exception:
                pass

            for n in nodes:
                self.g.upsert_node(
                    node_id=n["fqn"],
                    label="Symbol",
                    properties={
                        "kind": n["kind"],
                        "file": n["file"],
                        "version": n["version"]
                    }
                )
            for e in edges:
                self.g.upsert_edge(
                    source_id=e["from_fqn"],
                    target_id=e["to_fqn"],
                    rel_type="CALLS",
                    properties={
                        "confidence": float(e["confidence"] or 1.0),
                        "version": e["version"]
                    }
                )

        await asyncio.to_thread(_sync)

class DataflowEngine:
    def __init__(self, storage: VersionedStorage):
        self.storage = storage
        from ..settings import GRAPH_ENGINE
        if GRAPH_ENGINE == "local":
            self.engine = LocalGraphEngine(storage)
        else:
            self.engine = ProductionGraphEngine(storage)

    async def transitive_calls(self, version: str) -> List[Dict[str, Any]]:
        return await self.engine.transitive_calls(version)

    async def dead_code(self, version: str) -> List[Dict[str, Any]]:
        return await self.engine.dead_code(version)

    async def impact_analysis(self, symbol: str, version: str, depth: int = 3) -> List[Dict[str, Any]]:
        return await self.engine.impact_analysis(symbol, version, depth)

    async def rebuild_graph(self, version: str) -> None:
        await self.engine.rebuild_graph(version)
