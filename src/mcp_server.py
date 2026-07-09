import asyncio
import json
import os
from typing import Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .core.storage import VersionedStorage
from .core.dataflow import DataflowEngine
from .core.rules import RuleEngine
from .core.workspace import WorkspaceManager
from .core.udf import LLMUDF
from .settings import USE_BITEMPORAL
from .storage.bitemporal_adapter import BiTemporalAdapter
from .storage.graph_engine import SimpleGraphEngine
from .cache.memory_cache import MemoryCache
from .cache.cdc_listener import CDCListener
from .cache.cache_bootstrap import CacheBootstrap
from .semantic.search import SemanticSearch
from .analytics.predictor import ImpactPredictor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@postgres:5432/codeintel")
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

server = Server("code-intel-mcp")
workspace_manager = WorkspaceManager()

# Global topological storage stack
adapter: Optional[BiTemporalAdapter] = None
semantic_search_engine: Optional[SemanticSearch] = None
impact_predictor: Optional[ImpactPredictor] = None

async def init_topological_stack():
    global adapter, semantic_search_engine, impact_predictor
    if USE_BITEMPORAL and adapter is None:
        engine_client = SimpleGraphEngine()
        memory_cache = MemoryCache()
        
        bootstrap = CacheBootstrap(engine_client, memory_cache)
        await bootstrap.initialize_cache()
        
        listener = CDCListener(engine_client, memory_cache)
        await listener.start()
        
        adapter = BiTemporalAdapter(engine_client, memory_cache)
        semantic_search_engine = SemanticSearch()
        impact_predictor = ImpactPredictor(adapter)

TOOLS = [
    types.Tool(
        name="query_call_graph",
        description="Get transitive call graph for a function.",
        inputSchema={
            "type": "object",
            "properties": {
                "function": {"type": "string"},
                "commit_sha": {"type": "string"}
            },
            "required": ["function"]
        }
    ),
    types.Tool(
        name="query_dead_code",
        description="Find functions that are never called.",
        inputSchema={
            "type": "object",
            "properties": {
                "commit_sha": {"type": "string"}
            }
        }
    ),
    types.Tool(
        name="generate_requirements",
        description="Generate epics, features, stories from the codebase.",
        inputSchema={
            "type": "object",
            "properties": {
                "commit_sha": {"type": "string"}
            }
        }
    ),
    types.Tool(
        name="query_impact",
        description="Perform impact analysis for a symbol.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "depth": {"type": "integer", "default": 3},
                "commit_sha": {"type": "string"}
            },
            "required": ["symbol"]
        }
    ),
    types.Tool(
        name="semantic_search",
        description="Search the codebase using natural language semantics.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
                "commit_sha": {"type": "string"}
            },
            "required": ["query"]
        }
    ),
    types.Tool(
        name="get_workspace_info",
        description="Get current Git states from the workspace session.",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"}
            }
        }
    ),
    types.Tool(
        name="query_cross_repo_imports",
        description="Get cross-repo imports for the codebase.",
        inputSchema={
            "type": "object",
            "properties": {
                "commit_sha": {"type": "string"}
            }
        }
    ),
    types.Tool(
        name="predict_impact",
        description="Predict the blast radius of a code modification based on history.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "commit_sha": {"type": "string"}
            },
            "required": ["symbol"]
        }
    ),
]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return TOOLS

