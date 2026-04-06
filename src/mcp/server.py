import asyncio
import json
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from ..core.storage import VersionedStorage
from ..core.dataflow import DataflowEngine
from ..core.rules import RuleEngine
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@postgres:5432/codeintel")
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

server = Server("code-intel-mcp")

TOOLS = [
    types.Tool(name="query_dead_code", description="Find functions that are never called.",
               inputSchema={"type": "object", "properties": {"version": {"type": "string"}}}),
    types.Tool(name="query_call_graph", description="Get transitive call graph for a function.",
               inputSchema={"type": "object", "properties": {"function": {"type": "string"}, "version": {"type": "string"}}}),
    types.Tool(name="generate_requirements", description="Generate epics, features, stories from the codebase.",
               inputSchema={"type": "object", "properties": {"version": {"type": "string"}}}),
]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return TOOLS

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    async with AsyncSessionLocal() as session:
        storage = VersionedStorage(session)
        dataflow = DataflowEngine(storage)
        rules = RuleEngine(storage, dataflow)
        version = arguments.get("version") or await storage.get_current_version()
        if name == "query_dead_code":
            result = await rules.evaluate_rule("dead_code", version)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        elif name == "query_call_graph":
            func = arguments.get("function")
            if not func:
                raise ValueError("Missing 'function'")
            result = await dataflow.transitive_calls(version)
            filtered = [row for row in result if row["caller"] == func or row["callee"] == func]
            return [types.TextContent(type="text", text=json.dumps(filtered, indent=2))]
        elif name == "generate_requirements":
            from ..core.udf import LLMUDF
            udf = LLMUDF()
            symbols = await storage.execute_query("SELECT * FROM current_symbols WHERE version = :v", {"v": version})
            calls = await storage.execute_query("SELECT * FROM current_calls WHERE version = :v", {"v": version})
            req = await udf.generate_requirements(symbols, calls)
            return [types.TextContent(type="text", text=req)]
        else:
            raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream,
                         InitializationOptions(server_name="code-intel", server_version="0.1.0",
                                               capabilities=server.get_capabilities(notification_options=NotificationOptions(),
                                                                                    experimental_capabilities={})))

if __name__ == "__main__":
    asyncio.run(main())
