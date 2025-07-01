#!/usr/bin/env python3
"""
Comprehensive test of the enhanced MCP server with Neo4j integration
"""

import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_server_fixed import search_knowledge, execute_cypher, get_neo4j_schema, text2cypher_search, get_knowledge_stats

async def test_all_functions():
    """Test all MCP server functions"""
    print("Comprehensive Test of Enhanced MCP Server with Neo4j Integration")
    print("=" * 70)
    
    # Test 1: Direct Neo4j search
    print("\n1. Testing Neo4j Direct Search (search_type='neo4j_cypher')")
    print("-" * 50)
    result = await search_knowledge("What is the minimum balance requirement?", search_type="neo4j_cypher", limit=3)
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Test 2: Text2Cypher search
    print("\n\n2. Testing Text2Cypher Search")
    print("-" * 50)
    result = await text2cypher_search("Show me all fees and charges", limit=3)
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Test 3: Vector search comparison
    print("\n\n3. Testing Vector Search (for comparison)")
    print("-" * 50)
    result = await search_knowledge("minimum balance", search_type="vector", limit=3)
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Test 4: Hybrid search
    print("\n\n4. Testing Hybrid Search")
    print("-" * 50)
    result = await search_knowledge("interest rates", search_type="hybrid", limit=3)
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Test 5: Execute direct Cypher
    print("\n\n5. Testing Direct Cypher Execution")
    print("-" * 50)
    cypher = "MATCH (d:Document) RETURN d.filename as name, d.total_pages as pages LIMIT 5"
    result = await execute_cypher(cypher)
    print(result)
    
    # Test 6: Get schema
    print("\n\n6. Testing Schema Retrieval")
    print("-" * 50)
    result = await get_neo4j_schema()
    print(result)
    
    # Test 7: Get stats
    print("\n\n7. Testing Knowledge Base Stats")
    print("-" * 50)
    result = await get_knowledge_stats()
    print(result)
    
    # Test 8: Complex queries
    print("\n\n8. Testing Complex Natural Language Queries")
    print("-" * 50)
    
    complex_queries = [
        "Find documents about home loans",
        "What are the eligibility requirements?",
        "Show me the terms and conditions",
        "List all banking products"
    ]
    
    for query in complex_queries:
        print(f"\nQuery: {query}")
        result = await search_knowledge(query, search_type="neo4j_cypher", limit=2)
        lines = result.split('\n')
        print('\n'.join(lines[:10]) + "\n..." if len(lines) > 10 else result)

if __name__ == "__main__":
    # Set environment variables
    os.environ['NEO4J_PASSWORD'] = 'knowledge123'
    
    # Run the async tests
    asyncio.run(test_all_functions())