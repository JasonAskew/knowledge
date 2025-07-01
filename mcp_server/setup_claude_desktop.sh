#!/bin/bash

echo "Knowledge Graph MCP Server Setup for Claude Desktop"
echo "=================================================="
echo ""

CONFIG_PATH="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# Check if Claude Desktop config exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "❌ Claude Desktop config not found at: $CONFIG_PATH"
    echo "   Please make sure Claude Desktop is installed"
    exit 1
fi

echo "✅ Found Claude Desktop config"
echo ""

# Backup existing config
BACKUP_PATH="${CONFIG_PATH}.backup_$(date +%Y%m%d_%H%M%S)"
cp "$CONFIG_PATH" "$BACKUP_PATH"
echo "📁 Created backup at: $BACKUP_PATH"
echo ""

# Show current config
echo "Current MCP servers configured:"
cat "$CONFIG_PATH" | python -m json.tool | grep -A1 '"mcpServers"' | grep -E '^\s*"[^"]+"\s*:' | sed 's/[":,]//g' | sed 's/^\s*/  - /'
echo ""

# Ask user if they want to proceed
echo "This will add the 'knowledge-graph' MCP server to your Claude Desktop."
echo "The server will connect to your Knowledge Graph API at http://localhost:8000"
echo ""
read -p "Do you want to proceed? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Setup cancelled"
    exit 1
fi

# Copy the updated config
cp "claude_desktop_config_updated.json" "$CONFIG_PATH"
echo "✅ Updated Claude Desktop configuration"
echo ""

echo "Next steps:"
echo "1. Make sure your Knowledge Graph API is running:"
echo "   cd /Users/jaskew/workspace/Skynet/claude/knowledge/docker"
echo "   docker-compose up -d"
echo ""
echo "2. Restart Claude Desktop"
echo ""
echo "3. Test the integration by asking Claude:"
echo "   'Use the knowledge-graph tool to search for minimum account balance'"
echo ""
echo "✅ Setup complete!"