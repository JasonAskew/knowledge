#!/usr/bin/env python3
"""
Verify that all imports work correctly for the enhanced server
"""

import sys
print(f"Python: {sys.executable}")
print(f"Python version: {sys.version}")
print("-" * 50)

try:
    print("Checking mcp.server.FastMCP...")
    from mcp.server import FastMCP
    print("✓ FastMCP imported successfully")
except ImportError as e:
    print(f"✗ Failed to import FastMCP: {e}")

try:
    print("\nChecking neo4j...")
    from neo4j import GraphDatabase, AsyncGraphDatabase
    print("✓ Neo4j imported successfully")
except ImportError as e:
    print(f"✗ Failed to import neo4j: {e}")

try:
    print("\nChecking requests...")
    import requests
    print("✓ Requests imported successfully")
except ImportError as e:
    print(f"✗ Failed to import requests: {e}")

try:
    print("\nChecking asyncio...")
    import asyncio
    print("✓ Asyncio imported successfully")
except ImportError as e:
    print(f"✗ Failed to import asyncio: {e}")

try:
    print("\nChecking enhanced_server module...")
    from enhanced_server import mcp, neo4j_client
    print("✓ Enhanced server module imported successfully")
    print(f"  - MCP server name: {mcp.name}")
    print(f"  - Number of tools: {len(mcp._tools)}")
    print(f"  - Tools: {list(mcp._tools.keys())}")
except ImportError as e:
    print(f"✗ Failed to import enhanced_server: {e}")
except Exception as e:
    print(f"✗ Error accessing enhanced_server: {e}")

print("\n" + "-" * 50)
print("Import verification complete!")