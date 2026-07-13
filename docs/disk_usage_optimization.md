# Code-Intel: Disk Usage Diagnosis & Optimization Report

## 🔍 Root Cause Analysis

The excessive disk usage (>30 GB) reported by users was primarily caused by three "hidden" factors in the original configuration:

1.  **Local LLM Models (~5 GB)**: The installer defaulted to Local Ollama, which silently triggers a multi-gigabyte model download (`phi3`).
2.  **Nvidia/CUDA Dependency Bloat (~4 GB)**: The original configuration pulled full PyTorch and Nvidia CUDA binaries, even on systems without compatible GPUs.
3.  **Large Build Context (~10 GB+)**: A missing `.dockerignore` caused the entire local `.venv` and build artifacts to be sent to the container engine during every build.
4.  **Semantic Search Dependencies (~5 GB)**: Heavy libraries like `txtai`, `torch`, and `transformers` were installed by default.

---

## ⚡ Performance Tier Architecture

To resolve this, we have implemented a **Performance Tier** selection system. This allows users to choose the footprint that matches their needs.

| Tier | Host Space | Image Space | Key Features | Recommended For |
| :--- | :--- | :--- | :--- | :--- |
| **Minimal (Default)** | **~600 MB** | **~800 MB** | Graph, Impact, Dead Code, Requirements | **Most Users** |
| **Standard** | **~6.3 GB** | **~5.5 GB** | All above + **Semantic Search** | Power Users |
| **High** | **~7.5 GB** | **~12 GB** | All above + **GPU Acceleration** | Production |

---

## 🛠️ Action Plan: Fixing Current Disk Usage

If your system is already bloated, follow these steps:

### 1. The Purge (Safe Cleanup)
Run the new cleanup utility to stop containers and clear all Code-Intel related images and local caches:
```bash
./purge.sh
```

### 2. Lightweight Installation
Re-install using the **Minimal** tier and **Cloud LLM** to keep the footprint under 1GB:
```bash
./install.sh --skip-venv
```
- **Selection**: Choose **Google Gemini** (provide your API key).
- **Selection**: Choose **Minimal Tier**.

---

## 🛡️ Preventive Modifications (Fixed in v0.1.1)

The following changes have been applied to the repository to prevent future bloat:

- **`.dockerignore`**: Added to exclude large directories from the container build context.
- **Multi-Stage Dockerfile**: Implemented to keep production images lean.
- **CPU-First Strategy**: `pyproject.toml` now forces CPU-optimized PyTorch by default.
- **Optional Extras**: Semantic search libraries are now in an optional `[semantic]` group.
- **Interactive Wizard**: `install.sh` now makes cloud configuration mandatory and recommends it as the fastest path.

---

## 🧪 CI Verification
The CI pipeline has been updated (`.github/workflows/ci.yml`) to ensure both Lightweight and Full modes are tested, while preventing `ModuleNotFoundError` during test collection using `pytest.importorskip`.
