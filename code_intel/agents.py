import json
from .client import CodeIntelClient
from .agent_tools import get_langchain_tools, get_google_adk_tools

class AgentIntegrator:
    """Helper class to integrate Code-Intel with various AI Agent frameworks."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.client = CodeIntelClient(base_url)

    def generate_cursor_rules(self) -> str:
        """Generates a .cursorrules content tailored for Code-Intel usage."""
        rules = {
            "instruction": "You are an expert developer with access to Code-Intel, a topological code intelligence platform.",
            "api_endpoint": self.client.base_url,
            "rules": [
                "When asked about code structure, use the Code-Intel MCP tools or API.",
                "Always check for dead code using 'query_dead_code' before proposing deletions.",
                "Use 'predict_impact' to assess the blast radius of your proposed changes.",
                "Verify your requirements against the code using the 'trace' endpoint."
            ]
        }
        return json.dumps(rules, indent=2)

    def get_langchain_tools(self):
        return get_langchain_tools(self.client.base_url)

    def get_google_adk_tools(self):
        return get_google_adk_tools(self.client.base_url)
