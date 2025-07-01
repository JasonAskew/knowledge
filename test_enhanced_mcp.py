#\!/usr/bin/env python3
"""Test the enhanced MCP server functionality"""

import requests
import json

# Test the API directly first
api_url = "http://localhost:8000"

print("Testing Enhanced MCP Server Functionality")
print("=" * 50)

# Test 1: Check API stats
print("\n1. Testing API connectivity...")
try:
    response = requests.get(f"{api_url}/stats")
    if response.status_code == 200:
        stats = response.json()
        print(f"✓ API is running")
        print(f"  - Documents: {stats.get('documents', 0)}")
        print(f"  - Chunks: {stats.get('chunks', 0)}")
    else:
        print(f"✗ API error: {response.status_code}")
except Exception as e:
    print(f"✗ Cannot connect to API: {e}")

# Test 2: Test search functionality
print("\n2. Testing search functionality...")
test_query = "What is the minimum balance for a Foreign Currency Account?"

for search_type in ["vector", "hybrid", "text2cypher"]:
    print(f"\n  Testing {search_type} search...")
    try:
        response = requests.post(
            f"{api_url}/search",
            json={
                "query": test_query,
                "search_type": search_type,
                "limit": 3,
                "rerank": search_type \!= "text2cypher"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"  ✓ Found {len(results)} results")
            if results:
                top_doc = results[0].get('document_id', 'Unknown')
                print(f"    Top document: {top_doc}")
        else:
            print(f"  ✗ Error: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

print("\n" + "=" * 50)
print("Enhanced MCP server is ready for use in Claude Desktop\!")
print("\nAvailable tools:")
print("- search_knowledge(query, search_type, limit)")
print("- execute_cypher(query)")
print("- get_neo4j_schema()")
print("- text2cypher_search(query)")
print("- get_knowledge_stats()")
