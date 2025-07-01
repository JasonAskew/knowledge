#!/usr/bin/env python3
"""
Check what data is in Neo4j
"""

import os
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")

def check_neo4j_data():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # Count nodes by label
        print("Node counts by label:")
        labels = ["Document", "Chunk", "Entity"]
        for label in labels:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            count = result.single()['count']
            print(f"  {label}: {count}")
        
        # Sample chunks with "balance" text
        print("\n\nSample chunks containing 'balance':")
        result = session.run("""
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
            WHERE toLower(c.text) CONTAINS 'balance'
            RETURN d.title as document, c.text as text, c.page_num as page
            LIMIT 5
        """)
        
        chunks = list(result)
        if chunks:
            for i, chunk in enumerate(chunks, 1):
                print(f"\n{i}. Document: {chunk['document']}")
                print(f"   Page: {chunk['page']}")
                print(f"   Text: {chunk['text'][:200]}...")
        else:
            print("  No chunks found containing 'balance'")
        
        # Check if chunks have text property
        print("\n\nChecking chunk properties:")
        result = session.run("""
            MATCH (c:Chunk)
            RETURN keys(c) as properties
            LIMIT 1
        """)
        
        record = result.single()
        if record:
            print(f"  Chunk properties: {record['properties']}")
        
        # Sample chunk content
        print("\n\nSample chunk content:")
        result = session.run("""
            MATCH (c:Chunk)
            RETURN c
            LIMIT 3
        """)
        
        for i, record in enumerate(result, 1):
            chunk = record['c']
            print(f"\n{i}. Chunk:")
            for key, value in chunk.items():
                if key == 'text' or key == 'content':
                    print(f"   {key}: {str(value)[:200]}...")
                else:
                    print(f"   {key}: {value}")
    
    driver.close()

if __name__ == "__main__":
    check_neo4j_data()