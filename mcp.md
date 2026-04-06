# MCP Server Guide: Integration with Claude Code

This guide explains how to run the Model Context Protocol (MCP) server for your Code Intelligence Platform and integrate it with Claude Code. The MCP server exposes the same analysis tools (dead code, call graph, requirements generation) as a set of tools that Claude Code can invoke directly.

## 1. What is the MCP Server?

The MCP server is a lightweight process that communicates over stdio using the Model Context Protocol. It translates tool calls (e.g., `query_dead_code`) into internal API calls to your FastAPI backend and returns the results to Claude Code.

### Exposed Tools

| Tool Name | Description | Input Parameters |
|-----------|-------------|------------------|
| `query_dead_code` | Find functions that are never called | `version` (optional) |
| `query_call_graph` | Get transitive call graph for a function | `function` (required), `version` (optional) |
| `generate_requirements` | Generate epics, features, user stories from code | `version` (optional) |

## 2. Running the MCP Server

The server is part of your platform. You can run it either inside the container or directly from your virtual environment.

### Option A: Inside the Container (recommended for production)

```bash
podman exec -it codeintel-api uv run python -m src mcp
```

This starts the MCP server in the foreground (it will block). For integration with Claude Code, you need the command to be available as a standalone executable.

### Option B: Locally (for development)

Ensure your environment is set up:

```bash
source .venv/bin/activate
python -m src mcp
```

### Option C: As a Persistent Service

Create a systemd service or run it in a separate container. In `podman-compose.yml`, add an `mcp` service:

```yaml
mcp:
  build: .
  container_name: codeintel-mcp
  environment:
    - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/codeintel
    - REDIS_HOST=redis
    - OLLAMA_URL=http://ollama:11434
  volumes:
    - ./src:/app/src
  command: ["uv", "run", "python", "-m", "src", "mcp"]
  depends_on:
    - postgres
    - redis
    - ollama
  restart: unless-stopped
```

However, note that MCP servers communicate over stdio, so the container must be attached to Claude Code's process. A simpler approach is to run it as a subprocess from Claude Code's configuration.

## 3. Configuring Claude Code

Claude Code looks for an `mcp.json` configuration file. You can place it in your project root or in Claude Code's global config directory.

### Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "code-intel": {
      "command": "podman",
      "args": ["exec", "-i", "codeintel-api", "uv", "run", "python", "-m", "src", "mcp"]
    }
  }
}
```

If you are not using Podman, or you want to run the MCP server locally without containers, use:

```json
{
  "mcpServers": {
    "code-intel": {
      "command": "python",
      "args": ["-m", "src", "mcp"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:password@localhost:5432/codeintel",
        "REDIS_HOST": "localhost",
        "OLLAMA_URL": "http://localhost:11434"
      }
    }
  }
}
```

### Important Notes:

- The `command` must be an executable that Claude Code can spawn. Using `podman exec` works because Claude Code runs on the host (WSL) and can execute Podman commands.
- For Windows/WSL, ensure `podman` is in your PATH.
- The `-i` flag is needed to keep stdin open for stdio communication.

## 4. Testing the Integration

After configuring Claude Code, restart it (if already running). Then in a conversation, try:

```
@code-intel query_dead_code
```

Or ask naturally:

> "What are the dead functions in my codebase?"

Claude Code will call the tool and show the results.

## 5. Troubleshooting

### MCP server not starting

- Check the command: run it manually in your terminal to see errors.
- Ensure the API backend is running (PostgreSQL, Redis, etc.) because the MCP server connects to it.
- Verify that `uv` and Python are available in the container.

### Claude Code cannot find the server

- Check the path to `mcp.json`. It should be in the directory where you launch Claude Code, or in `~/.config/claude/mcp.json`.
- Look at Claude Code's logs (if available).

### Tools not showing up

- Ensure the MCP server is running before Claude Code starts. You may need to start it separately.
- Verify that the server implements the `list_tools` handler correctly.

## 6. Example Conversation

Once integrated, you can interact with Claude Code like this:

**User:** Show me dead code in my repository.

**Claude Code:** *[calls `query_dead_code`]*

> The dead code analysis shows the following functions are never called:
> - `add` in `calculator.py`
> - `subtract` in `calculator.py`
> - `multiply` in `calculator.py`
> - `divide` in `calculator.py`

**User:** Generate an epic for refactoring these.

**Claude Code:** *[calls `generate_requirements`]*

> Based on the code, here is a requirement:
> **Epic**: Remove Unused Functions
> **Feature**: Dead Code Cleanup
> **User Story**: As a developer, I want to remove dead functions so that the codebase is easier to maintain.
> **Acceptance Criteria**:
> - Functions `add`, `subtract`, `multiply`, `divide` are deleted.
> - No regression in remaining code.
> **Tasks**:
> - Delete unused functions from `calculator.py`
> - Update tests to remove references

## 7. Extending the MCP Server

To add a new tool, modify `src/mcp/server.py`:

1. Add a new `types.Tool` definition to the `TOOLS` list.
2. Add a branch in `handle_call_tool` for the new tool name.
3. Implement the logic (usually calling an existing API endpoint or core function).

After changes, rebuild the container and restart the MCP server.

## 8. Security Considerations

- The MCP server exposes database queries. Ensure your API backend has proper authentication if exposed externally.
- For local use, this is acceptable. For remote deployments, consider running the MCP server only on trusted machines.

Now your Claude Code can harness the full power of your code intelligence platform directly from the chat interface!