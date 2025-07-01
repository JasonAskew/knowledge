#!/bin/bash

echo "Setting up Knowledge Graph MCP Server..."

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "To configure Claude Desktop, add the following to your config file:"
echo ""
echo "macOS: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "Windows: %APPDATA%\\Claude\\claude_desktop_config.json"
echo "Linux: ~/.config/claude/claude_desktop_config.json"
echo ""
echo '{
  "mcpServers": {
    "knowledge-graph": {
      "command": "'$(pwd)'/venv/bin/python",
      "args": ["-m", "mcp_server.standalone_server"],
      "cwd": "'$(pwd)'",
      "env": {
        "API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}'