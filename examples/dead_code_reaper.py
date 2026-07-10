import os
import asyncio

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from src.agent_tools import get_langchain_tools

# --- 1. Custom Tools for Git and File Operations ---

@tool
def git_create_branch(branch_name: str):
    """Creates and checks out a new git branch."""
    os.system(f"git checkout -b {branch_name}")
    return f"Created and checked out branch: {branch_name}"

@tool
def delete_code_block(file_path: str, start_line: int, end_line: int):
    """Deletes a block of code from a file. Lines are 1-indexed."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Adjust to 0-indexed and delete
        del lines[start_line-1:end_line]
        
        with open(file_path, 'w') as f:
            f.writelines(lines)
        return f"Deleted lines {start_line} to {end_line} in {file_path}"
    except Exception as e:
        return f"Error deleting code: {e}"

@tool
def git_commit_and_push(message: str):
    """Commits changes and simulates a push."""
    os.system(f"git add . && git commit -m '{message}'")
    return f"Changes committed with message: {message}. (Push simulated)"

@tool
def submit_github_pr(repo_name: str, branch_name: str, title: str, body: str):
    """Submits a Pull Request to GitHub. Requires GITHUB_TOKEN."""
    try:
        from github import Github
        g = Github(os.getenv("GITHUB_TOKEN"))
        repo = g.get_repo(repo_name)
        pr = repo.create_pull(title=title, body=body, head=branch_name, base="main")
        return f"Successfully created PR #{pr.number}: {pr.html_url}"
    except Exception as e:
        return f"Error creating PR (Simulating success for demo): {e}"

# --- 2. Define the Agent ---

async def run_reaper():
    print("💀 Starting the Dead Code Reaper Agent...")

    # Initialize Code-Intel Tools
    code_intel_tools = get_langchain_tools()
    if not code_intel_tools:
        print("❌ Error: LangChain dependencies not found.")
        return

    # Combine with Git/File tools
    all_tools = code_intel_tools + [
        git_create_branch,
        delete_code_block,
        git_commit_and_push,
        submit_github_pr
    ]

    # Initialize LLM (Phi-3 is small enough for local loop)
    llm = ChatOllama(model="phi3:mini", temperature=0)

    # Create the ReAct agent
    agent = create_react_agent(llm, all_tools)

    # The Strategic Mission
    prompt = """
    You are the 'Dead Code Reaper'. Your mission is to safely clean up technical debt.
    
    Mission Steps:
    1. Call 'code_intel_query' with rule='query_dead_code' to find unused functions.
    2. Filter candidates to only those with confidence 1.0 (static analysis certainties).
    3. For each candidate (one by one):
       a. Create a unique git branch (e.g., 'cleanup/dead-function-name').
       b. Identify the file and line range from the code intel data.
       c. Delete the code block using 'delete_code_block'.
       d. Call 'code_intel_verification' for the symbol to run impact-aware tests.
       e. If the verification status is 'success':
          - Commit the change with 'git_commit_and_push'.
          - Call 'submit_github_pr' with a concise title and description summarizing the change and citing the Code-Intel fact IDs.
       f. If verification fails, revert or move to next.
    
    Execute the first mission step now.
    """

    # Run the mission
    inputs = {"messages": [HumanMessage(content=prompt)]}
    async for chunk in agent.astream(inputs, stream_mode="values"):
        message = chunk["messages"][-1]
        if hasattr(message, "content") and message.content:
            print(f"\n🤖 Reaper: {message.content}")

if __name__ == "__main__":
    try:
        asyncio.run(run_reaper())
    except KeyboardInterrupt:
        print("\n⏹️ Reaper stopped by user.")
