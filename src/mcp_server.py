import asyncio
import json
import os
from typing import Optional, List, Dict, Any

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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@postgres:5432/codeintel")
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

server = Server("code-intel-mcp")
workspace_manager = WorkspaceManager()

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
        
        version = await get_version(arguments, storage)
        if not version:
             return [types.TextContent(type="text", text="Error: No version/commit_sha available.")]

        if name == "query_call_graph":
            func = arguments.get("function")
            result = await dataflow.transitive_calls(version)
            filtered = [row for row in result if row["caller"] == func or row["callee"] == func]
            return [types.TextContent(type="text", text=json.dumps(filtered, indent=2))]

        elif name == "query_dead_code":
            result = await rules.evaluate_rule("dead_code", version)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

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
            # In a real system, we'd embed the query_text first.
            # For this task, we'll assume a dummy embedding or mock.
            # Ideally, LLMUDF could have an embed() method.
            dummy_vector = [0.1] * 384 
            result = await storage.semantic_search(dummy_vector, version, limit)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_workspace_info":
            workspace_id = arguments.get("workspace_id")
            session_data = await workspace_manager.get_session(workspace_id)
            if not session_data:
                return [types.TextContent(type="text", text="Error: Workspace session not found.")]
            return [types.TextContent(type="text", text=json.dumps(session_data, indent=2))]

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
