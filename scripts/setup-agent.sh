#!/bin/bash
set -e

echo "🚀 Setting up Code-Intel Agent Integration..."

# Detect OS
OS="$(uname)"
case "${OS}" in
    Darwin*)    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json";;
    Linux*)     CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json";;
    *)          echo "Unsupported OS: ${OS}"; exit 1;;
esac

echo "📍 Claude Desktop config path: $CLAUDE_CONFIG"

if [ ! -f "templates/claude_config.json" ]; then
    echo "❌ Error: templates/claude_config.json not found."
    exit 1
fi

# Check if code-intel is installed
if ! command -v code-intel &> /dev/null; then
    echo "⚠️ 'code-intel' command not found. Attempting to run via 'uv run'..."
    uv run python -m src.cli.main setup-claude
    uv run python -m src.cli.main setup-cursor
else
    echo "🔄 Running setup via global CLI..."
    code-intel setup-claude
    code-intel setup-cursor
fi

echo "🎉 Setup complete! Restart your AI assistant to begin."
