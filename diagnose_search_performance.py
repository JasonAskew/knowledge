#!/usr/bin/env python3
"""
Diagnose search performance issues between Cypher and search_documents
"""

import json
import time
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer, CrossEncoder
import sys

# Configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "knowledge123"

def test_direct_cypher(driver, query):
    """Test using direct Cypher queries (similar to what Claude Desktop might do)"""
    print(f"\n=== Testing Direct Cypher for: '{query}' ===")
    
    # Extract keywords
    keywords = [w.lower() for w in query.split() if len(w) > 3]
    
    with driver.session() as session:
        # Try different Cypher strategies
        
        # Strategy 1: Simple keyword search
        print("\n1. Simple keyword search:")
        start = time.time()
        result = session.run("""
            MATCH (c:Chunk)
            WHERE """ + " OR ".join([f"toLower(c.text) CONTAINS '{kw}'" for kw in keywords]) + """
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            RETURN DISTINCT d.filename as document, c.page_num as page, 
                   c.text as text, c.id as chunk_id
            LIMIT 5
        """)
        
        results = list(result)
        print(f"  Found {len(results)} results in {time.time()-start:.2f}s")
        for r in results[:2]:
            print(f"  - {r['document']}, p.{r['page']}: {r['text'][:100]}...")
        
        # Strategy 2: Entity-based search
        print("\n2. Entity-based search:")
        start = time.time()
        result = session.run("""
            MATCH (e:Entity)
            WHERE """ + " OR ".join([f"toLower(e.text) CONTAINS '{kw}'" for kw in keywords]) + """
            MATCH (e)<-[:CONTAINS_ENTITY]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
            RETURN DISTINCT d.filename as document, c.page_num as page, 
                   c.text as text, COUNT(e) as entity_matches
            ORDER BY entity_matches DESC
            LIMIT 5
        """)
        
        results = list(result)
        print(f"  Found {len(results)} results in {time.time()-start:.2f}s")
        for r in results[:2]:
            print(f"  - {r['document']}, p.{r['page']} ({r['entity_matches']} entities): {r['text'][:100]}...")
        
        # Strategy 3: Check if embeddings exist
        print("\n3. Checking embeddings:")
        result = session.run("""
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL
            RETURN COUNT(c) as count
        """)
        embed_count = result.single()['count']
        print(f"  Chunks with embeddings: {embed_count}")

def test_hybrid_search(driver, model, query):
    """Test using the hybrid search approach from search_documents"""
    print(f"\n=== Testing Hybrid Search for: '{query}' ===")
    
    # Generate embedding
    print("Generating query embedding...")
    start = time.time()
    query_embedding = model.encode(query).tolist()
    print(f"  Embedding generated in {time.time()-start:.2f}s (dim: {len(query_embedding)})")
    
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    
    with driver.session() as session:
        print("\nRunning hybrid search query...")
        start = time.time()
        
        result = session.run("""
            MATCH (c:Chunk)
            WITH c, 
                 reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                    similarity + c.embedding[i] * $query_embedding[i]
                 ) as cosine_similarity,
                 SIZE([keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword]) as keyword_matches
            WHERE cosine_similarity > 0.5 OR keyword_matches > 0
            WITH c, cosine_similarity, keyword_matches,
                 (cosine_similarity * 0.7 + (toFloat(keyword_matches) / SIZE($keywords)) * 0.3) as hybrid_score
            ORDER BY hybrid_score DESC
            LIMIT 10
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            RETURN c.id as chunk_id,
                   c.text as text,
                   c.page_num as page_num,
                   d.filename as document,
                   hybrid_score as score,
                   cosine_similarity,
                   keyword_matches
        """, query_embedding=query_embedding, keywords=keywords)
        
        results = list(result)
        elapsed = time.time() - start
        print(f"  Found {len(results)} results in {elapsed:.2f}s")
        
        for i, r in enumerate(results[:3]):
            print(f"\n  Result {i+1}:")
            print(f"    Document: {r['document']}, p.{r['page_num']}")
            print(f"    Scores: hybrid={r['score']:.3f}, cosine={r['cosine_similarity']:.3f}, keywords={r['keyword_matches']}")
            print(f"    Text: {r['text'][:150]}...")

def check_test_questions(driver, model):
    """Check performance on actual test questions"""
    print("\n=== Checking Test Questions ===")
    
    # Sample test questions
    test_questions = [
        "What are the fees for international wire transfers?",
        "What is the minimum balance for a savings account?",
        "How do I report a lost or stolen credit card?",
        "What are the eligibility requirements for a home loan?",
        "What is the interest rate for term deposits?"
    ]
    
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Question: {q}")
        
        # Test both approaches
        test_direct_cypher(driver, q)
        test_hybrid_search(driver, model, q)

def main():
    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        # Verify connection
        driver.verify_connectivity()
        print("✓ Connected to Neo4j")
        
        # Get database stats
        with driver.session() as session:
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, COUNT(n) as count
                ORDER BY count DESC
            """)
            print("\nDatabase statistics:")
            for record in result:
                print(f"  {record['label']}: {record['count']}")
        
        # Load embedding model
        print("\nLoading embedding model...")
        start = time.time()
        model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        print(f"✓ Model loaded in {time.time()-start:.2f}s")
        
        # Run tests
        check_test_questions(driver, model)
        
    finally:
        driver.close()

if __name__ == "__main__":
    main()