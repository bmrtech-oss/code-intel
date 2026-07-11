import json
from typing import Optional, List, Any
from .client import CodeIntelClient

class CodeIntelAgentTools:
    """Grouped tools for Code-Intel AI Agent integrations."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.client = CodeIntelClient(base_url)

    # Core logic functions used by both SDKs
    async def run_query(self, rule: str, symbol: Optional[str] = None, commit_sha: Optional[str] = None) -> str:
        res = await self.client.query(rule, symbol, commit_sha)
        return json.dumps(res, indent=2)

    async def run_analytics(self, symbol: str, commit_sha: Optional[str] = None, depth: int = 3) -> str:
        # Combined impact + predict_impact + predict_next_edit
        impact = await self.client.query("impact", symbol, commit_sha, depth)
        prediction = await self.client.query("predict_impact", symbol, commit_sha)
        cochange = await self.client.query("predict_next_edit", symbol, commit_sha)
        return json.dumps({
            "impact": impact, 
            "prediction": prediction,
            "likely_next_edits": cochange
        }, indent=2)

    async def run_verification(self, symbol: str, commit_sha: Optional[str] = None) -> str:
        # Note: This calls the verify_impact rule which handles the subprocess logic
        res = await self.client.query("verify_impact", symbol, commit_sha)
        return json.dumps(res, indent=2)

    async def run_requirements(self, action: str, job_id: Optional[str] = None, version: Optional[str] = None) -> str:
        if action == "generate":
            res = await self.client.generate_requirements(version)
            return json.dumps(res, indent=2)
        elif action == "status" and job_id:
            res = await self.client.get_job_status(job_id)
            return json.dumps(res, indent=2)
        return "Invalid action or missing job_id"

    async def run_search(self, query: str, limit: int = 5) -> str:
        res = await self.client.semantic_search(query, limit)
        return json.dumps(res, indent=2)

def get_langchain_tools(base_url: str = "http://localhost:8000") -> List[Any]:
    """Factory to return LangChain tools."""
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        return []

    tools_lib = CodeIntelAgentTools(base_url)

    return [
        StructuredTool.from_function(
            coroutine=tools_lib.run_query,
            name="code_intel_query",
            description="Query code structure, call graphs, and dead code. Rules: 'query_call_graph', 'query_dead_code', 'query_cross_repo_imports'."
        ),
        StructuredTool.from_function(
            coroutine=tools_lib.run_analytics,
            name="code_intel_analytics",
            description="Predict blast radius and impact of modifications for a given symbol."
        ),
        StructuredTool.from_function(
            coroutine=tools_lib.run_verification,
            name="code_intel_verification",
            description="Run relevant tests covering the blast radius of a code modification."
        ),
        StructuredTool.from_function(
            coroutine=tools_lib.run_requirements,
            name="code_intel_requirements",
            description="Lifecycle for requirements generation. Actions: 'generate', 'status'."
        ),
        StructuredTool.from_function(
            coroutine=tools_lib.run_search,
            name="code_intel_search",
            description="Semantic natural language search over the codebase."
        )
    ]

def get_google_adk_tools(base_url: str = "http://localhost:8000") -> List[Any]:
    """Factory to return Google AI SDK (ADK) tools."""
    # Note: Google ADK often uses function declarations directly
    tools_lib = CodeIntelAgentTools(base_url)
    
    # We return the bound methods which ADK can inspect for signatures
    return [
        tools_lib.run_query,
        tools_lib.run_analytics,
        tools_lib.run_verification,
        tools_lib.run_requirements,
        tools_lib.run_search
    ]
