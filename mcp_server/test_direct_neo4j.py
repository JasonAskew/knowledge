#!/usr/bin/env python3
"""
Direct test of Neo4j integration functions
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_server_fixed import natural_language_to_cypher, execute_neo4j_direct, neo4j_conn

def test_pattern_matching():
    """Test natural language to Cypher pattern matching"""
    print("Testing Natural Language to Cypher Conversion")
    print("=" * 50)
    
    test_queries = [
        "What is the minimum balance requirement?",
        "Show me all fees and charges",
        "What are the interest rates?",
        "List all products",
        "Find documents about home loans",
        "What are the eligibility requirements?",
        "Random query that doesn't match patterns"
    ]
    
    for query in test_queries:
        cypher = natural_language_to_cypher(query, limit=3)
        print(f"\nQuery: {query}")
        print(f"Generated Cypher:")
        print(cypher.strip())
        print("-" * 30)

def test_neo4j_execution():
    """Test direct Neo4j execution"""
    print("\n\nTesting Direct Neo4j Execution")
    print("=" * 50)
    
    if not neo4j_conn:
        print("⚠️  Neo4j connection not available")
        print("   Testing with mock response...")
        
    test_query = "What is the minimum balance?"
    print(f"\nQuery: {test_query}")
    
    result = execute_neo4j_direct(test_query, limit=3)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Cypher Query: {result.get('cypher_query', 'N/A')}")
        print(f"Total Results: {result.get('total_results', 0)}")
        
        for i, res in enumerate(result.get('results', [])[:3], 1):
            print(f"\nResult {i}:")
            print(f"  Document: {res.get('document_id')}")
            print(f"  Page: {res.get('page_num')}")
            print(f"  Text: {res.get('text', '')[:200]}...")

if __name__ == "__main__":
    test_pattern_matching()
    test_neo4j_execution()