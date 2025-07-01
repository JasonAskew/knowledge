#!/usr/bin/env python3
"""
Test client for the enhanced MCP server with Neo4j integration
"""

import asyncio
import json
from mcp import Client

async def test_neo4j_search():
    """Test the Neo4j search functionality"""
    # Create client
    client = Client("test-client")
    
    # Connect to the enhanced server
    await client.connect_to_server("enhanced-knowledge-graph")
    
    print("Testing Enhanced MCP Server with Neo4j Integration")
    print("=" * 50)
    
    # Test queries
    test_queries = [
        ("What is the minimum balance requirement?", "neo4j_cypher"),
        ("Show me all fees and charges", "neo4j_cypher"),
        ("What are the interest rates?", "neo4j_cypher"),
        ("List all banking products", "neo4j_cypher"),
        ("Find documents about home loans", "neo4j_cypher"),
        ("What is the minimum balance?", "text2cypher"),  # Compare with text2cypher
        ("What is the minimum balance?", "hybrid"),       # Compare with hybrid search
    ]
    
    for query, search_type in test_queries:
        print(f"\n\nQuery: {query}")
        print(f"Search Type: {search_type}")
        print("-" * 30)
        
        try:
            # Call the search_knowledge tool
            result = await client.call_tool(
                "search_knowledge",
                query=query,
                search_type=search_type,
                limit=3
            )
            
            print(result[:500] + "..." if len(result) > 500 else result)
            
        except Exception as e:
            print(f"Error: {e}")
    
    # Test direct Cypher execution
    print("\n\nTesting Direct Cypher Execution")
    print("=" * 50)
    
    cypher_query = "MATCH (d:Document) RETURN d.title as title LIMIT 5"
    try:
        result = await client.call_tool(
            "execute_cypher",
            query=cypher_query,
            limit=5
        )
        print(f"Cypher: {cypher_query}")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test schema retrieval
    print("\n\nTesting Schema Retrieval")
    print("=" * 50)
    
    try:
        result = await client.call_tool("get_neo4j_schema")
        print(result)
    except Exception as e:
        print(f"Error: {e}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_neo4j_search())