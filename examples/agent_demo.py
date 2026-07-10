import asyncio
from src.agent_tools import get_langchain_tools

async def main():
    print("🚀 Code-Intel Agent Demo")
    
    # 1. Initialize Tools
    # Note: Assumes Code-Intel API is running at http://localhost:8000
    tools = get_langchain_tools()
    
    if not tools:
        print("❌ LangChain not installed. Run 'pip install code-intel[agents]'.")
        return

    print(f"📦 Loaded {len(tools)} grouped tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")

    # 2. Demonstrate a Tool Call (requires a running server)
    # query_tool = [t for t in tools if t.name == "code_intel_query"][0]
    # try:
    #     result = await query_tool.ainvoke({"rule": "query_dead_code"})
    #     print(f"\n🔍 Dead Code Result:\n{result}")
    # except Exception as e:
    #     print(f"\n⚠️ Note: Server not reachable or no data found. ({e})")

    print("\n💡 To run a full agent, use the following pattern:")
    print("""
    from langchain_ollama import ChatOllama
    from langgraph.prebuilt import create_react_agent

    llm = ChatOllama(model="phi3:mini")
    agent = create_react_agent(llm, tools)
    
    for chunk in agent.stream({"messages": [("user", "Find dead code in this repo")]}):
        print(chunk)
    """)

if __name__ == "__main__":
    asyncio.run(main())
