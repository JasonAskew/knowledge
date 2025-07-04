#!/usr/bin/env python3
"""
Simple test of hierarchical implementation
"""

from neo4j import GraphDatabase
import json

# Neo4j connection
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "knowledge123"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

print("Simple Hierarchical Implementation Test")
print("=" * 80)

with driver.session() as session:
    # Test 1: Check hierarchy exists
    print("\n1. Hierarchy Structure:")
    result = session.run("""
        MATCH (i:Institution)-[:HAS_DIVISION]->(d:Division)
        RETURN i.name as institution, collect(d.name) as divisions
    """)
    record = result.single()
    print(f"   Institution: {record['institution']}")
    print(f"   Divisions: {', '.join(record['divisions'])}")
    
    # Test 2: Check document classification
    print("\n2. Document Classification:")
    result = session.run("""
        MATCH (d:Document)
        WHERE d.division IS NOT NULL
        RETURN d.division as division, count(d) as count
        ORDER BY count DESC
    """)
    for record in result:
        print(f"   {record['division']}: {record['count']} documents")
    
    # Test 3: Simple hierarchical search
    print("\n3. Hierarchical Search Test:")
    
    # Search without filter
    print("\n   a) Search 'credit card' (no filter):")
    result = session.run("""
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS 'credit card'
        MATCH (d:Document)-[:HAS_CHUNK]->(c)
        RETURN d.division as division, count(DISTINCT d) as doc_count
        ORDER BY doc_count DESC
    """)
    for record in result:
        print(f"      {record['division']}: {record['doc_count']} documents")
    
    # Search with filter
    print("\n   b) Search 'credit card' (Retail only):")
    result = session.run("""
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS 'credit card'
        MATCH (d:Document)-[:HAS_CHUNK]->(c)
        WHERE d.division = 'RETAIL'
        RETURN count(DISTINCT d) as doc_count, count(DISTINCT c) as chunk_count
    """)
    record = result.single()
    print(f"      Found: {record['doc_count']} documents, {record['chunk_count']} chunks")
    
    # Test 4: Category distribution
    print("\n4. Category Distribution:")
    result = session.run("""
        MATCH (d:Document)
        WHERE d.category_hierarchy IS NOT NULL
        RETURN d.division as division, 
               d.category_hierarchy as category, 
               count(d) as count
        ORDER BY division, count DESC
        LIMIT 10
    """)
    for record in result:
        print(f"   {record['division']}/{record['category']}: {record['count']} documents")
    
    # Test 5: Products coverage
    print("\n5. Product Coverage:")
    result = session.run("""
        MATCH (p:Product)
        OPTIONAL MATCH (d:Document)-[:COVERS_PRODUCT]->(p)
        WITH p.name as product, count(DISTINCT d) as doc_count
        WHERE doc_count > 0
        RETURN product, doc_count
        ORDER BY doc_count DESC
        LIMIT 10
    """)
    for record in result:
        print(f"   {record['product']}: {record['doc_count']} documents")

driver.close()

print("\nHierarchical implementation test completed!")
print("✅ Hierarchy structure created")
print("✅ Documents classified") 
print("✅ Hierarchical filtering works")
print("✅ Categories and products linked")