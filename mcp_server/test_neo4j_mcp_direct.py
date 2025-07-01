#!/usr/bin/env python3
"""Test direct Neo4j MCP execution"""

import subprocess
import json
import os

# Test if we can query Neo4j directly
env = os.environ.copy()
env.update({
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "knowledge123"
})

# Create a test query
test_query = """
MATCH (c:Chunk) 
WHERE toLower(c.text) CONTAINS 'minimum balance'
RETURN c.text as text, c.page_num as page
LIMIT 3
"""

print("Testing direct Neo4j query...")
print("Query:", test_query)
print("-" * 60)

try:
    # Run the query using neo4j CLI or cypher-shell if available
    # First, let's try using the Neo4j Python driver directly
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(
        env["NEO4J_URI"],
        auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"])
    )
    
    with driver.session() as session:
        result = session.run(test_query)
        records = list(result)
        
        print(f"Found {len(records)} results:")
        for i, record in enumerate(records, 1):
            print(f"\nResult {i}:")
            print(f"Page: {record['page']}")
            print(f"Text: {record['text'][:200]}...")
            
    driver.close()
    print("\n✓ Direct Neo4j connection works!")
    
except ImportError:
    print("Neo4j driver not installed")
except Exception as e:
    print(f"Error: {e}")

print("\nFor the MCP proxy, we'll use the text2cypher API fallback since mcp-neo4j-cypher requires complex setup.")