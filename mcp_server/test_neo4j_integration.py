#!/usr/bin/env python3
"""
Test the Neo4j integration in the enhanced MCP server
"""

import os
import sys
from neo4j import GraphDatabase, basic_auth

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")

def test_neo4j_connection():
    """Test basic Neo4j connection"""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USERNAME, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # Test basic query
            result = session.run("MATCH (n) RETURN count(n) as node_count LIMIT 1")
            record = result.single()
            print(f"✓ Connected to Neo4j successfully")
            print(f"  Total nodes in database: {record['node_count']}")
        
        # Test schema query
        with driver.session() as session:
            # Get node labels
            result = session.run("CALL db.labels()")
            labels = [record[0] for record in result]
            print(f"\n✓ Node labels: {', '.join(labels)}")
            
            # Get relationship types
            result = session.run("CALL db.relationshipTypes()")
            rel_types = [record[0] for record in result]
            print(f"✓ Relationship types: {', '.join(rel_types)}")
            
            # Sample Document nodes
            result = session.run("""
                MATCH (d:Document) 
                RETURN d.title as title, d.doc_id as id 
                LIMIT 5
            """)
            docs = list(result)
            print(f"\n✓ Sample documents ({len(docs)} shown):")
            for doc in docs:
                print(f"  - {doc['title']} (ID: {doc['id']})")
        
        driver.close()
        print("\n✓ All Neo4j tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Neo4j connection failed: {e}")
        print(f"  URI: {NEO4J_URI}")
        print(f"  Username: {NEO4J_USERNAME}")
        return False

def test_natural_language_patterns():
    """Test natural language to Cypher conversion patterns"""
    print("\n\nTesting Natural Language to Cypher Patterns:")
    print("=" * 50)
    
    # Import the conversion function
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from enhanced_server_fixed import natural_language_to_cypher
    
    test_queries = [
        "What is the minimum balance requirement?",
        "Show me all fees and charges",
        "What are the interest rates?",
        "List all products",
        "Find documents about home loans",
        "Show entities in the system",
        "What are the eligibility requirements?",
        "Show me the terms and conditions",
        "Find document about credit cards",
        "Search for Westpac entity"
    ]
    
    for query in test_queries:
        cypher = natural_language_to_cypher(query, limit=5)
        print(f"\nQuery: {query}")
        print(f"Cypher: {cypher.strip()}")

if __name__ == "__main__":
    print("Testing Neo4j Integration")
    print("=" * 50)
    
    # Test connection
    if test_neo4j_connection():
        # Test pattern conversion
        test_natural_language_patterns()
    else:
        print("\n⚠️  Please ensure Neo4j is running and accessible")
        print(f"   Expected connection: {NEO4J_URI}")