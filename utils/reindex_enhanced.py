#!/usr/bin/env python3
"""
Re-index all documents with enhanced chunking and metadata
"""

import os
import sys
import json
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_ingestion_agent.enhanced_ingestion import EnhancedKnowledgeIngestion
from neo4j import GraphDatabase

def clear_existing_data(neo4j_uri, neo4j_user, neo4j_password):
    """Clear existing data before re-indexing"""
    print("Clearing existing data...")
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session() as session:
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared all existing data")
    finally:
        driver.close()

def create_enhanced_indices(neo4j_uri, neo4j_user, neo4j_password):
    """Create enhanced indices for better search performance"""
    print("Creating enhanced indices...")
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session() as session:
            # Create vector index with proper dimensions
            session.run("""
                CREATE VECTOR INDEX `chunk-embeddings` IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 384,
                    `vector.similarity_function`: 'cosine'
                }}
            """)
            
            # Create additional indices for enhanced search
            indices = [
                "CREATE INDEX chunk_keywords IF NOT EXISTS FOR (c:Chunk) ON (c.keywords)",
                "CREATE INDEX chunk_type IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_type)",
                "CREATE INDEX chunk_density IF NOT EXISTS FOR (c:Chunk) ON (c.semantic_density)",
                "CREATE INDEX doc_title IF NOT EXISTS FOR (d:Document) ON (d.title)",
                "CREATE INDEX doc_keywords IF NOT EXISTS FOR (d:Document) ON (d.keywords)",
                "CREATE INDEX entity_text IF NOT EXISTS FOR (e:Entity) ON (e.text)",
                "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)"
            ]
            
            for index_query in indices:
                try:
                    session.run(index_query)
                    print(f"Created index: {index_query.split()[2]}")
                except Exception as e:
                    print(f"Index might already exist: {e}")
            
            print("All indices created successfully")
    
    finally:
        driver.close()

def reindex_documents():
    """Re-index all documents with enhanced settings"""
    # Configuration
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    # Clear existing data
    clear_existing_data(neo4j_uri, neo4j_user, neo4j_password)
    
    # Create indices
    create_enhanced_indices(neo4j_uri, neo4j_user, neo4j_password)
    
    # Initialize enhanced ingestion
    ingestion = EnhancedKnowledgeIngestion(neo4j_uri, neo4j_user, neo4j_password)
    
    # Load inventory
    base_dir = Path(__file__).parent.parent
    inventory_path = base_dir / "full_mvp_inventory_docker.json"
    with open(inventory_path, 'r') as f:
        inventory = json.load(f)
    
    print(f"\nRe-indexing {len(inventory['files'])} documents with enhanced settings...")
    print("=" * 80)
    
    total_chunks = 0
    total_entities = 0
    start_time = time.time()
    
    for i, file_info in enumerate(inventory['files']):
        print(f"\n[{i+1}/{len(inventory['files'])}] Processing {file_info['filename']}...")
        
        # Get PDF path from inventory (already has correct path)
        pdf_path = Path(file_info['local_path'].replace('/data/pdfs/', 'knowledge_discovery_agent/westpac_pdfs/'))
        
        if not pdf_path.exists():
            print(f"  Warning: File not found at {pdf_path}")
            continue
        
        try:
            # Process with enhanced extraction
            result = ingestion.process_document_enhanced(
                str(pdf_path),
                {
                    'id': file_info.get('filename', '').replace('.pdf', ''),
                    'filename': file_info['filename'],
                    's3_key': file_info.get('original_url', ''),
                    'document_type': file_info.get('category', 'unknown')
                }
            )
            
            # Store in Neo4j
            ingestion.store_enhanced_knowledge(result)
            
            # Update statistics
            total_chunks += result['stats']['total_chunks']
            total_entities += result['stats']['unique_entities']
            
            print(f"  ✓ Processed: {result['stats']['total_chunks']} chunks, "
                  f"{result['stats']['unique_entities']} entities")
            print(f"  ✓ Avg chunk size: {result['stats']['avg_chunk_size']:.1f} words")
            print(f"  ✓ Definitions: {result['stats']['chunks_with_definitions']}, "
                  f"Examples: {result['stats']['chunks_with_examples']}")
            
        except Exception as e:
            print(f"  ✗ Error processing {file_info['filename']}: {e}")
    
    elapsed_time = time.time() - start_time
    
    print(f"\n{'='*80}")
    print("Re-indexing Complete!")
    print(f"Total documents: {len(inventory['files'])}")
    print(f"Total chunks: {total_chunks}")
    print(f"Total unique entities: {total_entities}")
    print(f"Time elapsed: {elapsed_time:.1f} seconds")
    print(f"Average time per document: {elapsed_time/len(inventory['files']):.1f} seconds")
    
    # Verify data in Neo4j
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        with driver.session() as session:
            # Count nodes
            result = session.run("""
                MATCH (d:Document) 
                RETURN count(d) as doc_count
            """)
            doc_count = result.single()['doc_count']
            
            result = session.run("""
                MATCH (c:Chunk) 
                RETURN count(c) as chunk_count,
                       avg(c.semantic_density) as avg_density
            """)
            record = result.single()
            chunk_count = record['chunk_count']
            avg_density = record['avg_density']
            
            result = session.run("""
                MATCH (e:Entity) 
                RETURN count(DISTINCT e) as entity_count
            """)
            entity_count = result.single()['entity_count']
            
            print(f"\nVerification:")
            print(f"  Documents in Neo4j: {doc_count}")
            print(f"  Chunks in Neo4j: {chunk_count}")
            print(f"  Entities in Neo4j: {entity_count}")
            print(f"  Average semantic density: {avg_density:.3f}")
            
    finally:
        driver.close()

if __name__ == "__main__":
    reindex_documents()