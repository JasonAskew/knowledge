#!/usr/bin/env python3
"""
Test script for the enhanced FastMCP server
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_server import mcp, neo4j_client

async def test_server():
    """Test the enhanced server functionality"""
    print("Testing Enhanced FastMCP Server")
    print("=" * 50)
    
    # Test startup
    print("\n1. Testing startup...")
    await mcp._startup_handlers[0]()  # Call the startup handler
    
    # Test basic search
    print("\n2. Testing basic search...")
    try:
        result = await mcp._tools["search_knowledge"](
            query="What is the minimum balance requirement?",
            search_type="hybrid",
            limit=3
        )
        print(f"Search result preview: {result[:200]}...")
    except Exception as e:
        print(f"Search error: {e}")
    
    # Test stats
    print("\n3. Testing stats...")
    try:
        stats = await mcp._tools["get_stats"]()
        print(f"Stats: {stats[:200]}...")
    except Exception as e:
        print(f"Stats error: {e}")
    
    # Test Neo4j schema (if available)
    print("\n4. Testing Neo4j schema...")
    try:
        schema = await mcp._tools["get_neo4j_schema"]()
        print(f"Schema: {schema[:200]}...")
    except Exception as e:
        print(f"Schema error: {e}")
    
    # Test shutdown
    print("\n5. Testing shutdown...")
    await mcp._shutdown_handlers[0]()  # Call the shutdown handler
    
    print("\n" + "=" * 50)
    print("Test complete!")

if __name__ == "__main__":
    asyncio.run(test_server())