# Installation and Setup Guide

This guide walks through the installation of Code-Intel using our **Interactive Setup Wizard**.

---

## 🚀 One-Click Installation (Recommended)

The easiest way to get started is to run the installer and follow the on-screen prompts:

```bash
./install.sh
```

### What happens during installation?

1. **LLM Configuration**: The wizard will ask for an LLM provider.
   - **Google Gemini** (Recommended): Fastest setup. Just paste your API key.
   - **OpenRouter**: Great for using Claude or other specific models.
   - **Local Ollama**: For users who want 100% privacy and have 5GB+ of disk space.

2. **Performance Tier**: You will choose a "Size vs. Features" tier.
   - **Minimal** (Default): Fast, small (~800MB), includes all core topological features.
   - **Standard**: Adds Semantic Search using your CPU (~5.5GB).
   - **High**: Adds Nvidia GPU acceleration for massive repositories (~12GB).

3. **Dependency Sync**: The script installs Python dependencies via `uv`.
4. **Services**: Starts Postgres, Redis, and (optionally) Ollama containers.
5. **Migrations**: Automatically sets up the database schema.

---

## 💾 Minimizing Disk Usage

If you have limited disk space, use the following combination:

```bash
./install.sh --skip-venv
```

- **Interactive Choices**: Select **Google Gemini** and the **Minimal** tier.
- **Benefit**: This keeps your host machine clean and uses less than 1GB of total space for containers.

---

## 🎬 Verifying the Setup

After installation, run the strategic demo to ensure everything is working:

```bash
./demo.sh
```

If you are using Google Gemini, you can skip local model checks:
```bash
./demo.sh --provider google --google-key YOUR_KEY
```

---

## 🧹 Troubleshooting & Cleanup

If the installation is stuck or fails:
1. **Clean up**: Run `./purge.sh` to remove all broken containers and images.
2. **Space**: Ensure you have at least 2GB of free space (for Minimal tier).
3. **Engine**: If Podman/Docker is unresponsive, the installer will attempt to restart it for you.

For advanced settings, see the [Configuration Guide](docs/configuration.md).
