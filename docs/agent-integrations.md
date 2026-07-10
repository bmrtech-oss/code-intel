# AI Agent Integrations Guide

This guide explains how to connect Code-Intel with various AI Agent frameworks and IDEs.

## 🧠 Integration Decision Tree

| Use Case | Recommended Solution | Setup Command |
| :--- | :--- | :--- |
| **Claude Desktop** | MCP Integration (System-wide) | `code-intel setup-claude` |
| **Cursor / Continue** | IDE Rules & MCP Integration | `code-intel setup-cursor` |
| **Python Agent SDK** | LangChain / CrewAI Wrappers | `pip install code-intel[agents]` |
| **Google Vertex / ADK** | Native ADK Tool Bindings | `get_google_adk_tools()` |

---

## 1. IDE & Desktop Integrations

### Claude Desktop (MCP)
Code-Intel provides a first-class Model Context Protocol (MCP) server. To link it to Claude Desktop:
```bash
code-intel setup-claude
```
*Note: Ensure your `DATABASE_URL` is exported in your environment or provided in the config.*

### Cursor / Continue
Enable Code-Intel's topological context in your IDE by adding project-specific rules:
```bash
code-intel setup-cursor
```
This adds a `.cursorrules` file to your project that instructs the AI on how to use Code-Intel tools.

---

## 2. Python SDK Integrations

### LangChain / CrewAI
We provide pre-built, grouped tools for LangChain to keep the agent's context window clean.

```python
from src.agent_tools import get_langchain_tools

# Get 4 high-level grouped tools
tools = get_langchain_tools(base_url="http://localhost:8000")

# Integration with a ReAct agent
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama

llm = ChatOllama(model="phi3:mini")
agent = create_react_agent(llm, tools)
```

### Google AI SDK (ADK)
Native method bindings for Google's Generative AI SDK:

```python
from src.agent_tools import get_google_adk_tools
import google.generativeai as genai

tools = get_google_adk_tools()
model = genai.GenerativeModel("gemini-1.5-flash", tools=tools)
```

---

## 🚀 Instant Setup via Docker/Podman

If you want to run the entire stack including the MCP server in one command:

```bash
podman-compose --profile mcp up -d
```

This starts:
- **API**: The main REST backend.
- **Worker**: Background ingestion worker.
- **Ollama**: Local LLM runner.
- **MCP Server**: The global agent integration point.
