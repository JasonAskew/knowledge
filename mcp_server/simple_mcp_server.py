#!/usr/bin/env python3
"""
Simple MCP Server for Knowledge Graph System
This provides a basic example of how to configure Claude Desktop
"""

import asyncio
import json
import os
from typing import Any

# For this example, we'll create a simple server that demonstrates the config
print("""
Knowledge Graph MCP Server Configuration Guide
==============================================

To configure Claude Desktop to use the Knowledge Graph MCP server:

1. Locate your Claude Desktop configuration file:
   - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
   - Windows: %APPDATA%\\Claude\\claude_desktop_config.json  
   - Linux: ~/.config/claude/claude_desktop_config.json

2. Add the following configuration to the file:

{
  "mcpServers": {
    "knowledge-graph": {
      "command": "python",
      "args": [
        "-m", 
        "mcp_server.standalone_server"
      ],
      "cwd": "/Users/jaskew/workspace/Skynet/claude/knowledge",
      "env": {
        "API_BASE_URL": "http://localhost:8000",
        "PYTHONPATH": "/Users/jaskew/workspace/Skynet/claude/knowledge"
      }
    }
  }
}

3. If you already have other MCP servers configured, merge this into your existing config:

{
  "mcpServers": {
    "your-existing-server": {
      // ... existing config ...
    },
    "knowledge-graph": {
      "command": "python",
      "args": ["-m", "mcp_server.standalone_server"],
      "cwd": "/Users/jaskew/workspace/Skynet/claude/knowledge",
      "env": {
        "API_BASE_URL": "http://localhost:8000",
        "PYTHONPATH": "/Users/jaskew/workspace/Skynet/claude/knowledge"
      }
    }
  }
}

4. Save the file and restart Claude Desktop

5. Once restarted, you should see "knowledge-graph" in the available tools

6. Test it by asking Claude:
   - "Use the knowledge-graph tool to search for minimum account balance"
   - "Query the knowledge graph for foreign exchange options"
   - "Get statistics about the knowledge base using knowledge-graph"

IMPORTANT NOTES:
- Make sure the Knowledge Graph API is running at http://localhost:8000
- The cwd path must be absolute and point to your knowledge directory
- If you're using a different API URL, update API_BASE_URL accordingly

For production deployment with authentication:

{
  "mcpServers": {
    "knowledge-graph": {
      "command": "python",
      "args": ["-m", "mcp_server.standalone_server"],
      "cwd": "/Users/jaskew/workspace/Skynet/claude/knowledge",
      "env": {
        "API_BASE_URL": "https://your-api-domain.com",
        "API_KEY": "your-secure-api-key",
        "PYTHONPATH": "/Users/jaskew/workspace/Skynet/claude/knowledge"
      }
    }
  }
}
""")