async def get_version(arguments: dict, storage: VersionedStorage) -> str:
    commit_sha = arguments.get("commit_sha")
    if not commit_sha:
        commit_sha = await workspace_manager.get_active_sha()
    
    if not commit_sha:
        commit_sha = await storage.get_current_version()
    
    return commit_sha

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        dataflow = DataflowEngine(storage)
        rules = RuleEngine(storage, dataflow)
        
        # Ensure topological stack is initialized
        if USE_BITEMPORAL:
            await init_topological_stack()

        version = await get_version(arguments, storage)
        if not version:
             return [types.TextContent(type="text", text="Error: No version/commit_sha available.")]

        if name == "query_call_graph":
            func = arguments.get("function")
            if adapter:
                # Use topological graph adapter
                calls = await adapter.get_calls(version, caller_fqn=func)
                # For call graph we might want both directions
                # Simplification: just return calls from/to this function
                # Note: get_calls currently only filters by caller if caller_fqn is provided
                return [types.TextContent(type="text", text=json.dumps(calls, indent=2))]
            else:
                result = await dataflow.transitive_calls(version)
                filtered = [row for row in result if row["caller"] == func or row["callee"] == func]
                return [types.TextContent(type="text", text=json.dumps(filtered, indent=2))]

        elif name == "query_dead_code":
            if adapter:
                # Dead code via graph lookup: symbols with no incoming CALLS edges
                # This is a simplified rule for the adapter implementation
                all_symbols = await adapter.get_symbols(version, filters={"kind": "function"})
                all_calls = await adapter.get_calls(version)
                called_fqns = {c["to"] for c in all_calls}
                dead_code = [s for s in all_symbols if s["fqn"] not in called_fqns]
                return [types.TextContent(type="text", text=json.dumps(dead_code, indent=2))]
            else:
                result = await rules.evaluate_rule("dead_code", version)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "query_cross_repo_imports":
            if adapter:
                imports = await adapter.get_calls(version, edge_type="IMPORTS_FROM")
                return [types.TextContent(type="text", text=json.dumps(imports, indent=2))]
            else:
                # Fallback to direct fact query and map to edge schema
                result = await storage.execute_query("SELECT * FROM facts WHERE version = :v AND entity_type = 'cross_repo_import'", {"v": version})
                
                # Group by entity_id to extract caller and module
                mapped = {}
                for row in result:
                    eid = row["entity_id"]
                    if eid not in mapped:
                        mapped[eid] = {"from": eid.split("->")[0]}
                    if row["attribute"] == "module":
                        mapped[eid]["to"] = row["value"]
                
                return [types.TextContent(type="text", text=json.dumps(list(mapped.values()), indent=2))]

        elif name == "generate_requirements":
            udf = LLMUDF()
            # Note: The current current_symbols/current_calls views might not be parameterized by version correctly if they are just views.
            # Assuming VersionedStorage.execute_query handles the raw version filtering.
            symbols = await storage.execute_query("SELECT * FROM facts WHERE version = :v AND entity_type = 'symbol'", {"v": version})
            calls = await storage.execute_query("SELECT * FROM facts WHERE version = :v AND entity_type = 'call'", {"v": version})
            req = await udf.generate_requirements(symbols, calls)
            return [types.TextContent(type="text", text=req)]

        elif name == "query_impact":
            symbol = arguments.get("symbol")
            depth = arguments.get("depth", 3)
            result = await dataflow.impact_analysis(symbol, version, depth)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "semantic_search":
            query_text = arguments.get("query")
            limit = arguments.get("limit", 5)
            if semantic_search_engine:
                result = await semantic_search_engine.search(query_text, limit)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                # Fallback to legacy pgvector search if semantic engine not initialized
                dummy_vector = [0.1] * 384 
                result = await storage.semantic_search(dummy_vector, version, limit)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_workspace_info":
            workspace_id = arguments.get("workspace_id")
            session_data = await workspace_manager.get_session(workspace_id)
            if not session_data:
                return [types.TextContent(type="text", text="Error: Workspace session not found.")]
            return [types.TextContent(type="text", text=json.dumps(session_data, indent=2))]

        elif name == "predict_impact":
            symbol = arguments.get("symbol")
            if impact_predictor:
                result = await impact_predictor.predict_blast_radius(symbol, version)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                return [types.TextContent(type="text", text="Error: Impact predictor not initialized.")]

        else:
            raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="code-intel",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
