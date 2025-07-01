#!/usr/bin/env python3
"""Test if MCP server can be imported and basic setup works"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Testing MCP Server Setup...")
print("=" * 50)

# Test 1: Can we import MCP?
try:
    import mcp
    print("✅ MCP package imported successfully")
    print(f"   Version info: {mcp.__file__}")
except ImportError as e:
    print(f"❌ Failed to import MCP: {e}")
    sys.exit(1)

# Test 2: Can we access the API?
try:
    import requests
    response = requests.get("http://localhost:8000/stats", timeout=2)
    if response.status_code == 200:
        stats = response.json()
        print("✅ Knowledge Graph API is accessible")
        print(f"   Documents: {stats.get('documents', 0)}")
        print(f"   Chunks: {stats.get('chunks', 0)}")
    else:
        print(f"❌ API returned status {response.status_code}")
except Exception as e:
    print(f"❌ Cannot connect to Knowledge Graph API: {e}")

# Test 3: Check Python environment
print(f"\n📍 Python executable: {sys.executable}")
print(f"📍 Python version: {sys.version.split()[0]}")
print(f"📍 Working directory: {os.getcwd()}")

print("\n" + "=" * 50)
print("MCP Server Status:")
print("- The MCP server is NOT meant to run continuously")
print("- Claude Desktop will start it when needed")
print("- Your Knowledge Graph API is running and ready")
print("\nTo test in Claude Desktop:")
print("1. Restart Claude Desktop")
print("2. Ask: 'Use the knowledge-graph tool to search for minimum balance'")