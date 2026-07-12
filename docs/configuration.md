# Code-Intel Configuration & Decision Guide

Code-Intel is highly configurable to balance performance, disk space, and privacy. This guide helps you make the right choices during the interactive setup.

---

## ⚡ Performance Tiers: Which one to choose?

During `./install.sh`, you will be asked to select a performance tier. This controls which AI libraries are installed and how much disk space is consumed.

| Tier | Host Space | Image Space | Features | Recommended For |
| :--- | :--- | :--- | :--- | :--- |
| **Minimal** (Default) | **~600 MB** | **~800 MB** | Graph queries, Dead Code, Impact Analysis, Requirement Gen. | **Most users.** Fast setup, low RAM, covers 90% of use cases. |
| **Standard** | **~6.3 GB** | **~5.5 GB** | All above + **Semantic Search** (Natural Language queries). | Users who want to search code by "meaning" using CPU. |
| **High** | **~7.5 GB** | **~12 GB** | All above + **GPU Acceleration** (Nvidia CUDA). | Production environments or massive repositories (>1M lines). |

### Trade-offs:
- **Minimal Tier**: You lose the ability to ask natural language questions like *"How do we handle login?"*. However, you can still find exactly what calls the login function via the topological graph.
- **Standard vs High**: Standard is significantly smaller but relies on your CPU for indexing. For most repositories, this is perfectly fine. High tier is only necessary if you have an Nvidia GPU and need sub-second indexing for very large codebases.

---

## 🤖 LLM Providers: Local vs Cloud

The "Requirements Generation" feature requires an LLM.

| Provider | Setup Time | Space Used | Speed | Privacy |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | **< 1 min** | **0 GB** | **Very Fast** | Remote |
| **OpenRouter** | **< 1 min** | **0 GB** | **Fast** | Remote |
| **Local Ollama** | **~10 min** | **~5 GB** | **Slow** (on CPU) | **Maximum** |

### Recommendations:
1. **Best Experience**: Use **Google Gemini**. It's free (for standard tiers), extremely fast, and requires no local model downloads.
2. **Maximum Privacy**: Use **Local Ollama**. Your code never leaves your machine, but ensure you have at least 16GB of RAM and 5GB of free disk space.

---

## 💾 Saving Host Disk Space

If you want to keep your host machine clean, use the `--skip-venv` flag:

```bash
./install.sh --skip-venv
```

**Why do this?**
The platform runs entirely inside containers. By skipping the local virtual environment (`.venv`), you save **5.3 GB** of host disk space. You only need the local venv if you are a developer planning to run/debug the Python code directly in your IDE (like Cursor or VSCode).

---

## 🧹 Cleanup & Reset

If an installation fails due to disk space or you want to start fresh:

```bash
./purge.sh
```

This will:
1. Stop and remove all Code-Intel containers.
2. Delete all related images and volumes.
3. Clear your local `uv` package cache and temporary build files.
4. (Optional) Perform a full system prune.

### 🔌 Port Conflict Troubleshooting

Code-Intel uses the following ports by default:
- **8000**: REST API
- **5432**: PostgreSQL
- **6379**: Redis
- **11434**: Ollama (if using local models)

If `install.sh` reports a port conflict:
1. **Reset everything**: Run `./purge.sh`. It will attempt to stop Code-Intel containers and kill any orphaned processes on these ports.
2. **Check other services**: Ensure you don't have another instance of Postgres or Redis running on your host machine.
3. **Manual clear**: Run `lsof -i :<PORT>` to find the process ID and `kill -9 <PID>` to clear it.

---

## Remote Git Ingestion

Code-Intel supports indexing remote repositories directly:

```bash
# In the CLI (Host)
uv run code-intel analyze https://github.com/user/repo.git --branch main

# Via the Container (if skipping host venv)
docker compose exec api code-intel analyze https://github.com/user/repo.git

# Via the API
curl -X POST http://localhost:8000/analyze -d '{"repo_path": "https://github.com/user/repo.git"}'

### 🎬 Using the Interactive Demo for custom repos

You can run the full strategic demo on your own repository to see how Code-Intel generates requirements and predicts impact for your specific code:

```bash
./demo.sh --repo-url https://github.com/your/repo.git --version-name my-project
```
```
